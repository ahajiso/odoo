"""Apply translations.csv to the stock monitor reports (OCA bi_sql_editor).

bi_sql_editor creates the report labels in English only, and recreates them in
English when a report is rebuilt: run this script again after each rebuild,
and once on production.

Usage (credentials from the environment, never stored):
    ODOO_URL=https://erp.lartdubati.com ODOO_DB=artdubati_test \
    ODOO_LOGIN=... ODOO_PASSWORD=... python3 apply_translations.py
The user needs Settings rights (Administration / Settings).
"""
import csv
import http.cookiejar
import json
import os
import urllib.request

URL, DB = os.environ["ODOO_URL"], os.environ["ODOO_DB"]
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
)


def post(path, params):
    req = urllib.request.Request(
        URL + path,
        json.dumps({"jsonrpc": "2.0", "params": params}).encode(),
        {"Content-Type": "application/json"},
    )
    res = json.load(opener.open(req, timeout=120))
    if "error" in res:
        raise RuntimeError(res["error"]["data"]["message"])
    return res.get("result")


def call(model, method, *args, **kwargs):
    return post(
        "/web/dataset/call_kw",
        {"model": model, "method": method, "args": list(args), "kwargs": kwargs},
    )


post(
    "/web/session/authenticate",
    {"db": DB, "login": os.environ["ODOO_LOGIN"], "password": os.environ["ODOO_PASSWORD"]},
)
rows = list(csv.DictReader(open(os.path.join(os.path.dirname(__file__), "translations.csv"))))
views = call("bi.sql.view", "search_read", [], ["technical_name", "model_name", "menu_id", "action_id"])
for lang in ("en_US", "fr_FR", "fa_IR"):
    ctx = {"lang": lang}
    for view in views:
        for row in rows:
            text = row[lang]
            if row["kind"] == "report" and row["key"] == view["technical_name"]:
                if view["menu_id"]:
                    call("ir.ui.menu", "write", [view["menu_id"][0]], {"name": text}, context=ctx)
                if view["action_id"]:
                    call("ir.actions.act_window", "write", [view["action_id"][0]], {"name": text}, context=ctx)
            elif row["kind"] == "field":
                ids = call("ir.model.fields", "search",
                           [("model", "=", view["model_name"]), ("name", "=", row["key"])])
                if ids:
                    call("ir.model.fields", "write", ids, {"field_description": text}, context=ctx)
            elif row["kind"] == "value":
                field, value = row["key"].split(".")
                ids = call("ir.model.fields.selection", "search",
                           [("field_id.model", "=", view["model_name"]),
                            ("field_id.name", "=", field), ("value", "=", value)])
                if ids:
                    call("ir.model.fields.selection", "write", ids, {"name": text}, context=ctx)
print("Translations applied to", ", ".join(v["technical_name"] for v in views))

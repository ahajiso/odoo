"""Phase 4, read-only: what an investor really sees and may read (docs/phase4/PLAN.md §2).

Logs in AS THE INVESTOR (credentials typed, never stored) and reports, without writing
anything:
- the investor's groups;
- the root menus shown to the investor;
- for a list of models: the read / write / create / delete access rights (ACL) and the
  number of records the investor can read (record rules applied).

Usage:
    read -r -p "Login: " ODOO_LOGIN && read -r -s -p "Password: " ODOO_PASSWORD && echo
    export ODOO_URL=https://erp.lartdubati.com ODOO_DB=artdubati_test ODOO_LOGIN ODOO_PASSWORD
    python3 probe_investor.py
    unset ODOO_PASSWORD
"""
import http.cookiejar
import json
import os
import urllib.request

URL, DB = os.environ["ODOO_URL"], os.environ["ODOO_DB"]
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
)

MODELS = [
    # what the investor needs
    "lartdubati.stock.monitor", "quick.start.screen", "quick.start.screen.action",
    "res.users", "res.partner", "res.company", "res.currency",
    # stock, products, equipment
    "stock.quant", "stock.lot", "stock.location", "stock.warehouse", "stock.move",
    "stock.move.line", "stock.picking", "product.template", "product.product",
    "product.category", "maintenance.equipment", "maintenance.request",
    "equipment.operation",
    # accounting, purchase, contracts
    "account.move", "account.move.line", "account.asset", "account.account",
    "purchase.order", "contract.contract", "contract.line", "res.currency.rate",
    # collaboration
    "mail.message", "discuss.channel", "ir.attachment", "calendar.event",
    "hr.employee", "hr.employee.public", "lartdubati.stock.access",
]


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
    return post("/web/dataset/call_kw",
                {"model": model, "method": method, "args": list(args), "kwargs": kwargs})


session = post("/web/session/authenticate", {
    "db": DB, "login": os.environ["ODOO_LOGIN"], "password": os.environ["ODOO_PASSWORD"]})
uid = session["uid"]
user = call("res.users", "read", [uid], ["login", "groups_id"])[0]
groups = call("res.groups", "read", user["groups_id"], ["full_name"])
print("User:", user["login"])
print("Groups:", ", ".join(sorted(g["full_name"] for g in groups)))

menus = call("ir.ui.menu", "load_menus", False)
roots = [menus[str(mid)]["name"] for mid in menus["root"]["children"]]
print("Root menus:", ", ".join(roots))

print(f"{'model':32} ACL   records")
for model in MODELS:
    try:
        rights = "".join(
            letter if call(model, "has_access", [], mode) else "."
            for letter, mode in zip("rwcd", ("read", "write", "create", "unlink")))
    except RuntimeError as error:
        print(f"{model:32} (not installed or refused: {str(error)[:60]})")
        continue
    count = call(model, "search_count", []) if rights[0] == "r" else "-"
    print(f"{model:32} {rights}  {count}")

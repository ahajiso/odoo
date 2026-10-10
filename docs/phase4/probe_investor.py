"""Phase 4, read-only: what an investor really sees and may read (docs/phase4/PLAN.md §2).

Logs in AS THE INVESTOR (credentials typed, never stored) and reports, without writing
anything:
- that the session is the expected investor login (ODOO_EXPECT_LOGIN) and that it reads
  the stock monitor; it never needs `res.groups`, which investors may not read after
  phase 4;
- the investor's groups when they are still readable (before phase 4);
- the root menus shown to the investor;
- for a list of models: the read / write / create / delete access rights (ACL) and the
  number of records the investor can read (record rules applied).

Usage:
    read -r -p "Login: " ODOO_LOGIN && read -r -s -p "Password: " ODOO_PASSWORD && echo
    export ODOO_URL=https://erp.lartdubati.com ODOO_DB=artdubati_test ODOO_LOGIN ODOO_PASSWORD
    export ODOO_EXPECT_LOGIN=test_investor
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
expected = os.environ["ODOO_EXPECT_LOGIN"]
print("User:", session.get("username"))
if session.get("username") != expected or expected != os.environ["ODOO_LOGIN"]:
    raise SystemExit(f"STOP: the session is not the expected investor login « {expected} ».")
print("Stock monitor rows readable:", call("lartdubati.stock.monitor", "search_count", []))
try:  # before phase 4 only: investors may not read res.groups afterwards
    user = call("res.users", "read", [session["uid"]], ["groups_id"])[0]
    groups = call("res.groups", "read", user["groups_id"], ["full_name"])
    print("Groups:", ", ".join(sorted(g["full_name"] for g in groups)))
except RuntimeError as error:
    print("Groups: not readable by this account (expected after phase 4):", str(error)[:60])

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

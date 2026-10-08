"""Phase 1 preparation of artdubati_test, BEFORE updating the modules.

Through JSON-RPC, on the running server (old code still loaded):
- lists every equipment (archived included) with its bill line, contracts and
  maintenance requests, then deletes them with their requests (test data, owner's
  decision);
- lists the active lent-out locations, checks they hold no stock, then archives them
  (O2: `Bg/TEST Lent out`; a lent-out stock will need a return location);
- lists every storable product that can be maintained and is not tracked by serial
  number: --apply is refused while one remains (fix them first: serial tracking,
  archive or delete).

With --after-update (run once the modules are updated): flags the category
« All / Fixed Assets » (created in phase 0) as fixed assets tracked in stock; the module
then checks its accounting setup and that its storable products are serialised.

Dry run by default; --apply only on artdubati_test; all checks before any write.

Usage (credentials from the environment, never stored):
    ODOO_URL=https://erp.lartdubati.com ODOO_DB=artdubati_test \
    ODOO_LOGIN=... ODOO_PASSWORD=... python3 setup_phase1.py [--after-update] [--apply]
Use an administrator outside the group « Stock Monitor Investor ».
"""
import http.cookiejar
import json
import os
import sys
import urllib.request

ALLOWED_DB = "artdubati_test"
APPLY = "--apply" in sys.argv
AFTER_UPDATE = "--after-update" in sys.argv
URL, DB = os.environ["ODOO_URL"], os.environ["ODOO_DB"]
if APPLY and DB != ALLOWED_DB:
    raise SystemExit(f"Refusing to modify any database except {ALLOWED_DB}")
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def post(path, params):
    req = urllib.request.Request(
        URL + path, json.dumps({"jsonrpc": "2.0", "params": params}).encode(),
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
    "db": DB, "login": os.environ["ODOO_LOGIN"], "password": os.environ["ODOO_PASSWORD"],
})
CTX = {"active_test": False}
print(f"Database {DB}, {'APPLY' if APPLY else 'DRY RUN'}\n")
try:
    investor = call("ir.model.data", "check_object_reference",
                    "lartdubati_investor_home", "group_stock_investor")[1]
except RuntimeError:
    investor = None
groups = call("res.users", "read", [session["uid"]], ["groups_id"])[0]["groups_id"]
if investor and investor in groups:
    raise SystemExit("This account is in « Stock Monitor Investor »: use another administrator.")

if AFTER_UPDATE:
    all_categ = call("ir.model.data", "check_object_reference", "product", "product_category_all")[1]
    categs = call("product.category", "search_read",
                  [("name", "=", "Fixed Assets"), ("parent_id", "=", all_categ)],
                  ["complete_name", "is_fixed_asset_stock"])
    if len(categs) != 1:
        raise SystemExit(f"category All / Fixed Assets: expected exactly one, found {categs}")
    categ = categs[0]
    print(f"category {categ['complete_name']} (id {categ['id']}): "
          f"is_fixed_asset_stock={categ['is_fixed_asset_stock']}")
    if categ["is_fixed_asset_stock"]:
        print("Nothing to do.")
    elif not APPLY:
        print("WOULD  flag it as fixed assets tracked in stock\n\nDry run only.")
    else:
        call("product.category", "write", [categ["id"]], {"is_fixed_asset_stock": True})
        print("APPLY  flagged (the module checked its accounting setup)\nDone.")
    sys.exit(0)

# 1. Equipment and their maintenance requests -----------------------------------------
fields = call("maintenance.equipment", "fields_get", [], attributes=["type"])
wanted = ["name", "active", "move_line_id", "contract_ids", "maintenance_ids"]
equipments = call("maintenance.equipment", "search_read", [],
                  [f for f in wanted if f in fields], context=CTX)
print(f"{len(equipments)} equipment record(s):")
for eq in equipments:
    print(f"  id {eq['id']} {eq['name']!r} active={eq['active']} "
          f"bill line={eq.get('move_line_id')} contracts={eq.get('contract_ids')} "
          f"requests={eq.get('maintenance_ids')}")
request_ids = call("maintenance.request", "search",
                   [("equipment_id", "in", [e["id"] for e in equipments])], context=CTX)

# 2. Lent-out locations -----------------------------------------------------------------
lent = call("stock.location", "search_read",
            [("place_type", "=", "lent_out"), ("active", "=", True)],
            ["complete_name", "usage"])
for loc in lent:
    quants = call("stock.quant", "search_count",
                  [("location_id", "child_of", loc["id"]), ("quantity", "!=", 0)])
    loc["quants"] = quants
    print(f"lent-out location {loc['complete_name']} (id {loc['id']}): {quants} quant(s)")
blocked = [loc for loc in lent if loc["quants"]]

# 3. Storable maintainable products not tracked by serial number -----------------------
products = call("product.template", "search_read",
                [("maintenance_ok", "=", True), ("is_storable", "=", True),
                 ("tracking", "!=", "serial")],
                ["name", "tracking", "qty_available", "active"])  # archived ones do not block
for prod in products:
    print(f"NOT SERIALISED: {prod['name']!r} (id {prod['id']}) tracking={prod['tracking']} "
          f"on hand={prod['qty_available']} active={prod['active']}")

print()
if blocked:
    raise SystemExit("Lent-out location(s) still holding stock: move it before archiving.")
if products:
    raise SystemExit(f"{len(products)} maintainable storable product(s) not tracked by serial "
                     "number: set serial tracking, archive or delete them, then rerun.")
print("All checks passed.\n")

if not APPLY:
    print(f"WOULD  delete {len(request_ids)} maintenance request(s) and {len(equipments)} "
          f"equipment record(s); archive {len(lent)} lent-out location(s)")
    print("\nDry run only: check the records above, then rerun with --apply.")
    sys.exit(0)
if request_ids:
    call("maintenance.request", "unlink", request_ids)
if equipments:
    call("maintenance.equipment", "unlink", [e["id"] for e in equipments])
if lent:
    call("stock.location", "write", [loc["id"] for loc in lent], {"active": False})
print(f"APPLY  deleted {len(request_ids)} request(s), {len(equipments)} equipment record(s); "
      f"archived {len(lent)} location(s)\nDone.")

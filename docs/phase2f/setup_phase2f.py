"""Phase 2f data preparation, run BEFORE the update (docs/phase2f/README.md, step 3).

Through JSON-RPC against the running Odoo (credentials from the environment, never
stored). Uses only fields that exist before the update (phase 2 schema).

Lists (always):
- D1: active integrated equipment without a valid responsible (none, archived, portal,
  or not allowed in the company);
- D2: candidate monitor stocks (warehouse stock locations, lent-out locations) and
  their address (city, country) – read only, to be completed in the interface;
- D3: equipment whose name starts with « Test »;
- D4: open incoming receipts not created by an equipment operation;
- D5: members of « Stock Monitor Investor » without an access profile, with their
  Inventory groups;
- approved operations: they will have to be approved again after the update (their
  approval carries no accounting treatment yet).

Changes (only with --apply, only on artdubati_test, only what the owner decided). Each
target must belong to the list the script prints, otherwise nothing is written:
  --responsible EQUIPMENT_ID=LOGIN   (repeatable) an equipment of the D1 list
  --archive-equipment EQUIPMENT_ID    (repeatable) an equipment of the D3 list (« Test… »)
  --cancel-receipt PICKING_NAME       (repeatable) a receipt of the D4 list

Usage:
    ODOO_URL=https://erp.lartdubati.com ODOO_DB=artdubati_test \
    ODOO_LOGIN=... ODOO_PASSWORD=... python3 setup_phase2f.py [options] [--apply]
"""
import argparse
import http.cookiejar
import json
import os
import sys
import urllib.request

ALLOWED_DB = "artdubati_test"
parser = argparse.ArgumentParser()
parser.add_argument("--apply", action="store_true")
parser.add_argument("--responsible", action="append", default=[], metavar="ID=LOGIN")
parser.add_argument("--archive-equipment", action="append", default=[], type=int, metavar="ID")
parser.add_argument("--cancel-receipt", action="append", default=[], metavar="NAME")
args = parser.parse_args()
URL, DB = os.environ["ODOO_URL"], os.environ["ODOO_DB"]
if args.apply and DB != ALLOWED_DB:
    raise SystemExit(f"Refusing to modify any database except {ALLOWED_DB}")
WOULD = "WILL" if args.apply else "WOULD"
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def post(path, params):
    req = urllib.request.Request(URL + path, json.dumps({"jsonrpc": "2.0", "params": params}).encode(),
                                 {"Content-Type": "application/json"})
    res = json.load(opener.open(req, timeout=120))
    if "error" in res:
        raise RuntimeError(res["error"]["data"]["message"])
    return res.get("result")


def call(model, method, *a, **kw):
    return post("/web/dataset/call_kw", {"model": model, "method": method, "args": list(a), "kwargs": kw})


session = post("/web/session/authenticate", {"db": DB, "login": os.environ["ODOO_LOGIN"],
                                             "password": os.environ["ODOO_PASSWORD"]})
print(f"Database {DB}, {'APPLY' if args.apply else 'DRY RUN'}\n")
company_id = call("res.users", "read", [session["uid"]], ["company_id"])[0]["company_id"][0]
errors, todo = [], []
Equip = {"context": {"active_test": False}}

# D1 ---------------------------------------------------------------------------------
equipment = call("maintenance.equipment", "search_read",
                 [("integration_state", "=", "done"), ("active", "=", True)],
                 ["name", "owner_user_id", "company_id"])
user_ids = sorted({e["owner_user_id"][0] for e in equipment if e["owner_user_id"]})
users = {u["id"]: u for u in call("res.users", "read", user_ids,
                                  ["login", "active", "share", "company_ids"],
                                  context={"active_test": False})} if user_ids else {}


def valid(eq):
    user = users.get(eq["owner_user_id"] and eq["owner_user_id"][0])
    company = eq["company_id"] and eq["company_id"][0]
    return bool(user) and user["active"] and not user["share"] and (
        not company or company in user["company_ids"])


invalid = [e for e in equipment if not valid(e)]
print(f"D1 – {len(invalid)} integrated equipment without a valid responsible:")
for e in invalid:
    print(f"  id {e['id']}: {e['name']} (responsible: {e['owner_user_id'] and e['owner_user_id'][1] or 'none'})")
d1_ids = {e["id"] for e in invalid}
for item in args.responsible:
    eq_id, _sep, login = item.partition("=")
    if not eq_id.isdigit() or int(eq_id) not in d1_ids:
        errors.append(f"--responsible {item}: equipment {eq_id} is not in the D1 list above")
        continue
    found = call("res.users", "search_read", [("login", "=", login)], ["login", "active", "share", "company_ids"])
    if len(found) != 1:
        errors.append(f"--responsible {item}: login {login} not found")
        continue
    user = found[0]
    if not user["active"] or user["share"] or company_id not in user["company_ids"]:
        errors.append(f"--responsible {item}: {login} is not an active internal user of the company")
        continue
    todo.append(("maintenance.equipment", int(eq_id), {"owner_user_id": user["id"]},
                 f"set responsible of equipment {eq_id} to {login}"))
print()

# D2 ---------------------------------------------------------------------------------
stock_ids = [w["lot_stock_id"][0] for w in call("stock.warehouse", "search_read", [], ["lot_stock_id"])]
stocks = call("stock.location", "search_read",
              ["|", ("id", "in", stock_ids), ("place_type", "=", "lent_out"), ("usage", "=", "internal")],
              ["complete_name", "address_id"])
print("D2 – candidate monitor stocks and their address:")
for loc in stocks:
    if loc["address_id"]:
        partner = call("res.partner", "read", [loc["address_id"][0]], ["city", "country_id"])[0]
        city, country = partner["city"] or "NO CITY", partner["country_id"] and partner["country_id"][1] or "NO COUNTRY"
        print(f"  {loc['complete_name']}: {loc['address_id'][1]} – {city}, {country}")
    else:
        print(f"  {loc['complete_name']}: NO ADDRESS (to set before phase 3)")
print()

# D3 ---------------------------------------------------------------------------------
tests = call("maintenance.equipment", "search_read", [("name", "=ilike", "test%")],
             ["name", "integration_state", "active", "stock_lot_id"], **Equip)
print(f"D3 – {len(tests)} equipment named « Test… »:")
for e in tests:
    print(f"  id {e['id']}: {e['name']} state={e['integration_state']} active={e['active']} "
          f"serial={e['stock_lot_id'] and e['stock_lot_id'][1]}")
d3 = {e["id"]: e for e in tests}
for eq_id in args.archive_equipment:
    if eq_id not in d3:
        errors.append(f"--archive-equipment {eq_id}: not in the D3 list above (« Test… » only)")
        continue
    todo.append(("maintenance.equipment", eq_id, {"active": False},
                 f"archive equipment {eq_id} ({d3[eq_id]['name']})"))
print()

# D4 ---------------------------------------------------------------------------------
receipts = call("stock.picking", "search_read",
                [("picking_type_code", "=", "incoming"), ("state", "not in", ["done", "cancel"]),
                 ("equipment_operation_id", "=", False)], ["name", "origin", "partner_id", "state"])
print(f"D4 – {len(receipts)} open receipt(s) not created by an equipment operation:")
for p in receipts:
    print(f"  {p['name']} origin={p['origin']} partner={p['partner_id'] and p['partner_id'][1]} state={p['state']}")
by_name = {p["name"]: p for p in receipts}
cancel = []
for name in args.cancel_receipt:
    if name not in by_name:
        errors.append(f"--cancel-receipt {name}: not an open receipt of the list")
    else:
        cancel.append(by_name[name])
print()

# D5 ---------------------------------------------------------------------------------
try:
    investor = call("ir.model.data", "check_object_reference", "lartdubati_investor_home", "group_stock_investor")[1]
    stock_user = call("ir.model.data", "check_object_reference", "stock", "group_stock_user")[1]
    members = call("res.users", "search_read", [("groups_id", "in", [investor])],
                   ["login", "groups_id", "stock_access_id"])
    print("D5 – investors:")
    for u in members:
        flags = []
        if stock_user in u["groups_id"]:
            flags.append("HAS INVENTORY RIGHTS")
        if not u["stock_access_id"]:
            flags.append("no access profile")
        print(f"  {u['login']}: {', '.join(flags) or 'ok'}")
except RuntimeError as exc:
    print(f"D5 – not checked: {exc}")
print()

approved = call("equipment.operation", "search_read", [("state", "=", "approved")], ["name"])
print(f"{len(approved)} approved operation(s), to approve again after the update: "
      f"{[o['name'] for o in approved]}\n")

if errors:
    raise SystemExit("Errors, nothing written:\n  " + "\n  ".join(errors))
for model, rec_id, vals, label in todo:
    print(f"{WOULD} {label}")
for p in cancel:
    print(f"{WOULD} cancel receipt {p['name']}")
if not args.apply:
    print("\nDry run only: check the lines above, then rerun with --apply.")
    sys.exit(0)
for model, rec_id, vals, label in todo:
    call(model, "write", [rec_id], vals)
    print(f"APPLY  {label}")
for p in cancel:
    call("stock.picking", "action_cancel", [p["id"]])
    print(f"APPLY  cancelled {p['name']}")
print("Done. Run precheck.sh next.")

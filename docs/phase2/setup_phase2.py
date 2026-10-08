"""Phase 2 settings of artdubati_test, AFTER updating the modules (18.0.3.0.0).

Through JSON-RPC (credentials from the environment, never stored):
- checks the accounts of the test choices exist: 613500 (C10), 708300 (C16),
  778000, 455100, 603200 (C17);
- looks up, or creates, the three service products of the contract lines:
  « Prêt de matériel », « Location de matériel (payée) » (expense 613500),
  « Location de matériel (facturée) » (income 708300);
- looks up, or creates, the three acquisition locations (inventory usage, under
  « Virtual Locations »), each with its credited account (C17);
- flags the internal location « Chez tiers » (phase 0) as parent of off-site stocks;
- writes the company settings (Invoicing → Equipment);
- refuses to go on if a warehouse receives in several steps (not supported);
- lists, without changing them: serial numbers of maintainable products in internal
  stock without equipment, open incoming receipts (to be received through equipment
  operations from now on), lent-out locations without address, incoming operation
  types with their default destination, members of the two new groups.

Dry run by default; --apply only on artdubati_test; every check before any write.

Usage:
    ODOO_URL=https://erp.lartdubati.com ODOO_DB=artdubati_test \
    ODOO_LOGIN=... ODOO_PASSWORD=... python3 setup_phase2.py [--apply]
Use an administrator outside the group « Stock Monitor Investor ».
"""
import http.cookiejar
import json
import os
import sys
import urllib.request

ALLOWED_DB = "artdubati_test"
APPLY = "--apply" in sys.argv
URL, DB = os.environ["ODOO_URL"], os.environ["ODOO_DB"]
if APPLY and DB != ALLOWED_DB:
    raise SystemExit(f"Refusing to modify any database except {ALLOWED_DB}")
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

ACCOUNTS = {"rent_paid": "613500", "rent_received": "708300", "gift": "778000",
            "current_account": "455100", "regularisation": "603200"}
PRODUCTS = [
    # (setting field, name, account role, account field)
    ("equipment_loan_product_id", "Prêt de matériel", None, None),
    ("equipment_rent_paid_product_id", "Location de matériel (payée)", "rent_paid",
     "property_account_expense_id"),
    ("equipment_rent_received_product_id", "Location de matériel (facturée)", "rent_received",
     "property_account_income_id"),
]
LOCATIONS = [
    ("equipment_gift_location_id", "Acquisitions - Don", "gift"),
    ("equipment_current_account_location_id", "Acquisitions - Apport en compte courant",
     "current_account"),
    ("equipment_regularisation_location_id", "Acquisitions - Régularisation", "regularisation"),
]


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


def xmlid(module, name):
    return call("ir.model.data", "check_object_reference", module, name)[1]


session = post("/web/session/authenticate", {
    "db": DB, "login": os.environ["ODOO_LOGIN"], "password": os.environ["ODOO_PASSWORD"],
})
print(f"Database {DB}, {'APPLY' if APPLY else 'DRY RUN'}\n")
try:
    investor = xmlid("lartdubati_investor_home", "group_stock_investor")
except RuntimeError:
    investor = None
user = call("res.users", "read", [session["uid"]], ["groups_id", "company_id"])[0]
if investor and investor in user["groups_id"]:
    raise SystemExit("This account is in « Stock Monitor Investor »: use another administrator.")
company_id = user["company_id"][0]
fields = call("res.company", "fields_get", [], attributes=["type"])
if "equipment_loan_product_id" not in fields:
    raise SystemExit("The modules are not updated yet (18.0.3.0.0): run the update first.")
company = call("res.company", "read", [company_id],
               [f for f, *_ in PRODUCTS] + [f for f, *_ in LOCATIONS])[0]
print(f"company {user['company_id'][1]} (id {company_id})\n")
errors, todo = [], []

# 1. Accounts ---------------------------------------------------------------------------
accounts = {}
for role, code in ACCOUNTS.items():
    found = call("account.account", "search_read",
                 [("code", "=", code), ("company_ids", "in", [company_id])], ["code", "name"])
    if len(found) != 1:
        errors.append(f"account {code}: expected exactly one, found {len(found)}")
        continue
    accounts[role] = found[0]["id"]
    print(f"account {code} {found[0]['name']} (id {found[0]['id']})")
print()

# 2. Service products of the contract lines ------------------------------------------
products = {}
for setting, name, role, account_field in PRODUCTS:
    read = ["name", "type", "maintenance_ok", "company_id"] + ([account_field] if account_field else [])
    found = call("product.product", "search_read",
                 [("name", "=", name), ("company_id", "in", [False, company_id])], read)
    if len(found) > 1:
        errors.append(f"product {name!r}: {len(found)} found, keep one")
        continue
    if found:
        prod = found[0]
        bad = []
        if prod["type"] != "service" or prod["maintenance_ok"]:
            bad.append("must be a service, not maintainable")
        if account_field and role in accounts and (prod[account_field] or [None])[0] != accounts[role]:
            bad.append(f"{account_field} must be {ACCOUNTS[role]}")
        if bad:
            errors.append(f"product {name!r} (id {prod['id']}): " + ", ".join(bad))
        products[setting] = prod["id"]
        print(f"product {name!r}: found (id {prod['id']})")
    else:
        vals = {"name": name, "type": "service", "purchase_ok": role != "rent_received",
                "sale_ok": role == "rent_received"}
        if account_field and role in accounts:
            vals[account_field] = accounts[role]
        todo.append(("product.product", vals, setting))
        print(f"product {name!r}: WOULD create")
    if company[setting] and products.get(setting) and company[setting][0] != products[setting]:
        print(f"  setting {setting} currently {company[setting]}: WOULD replace")
print()

# 3. Acquisition locations (C17) ------------------------------------------------------
virtual = xmlid("stock", "stock_location_locations_virtual")
locations = {}
for setting, name, role in LOCATIONS:
    found = call("stock.location", "search_read",
                 [("name", "=", name), ("usage", "=", "inventory"),
                  ("company_id", "in", [False, company_id])],
                 ["complete_name", "valuation_out_account_id"], context={"active_test": False})
    if len(found) > 1:
        errors.append(f"location {name!r}: {len(found)} found, keep one")
        continue
    if found:
        loc = found[0]
        if role in accounts and (loc["valuation_out_account_id"] or [None])[0] != accounts[role]:
            errors.append(f"location {loc['complete_name']!r}: account must be {ACCOUNTS[role]}")
        locations[setting] = loc["id"]
        print(f"location {loc['complete_name']!r}: found (id {loc['id']})")
    else:
        vals = {"name": name, "usage": "inventory", "location_id": virtual,
                "company_id": company_id}
        if role in accounts:
            vals["valuation_out_account_id"] = accounts[role]
        todo.append(("stock.location", vals, setting))
        print(f"location {name!r}: WOULD create under Virtual Locations, account {ACCOUNTS[role]}")
print()

# 4. Parent of off-site stocks ----------------------------------------------------------
parents = call("stock.location", "search_read",
               [("name", "=", "Chez tiers"), ("usage", "=", "internal"),
                ("company_id", "in", [False, company_id])],
               ["complete_name", "is_offsite_parent"])
if len(parents) != 1:
    errors.append(f"internal location « Chez tiers »: expected exactly one, found {parents}")
else:
    parent = parents[0]
    state = "already flagged" if parent["is_offsite_parent"] else "WOULD flag as parent of off-site stocks"
    print(f"location {parent['complete_name']} (id {parent['id']}): {state}\n")

# 5. Receipts in one step only ------------------------------------------------------
warehouses = call("stock.warehouse", "search_read", [("company_id", "=", company_id)],
                  ["name", "code", "reception_steps"])
for wh in warehouses:
    print(f"warehouse {wh['name']} ({wh['code']}): reception_steps={wh['reception_steps']}")
    if wh["reception_steps"] != "one_step":
        errors.append(f"warehouse {wh['name']}: receipts in several steps are not supported "
                      "by the equipment operations; set « Receive goods directly (1 step) »")
print()

# 6. Lists (no change) ----------------------------------------------------------------
lots = call("stock.quant", "search_read",
            [("quantity", ">", 0), ("location_id.usage", "=", "internal"),
             ("lot_id", "!=", False), ("product_id.maintenance_ok", "=", True)],
            ["lot_id", "product_id", "location_id"])
equipped = set()
if lots:
    eqs = call("maintenance.equipment", "search_read",
               [("stock_lot_id", "in", [q["lot_id"][0] for q in lots])], ["stock_lot_id"],
               context={"active_test": False})
    equipped = {e["stock_lot_id"][0] for e in eqs}
orphans = [q for q in lots if q["lot_id"][0] not in equipped]
print(f"{len(orphans)} serial number(s) of maintainable products in stock without equipment:")
for q in orphans:
    print(f"  {q['product_id'][1]} {q['lot_id'][1]} in {q['location_id'][1]}")
receipts = call("stock.picking", "search_read",
                [("picking_type_code", "=", "incoming"),
                 ("state", "not in", ["done", "cancel"])], ["name", "origin", "partner_id"])
print(f"{len(receipts)} open receipt(s), to be received through equipment operations:")
for p in receipts:
    print(f"  {p['name']} origin={p['origin']} partner={p['partner_id'] and p['partner_id'][1]}")
lent = call("stock.location", "search_read",
            [("place_type", "=", "lent_out"), ("address_id", "=", False)], ["complete_name"])
print(f"{len(lent)} active lent-out location(s) without address: "
      f"{[loc['complete_name'] for loc in lent]}")
types = call("stock.picking.type", "search_read", [("code", "=", "incoming")],
             ["display_name", "default_location_dest_id"])
print("incoming operation types:")
for t in types:
    print(f"  {t['display_name']} (id {t['id']}) -> {t['default_location_dest_id'] and t['default_location_dest_id'][1]}")
for group in ("group_equipment_operator", "group_equipment_approver"):
    gid = xmlid("maintenance_shareholder_equipment", group)
    users = call("res.users", "search_read", [("groups_id", "in", [gid])], ["login"])
    print(f"members of {group}: {[u['login'] for u in users] or 'none (to give before the interface tests)'}")
print()

if errors:
    raise SystemExit("Errors, nothing written:\n  " + "\n  ".join(errors))
print("All checks passed.\n")
if not APPLY:
    print("Dry run only: check the lines above, then rerun with --apply.")
    sys.exit(0)

settings = {}
for model, vals, setting in todo:
    new_id = call(model, "create", vals)
    settings[setting] = new_id
    print(f"APPLY  created {model} {vals['name']!r} (id {new_id})")
settings.update({k: v for k, v in products.items()})
settings.update({k: v for k, v in locations.items()})
call("res.company", "write", [company_id], settings)
print(f"APPLY  company settings written: {sorted(settings)}")
if not parent["is_offsite_parent"]:
    call("stock.location", "write", [parent["id"]], {"is_offsite_parent": True})
    print(f"APPLY  {parent['complete_name']} flagged as parent of off-site stocks")
print("Done.")

"""Phase 0 configuration of artdubati_test (revision 2 of docs/DEFINITIONS.md).

Sets, through JSON-RPC, the settings that need no code:
- Lots & Serial Numbers enabled (equipment is tracked by serial number);
- accounting choices FOR THE TEST DATABASE, to be reviewed by the accountant
  (see docs/phase0/README.md, "Accounting choices"): asset profile, its link on the
  fixed-asset account, product category "All / Fixed Assets";
- third-party location "Chez tiers" under the warehouse root location, outside its
  stock location (checked, created if missing).

Dry run by default: prints what it found (external IDs, accounts, journal) and what it
would do. Nothing is written without --apply, and --apply only works on
artdubati_test. Safe to run again: it creates what is missing and never changes an
existing profile, category or account link (the accountant may have changed them)
unless --force-update is given.

Usage (credentials from the environment, never stored):
    ODOO_URL=https://erp.lartdubati.com ODOO_DB=artdubati_test \
    ODOO_LOGIN=... ODOO_PASSWORD=... python3 setup_phase0.py [--apply [--force-update]]
The user running it needs the Administration / Settings right.
"""
import http.cookiejar
import json
import os
import sys
import urllib.request

# --- Choices for the test database (accountant may change them) -----------------
# Exact codes of the Odoo 18 French chart of accounts (l10n_fr_account template).
ASSET_ACCOUNT = "215400"         # Matériels industriels
DEPRECIATION_ACCOUNT = "281500"  # Amortissements installations, matériel et outillage industriels
EXPENSE_ACCOUNT = "681120"       # Dotations aux amortissements des immobilisations corporelles
PROFILE_NAME = "Matériel et outillage (test)"
PROFILE_VALUES = {
    "method": "linear",
    "method_time": "year",
    "method_number": 5,          # years
    "method_period": "year",
    "prorata": True,
    "open_asset": False,         # assets stay in draft until the accountant confirms
    "asset_product_item": True,  # one asset per unit (one per serial number)
}
CATEGORY_NAME = "Fixed Assets"   # under "All"; category names are not translatable
CATEGORY_COST_METHOD = "average"
CATEGORY_VALUATION = "manual_periodic"
WAREHOUSE_CODE = "Bg"            # warehouse "Bougival 1"; its root location shows as WH
WAREHOUSE_NAME = "Bougival 1"
THIRD_PARTY_LOCATION = "Chez tiers"
ALLOWED_DB = "artdubati_test"
# ----------------------------------------------------------------------------------

APPLY = "--apply" in sys.argv
FORCE = "--force-update" in sys.argv
URL, DB = os.environ["ODOO_URL"], os.environ["ODOO_DB"]
if APPLY and DB != ALLOWED_DB:
    raise SystemExit(f"Refusing to modify any database except {ALLOWED_DB}")
if FORCE and not APPLY:
    raise SystemExit("--force-update needs --apply")
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


def ref(xmlid):
    module, name = xmlid.split(".")
    return call("ir.model.data", "check_object_reference", module, name)[1]


def one(model, domain, fields, what):
    recs = call(model, "search_read", domain, fields, context=CTX)
    if len(recs) != 1:
        found = ", ".join(str(r) for r in recs) or "none"
        raise SystemExit(f"{what}: expected exactly one record, found {found}")
    return recs[0]


def account(code):
    return one("account.account", [("code", "=", code)], ["code", "name"], f"account {code}")


def do(label, fn):
    print(("APPLY  " if APPLY else "WOULD  ") + label)
    if APPLY:
        return fn()
    return None


DIFFS = []


def compare(label, record, expected):
    """Print the structural values that differ from the test choices (never written)."""
    for field, want in expected.items():
        got = record[field]
        got = got[0] if isinstance(got, list) and got else got
        if got != want:
            DIFFS.append(f"{label}.{field}")
            print(f"DIFF   {label}: {field} = {record[field]!r}, test choice {want!r}")


def keep(label):
    print(f"KEEP   {label} (exists; rerun with --apply --force-update to overwrite)")


session = post("/web/session/authenticate", {
    "db": DB, "login": os.environ["ODOO_LOGIN"], "password": os.environ["ODOO_PASSWORD"],
})
company_id = session["user_companies"]["current_company"]
CTX = {"lang": "fr_FR", "allowed_company_ids": [company_id]}
print(f"Database {DB}, company id {company_id}, {'APPLY' if APPLY else 'DRY RUN'}\n")

# 0. Checks before any write: warehouse and third-party location ---------------------
wh = one("stock.warehouse", [("company_id", "=", company_id), ("code", "=", WAREHOUSE_CODE)],
         ["name", "lot_stock_id", "view_location_id"], f"warehouse {WAREHOUSE_CODE}")
if wh["name"] != WAREHOUSE_NAME:
    raise SystemExit(f"warehouse {WAREHOUSE_CODE} is named '{wh['name']}', "
                     f"expected '{WAREHOUSE_NAME}': check the constants")
root_id, stock_id = wh["view_location_id"][0], wh["lot_stock_id"][0]
# The global rule of lartdubati_investor_home hides internal locations from members of
# "Stock Monitor Investor", administrators included: a hidden "Chez tiers" would look
# missing. Refuse such an account and prove the locations are readable.
try:
    investor_group = ref("lartdubati_investor_home.group_stock_investor")
except RuntimeError:
    investor_group = None
my_groups = call("res.users", "read", [session["uid"]], ["groups_id"])[0]["groups_id"]
if investor_group and investor_group in my_groups:
    raise SystemExit("This account is in the group 'Stock Monitor Investor': its stock access "
                     "profile hides locations. Use an administrator outside that group.")
try:
    readable = call("stock.location", "read", [root_id, stock_id], ["complete_name"], context=CTX)
except RuntimeError as e:
    raise SystemExit(f"Cannot read the warehouse locations {root_id}, {stock_id} ({e}). Use an "
                     "administrator outside the group 'Stock Monitor Investor'.")
if len(readable) != 2:
    raise SystemExit("The warehouse root or stock location is not readable by this account. Use "
                     "an administrator outside the group 'Stock Monitor Investor'.")
print(f"warehouse {wh['name']} ({WAREHOUSE_CODE}): root {wh['view_location_id']}, "
      f"stock {wh['lot_stock_id']}")
stock_path = call("stock.location", "read", [stock_id], ["parent_path"], context=CTX)[0]["parent_path"]
if f"/{root_id}/" not in "/" + stock_path:
    # Intentional on artdubati_test (owner's choice): Bg/Stock is outside the root WH, so
    # its warehouse_id is empty. Reported, not blocking; code must not rely on
    # stock.location.warehouse_id to find the warehouse of Bg/Stock.
    print(f"NOTE   stock location {wh['lot_stock_id'][1]} is not under the warehouse root "
          f"{wh['view_location_id'][1]}: its warehouse_id is empty (known, intentional)")
locs = call("stock.location", "search_read",
            [("name", "=", THIRD_PARTY_LOCATION), ("location_id", "child_of", root_id),
             ("company_id", "in", [company_id, False])],
            ["complete_name", "location_id", "parent_path", "usage", "active"],
            context=dict(CTX, active_test=False))
if len(locs) > 1:
    raise SystemExit(f"location {THIRD_PARTY_LOCATION}: several found {locs}")
if locs:
    loc = locs[0]
    if not loc["active"]:
        raise SystemExit(f"{loc['complete_name']} is archived: unarchive it in Odoo, then rerun")
    if f"/{stock_id}/" in loc["parent_path"]:
        raise SystemExit(f"{loc['complete_name']} is INSIDE the stock location: move it under "
                         "the warehouse root in Odoo, then rerun")
    if loc["usage"] != "internal":
        raise SystemExit(f"{loc['complete_name']} has type '{loc['usage']}', expected internal")
    if loc["location_id"][0] != root_id:
        raise SystemExit(f"{loc['complete_name']} is under {loc['location_id'][1]}, expected "
                         f"directly under the warehouse root {wh['view_location_id'][1]}")
    print(f"{loc['complete_name']} ({loc['usage']}): parent {loc['location_id']}, "
          "outside the stock location: OK")
else:
    print(f"location {THIRD_PARTY_LOCATION}: to create under {wh['view_location_id'][1]}")

# 1. Lots & Serial Numbers ------------------------------------------------------------
lot_group = ref("stock.group_production_lot")
user_group = ref("base.group_user")
implied = call("res.groups", "read", [user_group], ["implied_ids"])[0]["implied_ids"]
print(f"stock.group_production_lot = {lot_group}; enabled: {lot_group in implied}")

# 2. Accounts, journal, asset profile -------------------------------------------------
asset_acc = account(ASSET_ACCOUNT)
depr_acc = account(DEPRECIATION_ACCOUNT)
exp_acc = account(EXPENSE_ACCOUNT)
journal = one("account.journal", [("type", "=", "general"), ("company_id", "=", company_id),
                                  ("code", "in", ["OD", "MISC"])], ["code", "name"],
              "miscellaneous journal (code OD or MISC)")
for label, rec in (("asset account", asset_acc), ("depreciation account", depr_acc),
                   ("expense account", exp_acc), ("journal", journal)):
    print(f"{label}: {rec}")

all_categ = ref("product.product_category_all")
categs = call("product.category", "search",
              [("name", "=", CATEGORY_NAME), ("parent_id", "=", all_categ)], context=CTX)
if len(categs) > 1:
    raise SystemExit(f"category 'All / {CATEGORY_NAME}': {len(categs)} duplicates {categs}")
profiles = call("account.asset.profile", "search",
                [("name", "=", PROFILE_NAME), ("company_id", "=", company_id)], context=CTX)
if len(profiles) > 1:
    raise SystemExit(f"asset profile '{PROFILE_NAME}': {len(profiles)} duplicates {profiles}, "
                     "remove the extra ones first")
print("All checks passed.\n")

if lot_group not in implied:
    do("enable Lots & Serial Numbers (Inventory settings)", lambda: call(
        "res.config.settings", "execute",
        [call("res.config.settings", "create", {"group_stock_production_lot": True})]))

profile_vals = dict(PROFILE_VALUES, account_asset_id=asset_acc["id"],
                    account_depreciation_id=depr_acc["id"],
                    account_expense_depreciation_id=exp_acc["id"],
                    journal_id=journal["id"], company_id=company_id)
print(f"asset profile '{PROFILE_NAME}': {profiles or 'to create'}")
if not profiles:
    profile_id = do("create asset profile", lambda: call(
        "account.asset.profile", "create", dict(profile_vals, name=PROFILE_NAME), context=CTX))
elif FORCE:
    do("overwrite asset profile", lambda: call("account.asset.profile", "write", profiles,
                                               profile_vals, context=CTX))
    profile_id = profiles[0]
else:
    keep("asset profile")
    profile_id = profiles[0]
if profiles:
    existing = call("account.asset.profile", "read", profiles, list(profile_vals), context=CTX)[0]
    compare("asset profile", existing, profile_vals)
current = call("account.account", "read", [asset_acc["id"]], ["asset_profile_id"],
               context=CTX)[0]["asset_profile_id"]
print(f"profile on account {asset_acc['code']}: {current}")
if not current or (FORCE and current[0] != profile_id):
    do(f"set the asset profile on account {asset_acc['code']}",
       lambda: call("account.account", "write", [asset_acc["id"]],
                    {"asset_profile_id": profile_id}, context=CTX))
elif current[0] != profile_id:
    keep(f"other profile on account {asset_acc['code']}")
    DIFFS.append("account.asset_profile_id")
    print(f"DIFF   account {asset_acc['code']}: asset_profile_id = {current!r}, "
          f"test choice {profile_id}")

# 3. Product category All / Fixed Assets ----------------------------------------------
print(f"product.product_category_all = {all_categ}")
categ_vals = {"parent_id": all_categ, "property_cost_method": CATEGORY_COST_METHOD,
              "property_valuation": CATEGORY_VALUATION,
              "property_account_expense_categ_id": asset_acc["id"]}
print(f"category 'All / {CATEGORY_NAME}': {categs or 'to create'}")
if not categs:
    do("create category", lambda: call("product.category", "create",
                                       dict(categ_vals, name=CATEGORY_NAME), context=CTX))
elif FORCE:
    do("overwrite category", lambda: call("product.category", "write", categs, categ_vals,
                                          context=CTX))
else:
    keep("category")
if categs:
    existing = call("product.category", "read", categs, list(categ_vals), context=CTX)[0]
    compare("category", existing, categ_vals)

# 4. Third-party location (created only if missing) -----------------------------------
if not locs:
    do(f"create internal location {THIRD_PARTY_LOCATION} under the warehouse root",
       lambda: call("stock.location", "create", {
           "name": THIRD_PARTY_LOCATION, "usage": "internal", "location_id": root_id,
           "company_id": company_id}, context=CTX))

if DIFFS:
    print(f"\n{len(DIFFS)} value(s) differ from the test choices (kept, not overwritten): "
          + ", ".join(DIFFS) + ". Expected if the accountant changed them; otherwise check, "
          "or rerun with --apply --force-update.")
print("\nDone." if APPLY else "\nDry run only: check the records above, then rerun with --apply.")

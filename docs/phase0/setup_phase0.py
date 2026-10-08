"""Phase 0 configuration of artdubati_test (revision 2 of docs/DEFINITIONS.md).

Sets, through JSON-RPC, the settings that need no code:
- Lots & Serial Numbers enabled (equipment is tracked by serial number);
- accounting choices FOR THE TEST DATABASE, to be reviewed by the accountant
  (see docs/phase0/README.md, "Accounting choices"): asset profile, its link on the
  fixed-asset account, product category "All / Fixed Assets";
- check that the third-party location (WH/Chez tiers) is outside WH/Stock.

Dry run by default: prints what it found (external IDs, accounts, journal) and what it
would do. Nothing is written without --apply. Safe to run again: it updates what
exists.

Usage (credentials from the environment, never stored):
    ODOO_URL=https://erp.lartdubati.com ODOO_DB=artdubati_test \
    ODOO_LOGIN=... ODOO_PASSWORD=... python3 setup_phase0.py [--apply]
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
THIRD_PARTY_LOCATION = "Chez tiers"
# ----------------------------------------------------------------------------------

APPLY = "--apply" in sys.argv
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


session = post("/web/session/authenticate", {
    "db": DB, "login": os.environ["ODOO_LOGIN"], "password": os.environ["ODOO_PASSWORD"],
})
company_id = session["user_companies"]["current_company"]
CTX = {"lang": "fr_FR", "allowed_company_ids": [company_id]}
print(f"Database {DB}, company id {company_id}, {'APPLY' if APPLY else 'DRY RUN'}\n")

# 1. Lots & Serial Numbers ------------------------------------------------------------
lot_group = ref("stock.group_production_lot")
user_group = ref("base.group_user")
implied = call("res.groups", "read", [user_group], ["implied_ids"])[0]["implied_ids"]
print(f"stock.group_production_lot = {lot_group}; enabled: {lot_group in implied}")
if lot_group not in implied:
    do("enable Lots & Serial Numbers (Inventory settings)", lambda: call(
        "res.config.settings", "execute",
        [call("res.config.settings", "create", {"group_stock_production_lot": True})]))

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

profile_vals = dict(PROFILE_VALUES, account_asset_id=asset_acc["id"],
                    account_depreciation_id=depr_acc["id"],
                    account_expense_depreciation_id=exp_acc["id"],
                    journal_id=journal["id"], company_id=company_id)
profiles = call("account.asset.profile", "search", [("name", "=", PROFILE_NAME)], context=CTX)
print(f"asset profile '{PROFILE_NAME}': {profiles or 'to create'}")
if profiles:
    do("update asset profile", lambda: call("account.asset.profile", "write", profiles,
                                            profile_vals, context=CTX))
    profile_id = profiles[0]
else:
    profile_id = do("create asset profile", lambda: call(
        "account.asset.profile", "create", dict(profile_vals, name=PROFILE_NAME), context=CTX))
current = call("account.account", "read", [asset_acc["id"]], ["asset_profile_id"],
               context=CTX)[0]["asset_profile_id"]
print(f"profile on account {asset_acc['code']}: {current}")
do(f"set the asset profile on account {asset_acc['code']}",
   lambda: call("account.account", "write", [asset_acc["id"]],
                {"asset_profile_id": profile_id}, context=CTX))

# 3. Product category All / Fixed Assets ----------------------------------------------
all_categ = ref("product.product_category_all")
print(f"product.product_category_all = {all_categ}")
categ_vals = {"parent_id": all_categ, "property_cost_method": CATEGORY_COST_METHOD,
              "property_valuation": CATEGORY_VALUATION,
              "property_account_expense_categ_id": asset_acc["id"]}
categs = call("product.category", "search",
              [("name", "=", CATEGORY_NAME), ("parent_id", "=", all_categ)], context=CTX)
print(f"category 'All / {CATEGORY_NAME}': {categs or 'to create'}")
if categs:
    do("update category", lambda: call("product.category", "write", categs, categ_vals,
                                       context=CTX))
else:
    do("create category", lambda: call("product.category", "create",
                                       dict(categ_vals, name=CATEGORY_NAME), context=CTX))

# 4. Third-party location outside WH/Stock (check only) --------------------------------
wh = one("stock.warehouse", [("company_id", "=", company_id), ("code", "=", "WH")],
         ["lot_stock_id", "view_location_id"], "warehouse WH")
loc = one("stock.location", [("name", "=", THIRD_PARTY_LOCATION), ("usage", "=", "internal")],
          ["complete_name", "location_id", "parent_path"], f"location {THIRD_PARTY_LOCATION}")
inside_stock = f"/{wh['lot_stock_id'][0]}/" in loc["parent_path"]
print(f"{loc['complete_name']}: parent {loc['location_id']}, "
      f"{'INSIDE WH/Stock (move it out)' if inside_stock else 'outside WH/Stock: OK'}")

print("\nDone." if APPLY else "\nDry run only: check the records above, then rerun with --apply.")

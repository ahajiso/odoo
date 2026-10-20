"""Open the existing stock categories to governed product requests.

Run only through ``run_activation.sh``.  The default is a dry run; the wrapper sets
CATALOGUE_STOCK_APPLY=1 for the committed run.  The script is deliberately limited to
artdubati_test and uses the imported external IDs instead of names or guessed IDs.

Test accounting choice (owner request, 20/10/2026): AVCO and automated valuation.
Construction materials use 601000 / 311000 / 603100.  Consumables use their existing
602xxx purchase account / 321000 / 603200. Small durable tools are expensed immediately
on 606300 with manual valuation. The two balance accounts are created only when their
code is absent; an existing account is reused only if it is the single current-asset
account of the company.  All choices remain category configuration and must be reviewed
by the accountant before production.
"""
import os


APPLY = os.environ.get("CATALOGUE_STOCK_APPLY") == "1"
SERVER_DB = "artdubati_test"
MODULE = "maintenance_shareholder_equipment"
EXPECTED_VERSION = "18.0.5.2.4"
XMLID_MODULE = "catalogue_stock"

env = env(context=dict(env.context, active_test=False, lang="en_US"))  # noqa: F821
errors = []
changes = []


def out(section, *parts):
    print(" | ".join([section] + [str(part) for part in parts]))


def error(message):
    errors.append(message)
    out("ERROR", message)


def changed(message):
    changes.append(message)
    out("CHANGE", ("APPLY " if APPLY else "WOULD ") + message)


def ref(xmlid):
    record = env.ref(xmlid, raise_if_not_found=False)
    if not record:
        error(f"external ID {xmlid} not found")
    return record


def ensure_xmlid(record, name):
    existing = env.ref(f"{XMLID_MODULE}.{name}", raise_if_not_found=False)
    if existing:
        if existing != record:
            error(f"{XMLID_MODULE}.{name} points to {existing.id}, expected {record.id}")
        return
    env["ir.model.data"].create({
        "module": XMLID_MODULE,
        "name": name,
        "model": record._name,
        "res_id": record.id,
        "noupdate": True,
    })


if env.cr.dbname == "artdubati":
    raise SystemExit("REFUSED: production database")
if env.cr.dbname != SERVER_DB:
    raise SystemExit(f"REFUSED: {env.cr.dbname} is not {SERVER_DB}")

module = env["ir.module.module"].search([("name", "=", MODULE)])
if len(module) != 1 or module.state != "installed" or module.latest_version != EXPECTED_VERSION:
    raise SystemExit(
        f"REFUSED: {MODULE} must be installed at {EXPECTED_VERSION}; found "
        f"{module.state if module else '-'} {module.latest_version if module else '-'}")

companies = env["res.company"].search([])
if len(companies) != 1:
    raise SystemExit(f"REFUSED: expected one company, found {len(companies)}")
company = companies
env = env(context=dict(env.context, allowed_company_ids=company.ids))
out("START", f"database={env.cr.dbname}", "APPLY" if APPLY else "DRY RUN")
out("COMPANY", company.id, company.name)

Account = env["account.account"]


def find_account(code, allowed_types):
    records = Account.search([("code", "=", code), ("company_ids", "in", company.id)])
    if len(records) != 1:
        error(f"account {code}: expected one, found {len(records)}")
        return Account
    if records.account_type not in allowed_types:
        error(f"account {code}: type {records.account_type}, expected {allowed_types}")
    out("ACCOUNT", code, records.name, records.account_type, f"id={records.id}")
    return records


expense_codes = ("601000", "602220", "602230", "603100", "603200", "606300")
accounts = {code: find_account(code, ("expense",)) for code in expense_codes}

# Stock balance accounts are the only new accounting records.  Existing codes are
# accepted only after their type and company have been checked above/below.
for key, code, name in (
        ("materials", "311000", "Raw materials and supplies stock (test)"),
        ("consumables", "321000", "Consumable materials stock (test)")):
    account = env.ref(f"{XMLID_MODULE}.account_stock_{key}", raise_if_not_found=False)
    by_code = Account.search([("code", "=", code), ("company_ids", "in", company.id)])
    if account and account not in by_code:
        error(f"{XMLID_MODULE}.account_stock_{key} does not point to company account {code}")
        continue
    if len(by_code) > 1:
        error(f"account {code}: expected at most one, found {len(by_code)}")
        continue
    if by_code and by_code.account_type != "asset_current":
        error(f"account {code}: type {by_code.account_type}, expected asset_current")
        continue
    if not account:
        account = by_code
    accounts[code] = account
    out("ACCOUNT", code, account.name if account else "to create", "asset_current",
        f"id={account.id if account else '-'}")

root_old = ref("__import__.cat_consumables")
root_materials = ref(f"{MODULE}.categ_root_materials")
root_consumables = ref(f"{MODULE}.categ_root_consumables")
root_small = ref(f"{MODULE}.categ_root_small_equipment")

# xmlid, inventory id, target root, expense, valuation, variation
specs = (
    ("cat_20", 12, root_consumables, "602230", "321000", "603200"),
    ("cat_21", 13, root_consumables, "602230", "321000", "603200"),
    ("cat_22", 14, root_materials, "601000", "311000", "603100"),
    ("cat_23", 15, root_consumables, "602230", "321000", "603200"),
    ("cat_24", 16, root_consumables, "602230", "321000", "603200"),
    ("cat_25", 17, root_consumables, "602220", "321000", "603200"),
)

categories = []
ready_categories = []
for xmlid, expected_id, target_root, expense, valuation, variation in specs:
    category = ref(f"__import__.{xmlid}")
    if not category:
        continue
    if category.id != expected_id:
        error(f"__import__.{xmlid}: id {category.id}, inventory expected {expected_id}")
    category = category.with_company(company)
    target = {
        "parent_id": target_root.id,
        "property_cost_method": "average",
        "property_valuation": "real_time",
        "property_account_expense_categ_id": accounts[expense].id,
        "property_stock_valuation_account_id": accounts[valuation].id if accounts[valuation] else False,
        "property_stock_account_input_categ_id": accounts[variation].id,
        "property_stock_account_output_categ_id": accounts[variation].id,
        "request_ready": True,
    }
    original = {
        "parent_id": root_old.id,
        "property_cost_method": "average",
        "property_valuation": "manual_periodic",
        "property_account_expense_categ_id": find_account("607000", ("expense",)).id,
        "property_stock_valuation_account_id": False,
        "property_stock_account_input_categ_id": False,
        "property_stock_account_output_categ_id": False,
        "request_ready": False,
    }

    def current(field):
        value = category[field]
        return value.id if hasattr(value, "_name") else value

    state = {field: current(field) for field in target}
    if state != target and state != original:
        error(f"{category.complete_name}: partial or unexpected configuration {state}")
    if state == original:
        if env["product.template"].with_context(active_test=False).search_count(
                [("categ_id", "child_of", category.id)]):
            error(f"{category.complete_name}: contains products; automatic valuation needs a separate migration")
        else:
            categories.append((category, target))
    ready_categories.append(category)
    out("CATEGORY", category.id, category.complete_name,
        "target=" + target_root.complete_name, f"expense={expense}",
        f"stock={valuation}", f"variation={variation}")

if errors:
    out("END", f"{len(errors)} error(s) before changes; rolled back")
    env.cr.rollback()
    raise SystemExit(1)

for key, code, name in (
        ("materials", "311000", "Raw materials and supplies stock (test)"),
        ("consumables", "321000", "Consumable materials stock (test)")):
    if not accounts[code]:
        accounts[code] = Account.create({
            "code": code,
            "name": name,
            "account_type": "asset_current",
            "company_ids": [(6, 0, company.ids)],
        })
        ensure_xmlid(accounts[code], f"account_stock_{key}")
        changed(f"create account {code} {name}")
    else:
        ensure_xmlid(accounts[code], f"account_stock_{key}")

# Replace the temporary False ids now that the balance accounts exist.
for category, target in categories:
    target = dict(target)
    target["property_stock_valuation_account_id"] = (
        accounts["311000"].id if target["parent_id"] == root_materials.id
        else accounts["321000"].id)
    category.write(target)
    changed(f"configure and open {category.complete_name}")

# These two leaves did not exist in the imported product-category tree but are needed
# by the same Leroy Merlin acceptance.  Their technical IDs make subsequent runs and
# deployment checks independent of translated/display names.
for xmlid, name, root, target in (
        ("categ_workwear", "Workwear & PPE", root_consumables, {
            "property_cost_method": "average",
            "property_valuation": "real_time",
            "property_account_expense_categ_id": accounts["602230"].id,
            "property_stock_valuation_account_id": accounts["321000"].id,
            "property_stock_account_input_categ_id": accounts["603200"].id,
            "property_stock_account_output_categ_id": accounts["603200"].id,
            "request_ready": True,
        }),
        ("categ_small_tools", "Tools & Workshop Equipment", root_small, {
            "property_cost_method": "average",
            "property_valuation": "manual_periodic",
            "property_account_expense_categ_id": accounts["606300"].id,
            "request_ready": True,
        })):
    category = env.ref(f"{XMLID_MODULE}.{xmlid}", raise_if_not_found=False)
    matches = env["product.category"].search([("name", "=", name), ("parent_id", "=", root.id)])
    if not category:
        if matches:
            error(f"{root.complete_name} / {name} exists without {XMLID_MODULE}.{xmlid}")
            continue
        category = env["product.category"].create(dict(target, name=name, parent_id=root.id))
        ensure_xmlid(category, xmlid)
        changed(f"create and open {category.complete_name}")
    else:
        category = category.with_company(company)
        expected = dict(target, parent_id=root.id)
        actual = {}
        for field in expected:
            value = category[field]
            actual[field] = value.id if hasattr(value, "_name") else value
        if actual != expected:
            error(f"{category.complete_name}: unexpected configuration {actual}")
    ready_categories.append(category)

for category in ready_categories:
    category = category.with_company(company)
    problems = category._request_problems(category._catalogue_family(), company)
    if problems:
        error(f"{category.complete_name}: {'; '.join(problems)}")
    out("READY", category.id, category.complete_name,
        f"family={category._catalogue_family()}", f"ready={category.request_ready}")

if errors:
    out("END", f"{len(errors)} error(s) after checks; rolled back")
    env.cr.rollback()
    raise SystemExit(1)

if APPLY:
    env.cr.commit()
    out("END", f"applied, {len(changes)} record(s) changed")
else:
    env.cr.rollback()
    out("END", f"dry run, {len(changes)} record(s) rolled back")

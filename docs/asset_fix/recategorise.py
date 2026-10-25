"""Move the DEXTER mitre saw and the BOSCH set to « Tools & Workshop Equipment ».

Owner's test choice C28 (25/10/2026): the DEXTER mitre saw (88.22 € excl. tax) is
expensed, not capitalised; the BOSCH set (23.12 € excl. tax, filed by mistake under
« TEST – Installations temporaires ») is filed with the tools. Target category:
All / Small Durable Equipment / Tools & Workshop Equipment (606300, manual valuation),
created by docs/catalogue_stock (external ID catalogue_stock.categ_small_tools).

Run BEFORE the bill of P01144 is created: a bill line takes its account from the
product category when it is created. Dry run by default; CATEGORY_FIX_APPLY=1 commits.
Refuses (ERROR, nothing written) on any unexpected state: database, module version,
names, current categories, an existing bill line or fixed asset, a valuation change.
Data from the read-only inventory of 25/10/2026 (docs/asset_fix/inventory.py).
"""
import os

APPLY = os.environ.get("CATEGORY_FIX_APPLY") == "1"
SERVER_DB = "artdubati_test"
MODULE = "maintenance_shareholder_equipment"
EXPECTED_VERSION = "18.0.5.2.6"
TARGET_XMLID = "catalogue_stock.categ_small_tools"
TARGET_NAME = "All / Small Durable Equipment / Tools & Workshop Equipment"
# template id: (exact name, current category id, equipment id, serial number)
ITEMS = {
    2889: ("DEXTER mitre saw", 634, 2180, "55669982"),
    3202: ("BOSCH set, 68 piece", 869, 2181, "998877"),
}
EXPECTED_CHANGES = len(ITEMS)

env = env(context=dict(env.context, active_test=False, lang="en_US"))  # noqa: F821
errors, changes = [], []


def out(section, *parts):
    print(" | ".join([section] + [str(p) for p in parts]))


def error(message):
    errors.append(message)
    out("ERROR", message)


if env.cr.dbname != SERVER_DB:
    raise SystemExit(f"REFUSED: {env.cr.dbname} is not {SERVER_DB}")
module = env["ir.module.module"].search([("name", "=", MODULE)])
if module.state != "installed" or module.latest_version != EXPECTED_VERSION:
    raise SystemExit(f"REFUSED: {MODULE} must be installed at {EXPECTED_VERSION}, "
                     f"found {module.state} {module.latest_version}")
company = env["res.company"].search([])
if len(company) != 1:
    raise SystemExit(f"REFUSED: expected one company, found {len(company)}")
env = env(context=dict(env.context, allowed_company_ids=company.ids))
out("START", f"database={env.cr.dbname}", "APPLY" if APPLY else "DRY RUN")

target = env.ref(TARGET_XMLID, raise_if_not_found=False)
if not target:
    raise SystemExit(f"REFUSED: {TARGET_XMLID} not found")
target = target.with_company(company)
out("TARGET", target.id, target.complete_name, f"family={target._catalogue_family()}",
    f"valuation={target.property_valuation}",
    f"expense={target.property_account_expense_categ_id.code}",
    f"ready={target.request_ready}")
if (target.complete_name != TARGET_NAME or target._catalogue_family() != "durable_equipment"
        or not target._is_small_equipment() or target.is_fixed_asset_stock
        or target.property_valuation != "manual_periodic"
        or target.property_account_expense_categ_id.code != "606300"
        or target.property_account_expense_categ_id.asset_profile_id):
    error("the target category is not the expected expensed small-equipment category")

Template = env["product.template"]
Equipment = env["maintenance.equipment"]
todo = []
for tmpl_id, (name, current_id, equipment_id, serial) in ITEMS.items():
    tmpl = Template.browse(tmpl_id).exists().with_company(company)
    if not tmpl:
        error(f"product template {tmpl_id} not found")
        continue
    equipment = Equipment.browse(equipment_id).exists()
    out("ITEM", tmpl.id, tmpl.name, f"category={tmpl.categ_id.id} {tmpl.categ_id.complete_name}",
        f"equipment={equipment.id} {equipment.name}", f"serial={equipment.stock_lot_id.name}",
        f"asset={equipment.asset_id.id or '-'}")
    if tmpl.name != name:
        error(f"template {tmpl_id}: name « {tmpl.name} », expected « {name} »")
    if not equipment or equipment.stock_lot_id.name != serial \
            or equipment.product_id.product_tmpl_id != tmpl:
        error(f"equipment {equipment_id}: not the {name} with serial {serial}")
    if equipment.asset_id:
        error(f"{name}: equipment already has a fixed asset")
    bill_lines = env["account.move.line"].search([
        ("product_id", "in", tmpl.product_variant_ids.ids),
        ("move_id.move_type", "in", ("in_invoice", "in_refund")),
        ("move_id.state", "!=", "cancel")])
    if bill_lines:
        error(f"{name}: supplier bill lines exist ({', '.join(bill_lines.move_id.mapped('display_name'))}); "
              "the category must change before the bill is created")
    if tmpl.categ_id == target:
        out("SKIP", name, "already in the target category")
        continue
    if tmpl.categ_id.id != current_id:
        error(f"{name}: category {tmpl.categ_id.id}, expected {current_id} or the target")
        continue
    if tmpl.categ_id.with_company(company).property_valuation != target.property_valuation:
        error(f"{name}: valuation would change; not handled by this script")
    todo.append((tmpl, equipment))

if errors:
    env.cr.rollback()
    out("END", f"{len(errors)} error(s); nothing written")
    raise SystemExit(1)

for tmpl, equipment in todo:
    old = tmpl.categ_id.complete_name
    tmpl.write({"categ_id": target.id})
    note = (f"Product category changed from « {old} » to « {target.complete_name} » "
            "(owner's test choice C28 of 25/10/2026, docs/asset_fix/recategorise.py): "
            "expensed on 606300, no fixed asset.")
    tmpl.message_post(body=note)
    equipment.message_post(body=note)
    changes.append(tmpl.name)
    out("CHANGE", ("APPLY " if APPLY else "WOULD ") + f"{tmpl.name}: {old} -> {target.complete_name}")

env.flush_all()
for tmpl, equipment in todo:
    if tmpl.categ_id != target or tmpl.categ_id._catalogue_family() != "durable_equipment":
        error(f"{tmpl.name}: category not applied")
rows = env["lartdubati.stock.monitor"].search([
    ("equipment_id", "in", [eq for _n, _c, eq, _s in ITEMS.values()])])
for row in rows:
    out("MONITOR", row.equipment_name, f"fixed_asset_missing={row.alert_asset_missing}",
        f"expensed={row.alert_no_asset}")
    if row.alert_asset_missing:
        error(f"{row.equipment_name}: still « Fixed Asset Missing »")

if errors or len(changes) not in (0, EXPECTED_CHANGES):
    env.cr.rollback()
    out("END", f"{len(errors)} error(s), {len(changes)} change(s); rolled back")
    raise SystemExit(1)
if APPLY:
    env.cr.commit()
    out("END", f"applied, {len(changes)} change(s) committed")
else:
    env.cr.rollback()
    out("END", f"dry run, {len(changes)} change(s) rolled back")

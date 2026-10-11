"""ROADMAP section 0, item 3: catalogue migration (docs/roadmap0/MIGRATION.md).

Run through the Odoo shell (superuser mode: the catalogue guards admit only it), right
after the update to maintenance_shareholder_equipment 18.0.5.0.0, by run_migration.sh:
    bash run_migration.sh            dry run: every change is made, checked by the
                                     model constraints, printed, then ROLLED BACK
    bash run_migration.sh --apply    the same, COMMITTED only if no ERROR line
A control dry run after --apply must print « 0 change(s) ».

Records are found by external ID, or by name and parent, never by a guessed id; each
one is printed with its id. On artdubati_test the ids must also match the inventory of
11/10/2026 (EXTRACT.md), otherwise ERROR and nothing is written. On any other database
(local rehearsal) only with ROADMAP0_REHEARSAL=1, ids not compared. Never on artdubati.

Changes (MIGRATION.md §2):
  M1 asset profile « Matériel informatique (test) » (copy of profile 4, account 218300,
     depreciation 281800, 3 years), set on account 218300;
  M2 product categories of the catalogue (fixed assets IT and plant & tools, services
     purchased, sales), accounts looked up by code, made « Available for Product
     Requests » (superuser, traced);
  M3 the 8 service products and the Mac Mini moved to them; the Mac Mini's default
     equipment category;
  M4 the four equipment moved to the business tree, two renamed;
  M5 duplicate, unused and TEST products archived when nothing depends on them, the
     TEST scaffold contract with its product;
  M6 old equipment categories (29 imported, `All`, `Fixed Assets`): archived while
     referenced, deleted otherwise (leaves first; a parent with children is kept);
  M7 contract tags.
Read only: what stays waiting for C24 / C25, the table saw's values (H3), the open
documents of maintainable products without a default equipment category, final checks.
"""
import os

APPLY = os.environ.get("ROADMAP0_APPLY") == "1"
REHEARSAL = os.environ.get("ROADMAP0_REHEARSAL") == "1"
SERVER_DB = "artdubati_test"
MODULE = "maintenance_shareholder_equipment"
XMLID_MODULE = "roadmap0"  # external IDs of the records created here (no module owns them)
EXPECTED_VERSION = "18.0.5.0.0"

env = env(context=dict(env.context, active_test=False, lang="en_US"))  # noqa: F821
DB = env.cr.dbname
CHECK_IDS = DB == SERVER_DB
errors, changes = [], []


def out(section, *parts):
    print(" | ".join([section] + [str(p) for p in parts]))


def error(message):
    errors.append(message)
    out("ERROR", message)


def change(section, message):
    changes.append(message)
    out(section, ("APPLY " if APPLY else "WOULD ") + message)


def expect_id(label, record, server_id):
    """Ids of the inventory, compared on artdubati_test only."""
    if CHECK_IDS and server_id and record and record.id != server_id:
        error(f"{label}: found id {record.id}, the inventory says {server_id}")


def ref(xmlid):
    record = env.ref(xmlid, raise_if_not_found=False)
    if not record:
        error(f"external ID {xmlid} not found")
    return record


def ensure_xmlid(record, name):
    env["ir.model.data"].create({"module": XMLID_MODULE, "name": name, "model": record._name,
                                 "res_id": record.id, "noupdate": True})


if DB == "artdubati":
    raise SystemExit("REFUSED: production database")
if DB != SERVER_DB and not REHEARSAL:
    raise SystemExit(f"REFUSED: {DB} is not {SERVER_DB} (set ROADMAP0_REHEARSAL=1 locally)")
out("START", f"database={DB}", "APPLY" if APPLY else "DRY RUN", f"compare ids={CHECK_IDS}")

# M0 preconditions -------------------------------------------------------------------
module = env["ir.module.module"].search([("name", "=", MODULE)])
if module.state != "installed" or module.latest_version != EXPECTED_VERSION:
    raise SystemExit(f"REFUSED: {MODULE} is {module.state} {module.latest_version}, "
                     f"expected installed {EXPECTED_VERSION} (update first)")
companies = env["res.company"].search([])
if len(companies) != 1:
    raise SystemExit(f"REFUSED: {len(companies)} companies, the migration expects one")
company = companies
env = env(context=dict(env.context, allowed_company_ids=company.ids))
out("COMPANY", company.id, company.name)
Account = env["account.account"]


def account(code, types):
    found = Account.search([("code", "=", code), ("company_ids", "in", company.id)])
    if len(found) != 1:
        error(f"account {code}: {len(found)} found")
        return Account
    if found.account_type not in types:
        error(f"account {code} {found.name}: type {found.account_type}, expected {types}")
    profile = found.asset_profile_id
    out("ACCOUNT", code, found.name, found.account_type, f"id={found.id}",
        f"asset profile={profile.name or '-'}")
    return found


FIXED, EXPENSE, INCOME = ("asset_fixed",), ("expense",), ("income", "income_other")
ACC = {
    "218300": account("218300", FIXED), "281800": account("281800", FIXED),
    "681120": account("681120", EXPENSE), "215400": account("215400", FIXED),
    "613500": account("613500", EXPENSE), "626000": account("626000", EXPENSE),
    "627800": account("627800", EXPENSE), "606400": account("606400", EXPENSE),
    "706000": account("706000", INCOME), "704000": account("704000", INCOME),
    "708300": account("708300", INCOME),
}

# the records of the inventory: (label, model, domain, server id)
Tmpl = env["product.template"]
ECat = env["maintenance.equipment.category"]
Equipment = env["maintenance.equipment"]


def find(label, model, domain, server_id, required=True):
    found = env[model].search(domain)
    if len(found) != 1:
        if required or found:
            error(f"{label}: {len(found)} record(s) for {domain}")
        return env[model]
    expect_id(label, found, server_id)
    out("FOUND", label, f"{model} id={found.id}", found.display_name)
    return found


categ_all = ref("product.product_category_all")
categ_old_fixed = find("product category All / Fixed Assets", "product.category",
                       [("name", "=", "Fixed Assets"), ("parent_id", "=", categ_all.id)], 19)
categ_overheads = find("product category Frais généraux", "product.category",
                       [("name", "=", "Frais généraux")], 18)
P = {}
for key, name, categ, server_id in [
    ("saw", "1800W corded table saw, 254mm blade, with wheeled stand", categ_all, 8),
    ("computer", "Computer", categ_all, 837),
    ("consulting", "Conseil / Prestation intellectuelle", categ_all, 7),
    ("green_cross", "Green cross laser", categ_all, 824),
    ("ranger_dup", "Laser rangefinder", categ_all, 823),
    ("rent_sold", "Location de matériel (facturée)", categ_all, 127),
    ("rent_paid", "Location de matériel (payée)", categ_all, 126),
    ("mac", "Mac Mini", categ_all, 843),
    ("works", "Main d'œuvre - Finition / Façade (horaire)", categ_all, 5),
    ("materials", "Matériaux de construction (finition/façade)", categ_all, 6),
    ("loan", "Prêt de matériel", categ_all, 125),
    ("test_compressor", "TEST Bought compressor", categ_all, 13),
    ("test_cement", "TEST Cement bag", categ_all, 10),
    ("test_scaffold", "TEST Scaffold rent", categ_all, 11),
    ("telecom", "Abonnement téléphonique", categ_overheads, 3),
    ("admin", "Frais administratifs", categ_overheads, 4),
    ("bank", "Frais bancaires", categ_overheads, 1),
    ("green360", "360° green laser", categ_old_fixed, 836),
    ("ranger", "Laser rangefinder", categ_old_fixed, 828),
]:
    # after --apply the moved products are found again by name alone (control run)
    domain = [("name", "=", name)]
    if Tmpl.search_count(domain) > 1:
        domain.append(("categ_id", "=", categ.id))
    P[key] = find(f"product {key}", "product.template", domain, server_id)

E = {}
for key, names, server_id in [
    ("saw", ("1800W corded table saw – 1234", "Scie sur table – 1234"), 484),
    ("green360", ("360° green laser",), 869),
    ("ranger", ("Laser rangefinder",), 870),
    ("mac", ("Device 1", "Mac Mini – 877790"), 871),
]:
    E[key] = find(f"equipment {key}", "maintenance.equipment", [("name", "in", names)], server_id)

ecat_auto_all = find("equipment category All (automatic)", "maintenance.equipment.category",
                     [("name", "=", "All"), ("product_category_id", "=", categ_all.id)], 89)
# after --apply (control run) the unreferenced old category is gone
MIGRATED = bool(env.ref(f"{XMLID_MODULE}.asset_profile_it", raise_if_not_found=False))
out("STATE", "already migrated (control run)" if MIGRATED else "not migrated yet")
ecat_auto_fixed = find("equipment category Fixed Assets (automatic)",
                       "maintenance.equipment.category",
                       [("name", "=", "Fixed Assets"), ("product_category_id", "=", categ_old_fixed.id)],
                       481, required=not MIGRATED)
profile_tools = find("asset profile Matériel et outillage (test)", "account.asset.profile",
                     [("name", "=", "Matériel et outillage (test)")], 4)
if errors:
    out("END", f"{len(errors)} error(s) before any change, nothing written")
    env.cr.rollback()
    raise SystemExit(1)

# M1 asset profile for IT ------------------------------------------------------------
Profile = env["account.asset.profile"]
IT_PROFILE = {"name": "Matériel informatique (test)", "account_asset_id": ACC["218300"].id,
              "account_depreciation_id": ACC["281800"].id,
              "account_expense_depreciation_id": ACC["681120"].id, "method": "linear",
              "method_number": 3, "method_period": "year", "method_time": "year",
              "asset_product_item": True, "company_id": company.id}
profile_it = env.ref(f"{XMLID_MODULE}.asset_profile_it", raise_if_not_found=False)
if not profile_it:
    if Profile.search_count([("name", "=", IT_PROFILE["name"])]):
        error("a profile « Matériel informatique (test) » exists without the external ID "
              f"{XMLID_MODULE}.asset_profile_it: to look at before the migration")
    else:
        # copy of the tools profile: same journal and options, IT accounts and 3 years
        profile_it = profile_tools.copy(IT_PROFILE)
        ensure_xmlid(profile_it, "asset_profile_it")
        change("M1", f"create asset profile asset_profile_it {profile_it.name} id={profile_it.id} "
               f"(218300 / 281800 / 681120, linear, 3 years, one asset per item, "
               f"journal {profile_it.journal_id.name})")
if profile_it:
    for name, value in IT_PROFILE.items():
        current = profile_it[name]
        current = current.id if hasattr(current, "_name") else current
        if current != value:
            error(f"asset profile {profile_it.name}: {name} is {current}, expected {value}")
    if ACC["218300"].asset_profile_id == profile_it and "asset_profile_it" in str(changes):
        # account_asset_management sets the profile on its asset account when the
        # profile is created and the account has none (account.asset.profile.create)
        change("M1", "account 218300 carries the profile (set by account_asset_management "
               "at the profile's creation)")
    elif ACC["218300"].asset_profile_id != profile_it:
        if ACC["218300"].asset_profile_id:
            error(f"account 218300 already has the profile {ACC['218300'].asset_profile_id.name}")
        else:
            ACC["218300"].asset_profile_id = profile_it
            change("M1", f"set asset profile {profile_it.name} on account 218300")

# M2 product categories --------------------------------------------------------------
Categ = env["product.category"]
CATEGORIES = [
    # external ID, parent root, name, expense, income, fixed asset (manual valuation)
    ("categ_fixed_it", "categ_root_fixed_assets", "IT Equipment", "218300", None, True),
    ("categ_fixed_plant", "categ_root_fixed_assets", "Plant & Tools", "215400", None, True),
    ("categ_svc_rentals", "categ_root_services_purchased", "Equipment Rentals & Loans",
     "613500", None, False),
    ("categ_svc_telecom", "categ_root_services_purchased", "Telecom & Internet", "626000",
     None, False),
    ("categ_svc_bank", "categ_root_services_purchased", "Bank Services", "627800", None, False),
    ("categ_svc_admin", "categ_root_services_purchased", "Administrative Supplies & Fees",
     "606400", None, False),
    ("categ_sale_consulting", "categ_root_sales", "Consulting", None, "706000", False),
    ("categ_sale_works", "categ_root_sales", "Works", None, "704000", False),
    ("categ_sale_rentals", "categ_root_sales", "Equipment Rentals", None, "708300", False),
]
C = {}
for xml, root, name, expense, income, fixed in CATEGORIES:
    parent = ref(f"{MODULE}.{root}")
    categ = env.ref(f"{XMLID_MODULE}.{xml}", raise_if_not_found=False)
    vals = {}
    if fixed:
        vals.update(is_fixed_asset_stock=True, property_cost_method="average",
                    property_valuation="manual_periodic")
    if expense:
        vals["property_account_expense_categ_id"] = ACC[expense].id
    if income:
        vals["property_account_income_categ_id"] = ACC[income].id
    if not categ:
        if Categ.search_count([("name", "=", name), ("parent_id", "=", parent.id)]):
            error(f"category {parent.name} / {name} exists without the external ID "
                  f"{XMLID_MODULE}.{xml}: to look at before the migration")
            continue
        categ = Categ.create(dict(vals, name=name, parent_id=parent.id))
        ensure_xmlid(categ, xml)
        change("M2", f"create product category {categ.complete_name} id={categ.id}")
    for field, value in vals.items():
        current = categ[field]
        current = current.id if hasattr(current, "_name") else current
        if current != value:
            error(f"category {categ.complete_name}: {field} is {current}, expected {value}")
    if not categ.request_ready:
        categ.request_ready = True
        change("M2", f"make {categ.complete_name} available for product requests "
               f"(superuser, traced: {categ.request_ready_user_id.name}, {categ.request_ready_date})")
    tmpl = Tmpl
    out("CATEG", categ.complete_name, f"id={categ.id}",
        f"family={categ._catalogue_family()}",
        f"expense={tmpl._catalogue_category_account(categ, 'property_account_expense_categ_id').code or '-'}",
        f"income={tmpl._catalogue_category_account(categ, 'property_account_income_categ_id').code or '-'}",
        f"cost={categ.property_cost_method}", f"valuation={categ.property_valuation}",
        f"fixed asset flag={categ.is_fixed_asset_stock}")
    C[xml] = categ

# M3 products moved now (services and the Mac Mini) ----------------------------------
MOVES = [
    ("consulting", "categ_sale_consulting", None),
    ("works", "categ_sale_works", None),
    ("rent_sold", "categ_sale_rentals", None),
    ("rent_paid", "categ_svc_rentals", None),
    ("loan", "categ_svc_rentals", None),
    ("telecom", "categ_svc_telecom", None),
    ("admin", "categ_svc_admin", None),
    ("bank", "categ_svc_bank", None),
    ("mac", "categ_fixed_it", f"{MODULE}.ecat_it_computers"),
]
for key, xml, ecat_xmlid in MOVES:
    product, categ = P[key], C.get(xml)
    if not (product and categ):
        continue
    vals = {}
    if product.categ_id != categ:
        vals["categ_id"] = categ.id
    if ecat_xmlid and product.equipment_category_id != ref(ecat_xmlid):
        vals["equipment_category_id"] = ref(ecat_xmlid).id
    if vals:
        before = (product.categ_id.complete_name, product.equipment_category_id.complete_name)
        quantity = product.qty_available if product.is_storable else None
        product.write(vals)
        change("M3", f"product {product.display_name} id={product.id}: category {before[0]} -> "
               f"{product.categ_id.complete_name}"
               + (f", default equipment category {before[1] or '-'} -> "
                  f"{product.equipment_category_id.complete_name}" if ecat_xmlid else "")
               + (f" (stock {quantity}: emptied and replenished by Odoo at the cost of "
                  f"{product.standard_price}, manual valuation: no journal entry)"
                  if quantity else ""))
    problems = product._family_problems(product.categ_id._catalogue_family())
    if problems:
        error(f"product {product.display_name}: {' '.join(problems)}")
    for field in ("property_account_income_id", "property_account_expense_id"):
        own = product[field]
        categ_field = field.replace("_id", "_categ_id")
        categ_account = Tmpl._catalogue_category_account(product.categ_id, categ_field)
        if own and own != categ_account:
            out("NOTE", f"product {product.display_name} keeps its own {field} {own.code} "
                f"(category: {categ_account.code or '-'})")

# M4 equipment -----------------------------------------------------------------------
EQUIPMENT = [
    ("saw", f"{MODULE}.ecat_workshop_wood", "Scie sur table – 1234"),
    ("green360", f"{MODULE}.ecat_measuring", None),
    ("ranger", f"{MODULE}.ecat_measuring", None),
    ("mac", f"{MODULE}.ecat_it_computers", "Mac Mini – 877790"),
]
LANGS = env["res.lang"].search([("active", "=", True)]).mapped("code")
out("LANGS", ", ".join(LANGS))
for key, ecat_xmlid, new_name in EQUIPMENT:
    equipment, category = E[key], ref(ecat_xmlid)
    if not (equipment and category):
        continue
    before = f"{equipment.name} [{equipment.category_id.complete_name}]"
    done = []
    if equipment.category_id != category:
        equipment.category_id = category
        done.append(f"category -> {category.complete_name}")
    # the equipment name is translatable: the same name in every active language,
    # otherwise a French or Persian user keeps reading the old one
    for lang in LANGS if new_name else ():
        if equipment.with_context(lang=lang).name != new_name:
            equipment.with_context(lang=lang).name = new_name
            done.append(f"name ({lang}) -> {new_name}")
    if done:
        change("M4", f"equipment id={equipment.id} {before}: {'; '.join(done)}")

# M5 archiving after dependency checks -----------------------------------------------
Contract = env["contract.contract"]
scaffold_contract = find("contract TEST Scaffold rental", "contract.contract",
                         [("name", "=", "TEST Scaffold rental")], None, required=False)


def product_dependencies(tmpl, allowed_contracts=Contract):
    variants = tmpl.product_variant_ids
    deps = []
    quants = env["stock.quant"].search([("product_id", "in", variants.ids),
                                        ("location_id.usage", "=", "internal"),
                                        ("quantity", "!=", 0)])
    if quants:
        deps.append(f"stock {sum(quants.mapped('quantity'))}")
    moves = env["stock.move"].search_count([("product_id", "in", variants.ids),
                                            ("state", "not in", ("done", "cancel"))])
    if moves:
        deps.append(f"{moves} open stock move(s)")
    if "purchase.order.line" in env:
        lines = env["purchase.order.line"].search([("product_id", "in", variants.ids),
                                                   ("state", "!=", "cancel")])
        open_lines = lines.filtered(lambda ln: ln.state in ("draft", "sent", "to approve")
                                    or ln.qty_received != ln.product_qty
                                    or ln.qty_invoiced != ln.product_qty)
        if open_lines:
            deps.append(f"open purchase lines {open_lines.order_id.mapped('name')}")
    if "sale.order.line" in env:
        lines = env["sale.order.line"].search([("product_id", "in", variants.ids),
                                               ("state", "!=", "cancel")])
        open_lines = lines.filtered(lambda ln: ln.state == "draft"
                                    or ln.qty_delivered != ln.product_uom_qty
                                    or ln.qty_invoiced != ln.product_uom_qty)
        if open_lines:
            deps.append(f"open sale lines {open_lines.order_id.mapped('name')}")
    contract_lines = env["contract.line"].search([("product_id", "in", variants.ids),
                                                  ("contract_id.active", "=", True),
                                                  ("contract_id", "not in", allowed_contracts.ids)])
    if contract_lines:
        deps.append(f"contracts {contract_lines.contract_id.mapped('name')}")
    equipment = Equipment.search([("product_id", "in", variants.ids), ("active", "=", True)])
    if equipment:
        deps.append(f"equipment {equipment.ids}")
    draft = env["account.move.line"].search([("product_id", "in", variants.ids),
                                             ("parent_state", "=", "draft")])
    if draft:
        deps.append(f"draft entries {draft.move_id.mapped('name')}")
    operations = env["equipment.operation.line"].search([
        ("product_id", "in", variants.ids),
        ("operation_id.state", "not in", ("done", "cancel"))])
    if operations:
        deps.append(f"open operations {operations.operation_id.mapped('name')}")
    return deps


def draft_contract_invoices(contract):
    return env["account.move.line"].search([("contract_line_id", "in", contract.contract_line_ids.ids),
                                            ("parent_state", "=", "draft")]).move_id


for key, reason in [("ranger_dup", "duplicate of Laser rangefinder 828, no equipment"),
                    ("computer", "unused (D5)"),
                    ("test_compressor", "TEST product"),
                    ("test_scaffold", "TEST product, with its contract TEST Scaffold rental")]:
    product = P[key]
    if not product or not product.active:
        continue
    allowed = scaffold_contract if key == "test_scaffold" else Contract
    deps = product_dependencies(product, allowed)
    if key == "test_scaffold" and scaffold_contract:
        drafts = draft_contract_invoices(scaffold_contract)
        if drafts:
            deps.append(f"draft bills of its contract {drafts.mapped('name')}")
    if deps:
        out("KEPT", f"product {product.display_name} id={product.id} not archived: "
            + "; ".join(deps))
        continue
    if key == "test_scaffold" and scaffold_contract.active:
        scaffold_contract.active = False
        change("M5", f"archive contract {scaffold_contract.name} id={scaffold_contract.id}")
    product.active = False
    change("M5", f"archive product {product.display_name} id={product.id} ({reason})")

# M6 old equipment categories --------------------------------------------------------
imported = env["ir.model.data"].search([("module", "=", "__import__"),
                                        ("model", "=", "maintenance.equipment.category")])
old = ECat.browse(imported.mapped("res_id")).exists() | ecat_auto_all | ecat_auto_fixed
# first run: the 29 of the inventory; after --apply only the archived ones remain
if CHECK_IDS and len(imported) != 29 and ECat.browse(imported.mapped("res_id")).filtered("active"):
    error(f"{len(imported)} imported equipment categories, the inventory says 29")
module_ecats = ECat.browse(env["ir.model.data"].search([
    ("module", "=", MODULE), ("model", "=", "maintenance.equipment.category")]).mapped("res_id"))
for other in ECat.search([("id", "not in", (old | module_ecats).ids)]):
    error(f"equipment category {other.complete_name} id={other.id}: neither the module's tree "
          "nor an old category of the inventory")
ref_fields = env["ir.model.fields"].search([("relation", "=", "maintenance.equipment.category"),
                                            ("ttype", "in", ("many2one", "many2many")),
                                            ("store", "=", True)])


def references(category):
    found = []
    for field in ref_fields:
        Model = env.get(field.model)
        if Model is None or Model._transient or Model._abstract:
            continue
        if field.model == "maintenance.equipment.category" and field.name == "parent_id":
            continue  # children are handled by the order below
        count = Model.with_context(active_test=False).search_count([(field.name, "in", category.ids)])
        if count:
            found.append(f"{field.model}.{field.name}: {count}")
    if ECat.search_count([("parent_id", "=", category.id)]):
        found.append("child categories")
    return found


for default in env["ir.default"].search([("field_id", "in", ref_fields.ids)]):
    out("DEFAULT", f"{default.field_id.model}.{default.field_id.name} = {default.json_value} "
        f"(user {default.user_id.name or '-'}, company {default.company_id.name or '-'})")
for saved in env["ir.filters"].search([("model_id", "in", ref_fields.mapped("model"))]):
    if "categ" in (saved.domain or "") or "categ" in (saved.context or ""):
        out("FILTER", f"{saved.name} id={saved.id} on {saved.model_id}: {saved.domain} {saved.context}")

CODE_MAP = {  # old imported code -> category of the business tree (NOMENCLATURE.md)
    "01": "ecat_tools_cordless", "02": "ecat_tools_corded", "03": "ecat_tools_hand",
    "04": None, "05": None, "08": None, "09": None, "10": None,
    "06": "ecat_workshop_wood", "07": "ecat_workshop_metal", "11": "ecat_measuring",
    "12": "ecat_site_machinery", "13": "ecat_cleaning", "14": "ecat_safety",
    "15": "ecat_handling", "16": "ecat_height", "17": "ecat_workshop_other",
    "18": "ecat_it", "19": "ecat_tools_batteries", "26": "ecat_site_machinery",
    "27": "ecat_vehicles", "28": "ecat_formwork",
}
# leaves first: a category whose children are gone becomes a leaf
for category in old.sorted(lambda c: -len((c.parent_path or "").split("/"))):
    xmlids = env["ir.model.data"].search([("model", "=", category._name),
                                          ("res_id", "=", category.id)])
    names = ", ".join(f"{x.module}.{x.name}" for x in xmlids) or "no external ID"
    code = category.name[:2] if category.name[:2].isdigit() else None
    target = CODE_MAP.get(code) if code else None
    mapping = (f"code {code} -> {ref(f'{MODULE}.{target}').complete_name}" if target
               else f"code {code} -> trade, by physical nature" if code else "no code")
    refs = references(category)
    if refs:
        if category.active:
            category.active = False
            change("M6", f"archive equipment category {category.complete_name} id={category.id} "
                   f"({names}; referenced by {', '.join(refs)}; {mapping})")
    else:
        label = f"{category.complete_name} id={category.id} ({names}; {mapping})"
        category.unlink()
        change("M6", f"delete equipment category {label}")

# M7 contract tags -------------------------------------------------------------------
Tag = env["contract.tag"]
for name in ("Insurance", "Maintenance", "Rental", "Leasing", "Telecom & Internet",
             "Software & SaaS", "Energy & Charges", "Other Subscription"):
    if not Tag.search_count([("name", "=", name), ("company_id", "in", (company.id, False))]):
        tag = Tag.create({"name": name, "company_id": company.id})
        change("M7", f"create contract tag {name} id={tag.id}")

env.flush_all()

# R read only: what waits, H3, open documents, final checks --------------------------
for key, reason in [("saw", "small durable equipment, C24"),
                    ("green_cross", "D5: serial equipment after C24 / C25, or deleted"),
                    ("green360", "D3: rented laser, controlled operation after C24 / C25"),
                    ("ranger", "D3: borrowed laser, controlled operation after C24 / C25"),
                    ("test_cement", "kept until the consignment plan (§5)"),
                    ("materials", "generic goods sold, goods family after C25")]:
    product = P[key]
    if product:
        out("WAITING", product.display_name, f"id={product.id}",
            f"category={product.categ_id.complete_name}",
            f"default equipment category={product.equipment_category_id.complete_name or '-'}",
            reason)

saw = P["saw"]
if saw:
    out("H3", f"table saw standard price {saw.standard_price}, cost method "
        f"{saw.categ_id.property_cost_method}")
    for layer in env["stock.valuation.layer"].search([("product_id", "in", saw.product_variant_ids.ids)],
                                                     order="id"):
        out("H3", f"valuation layer {layer.create_date:%Y-%m-%d %H:%M} {layer.description or '-'} "
            f"qty={layer.quantity} unit={layer.unit_cost} value={layer.value} "
            f"by {layer.create_uid.name}")
    for line in env["account.move.line"].search([("product_id", "in", saw.product_variant_ids.ids),
                                                 ("move_id.move_type", "in", ("in_invoice", "in_refund"))]):
        out("H3", f"bill line {line.move_id.name} {line.parent_state} qty={line.quantity} "
            f"price={line.price_unit} account={line.account_id.code} "
            f"equipment category={line.equipment_category_id.complete_name or '-'}")

maintainable = Tmpl.search([("maintenance_ok", "=", True), ("active", "=", True),
                            ("equipment_category_id", "=", False)])
variants = maintainable.product_variant_ids
for line in env["equipment.operation.line"].search([("product_id", "in", variants.ids),
                                                    ("operation_id.state", "not in", ("done", "cancel"))]):
    out("BLOCKED", f"operation {line.operation_id.name} ({line.operation_id.state}): "
        f"{line.product_id.display_name} has no default equipment category")
for line in env["account.move.line"].search([("product_id", "in", variants.ids),
                                             ("parent_state", "=", "draft"),
                                             ("equipment_category_id", "=", False),
                                             ("move_id.move_type", "in", ("in_invoice", "in_refund"))]):
    out("BLOCKED", f"draft bill {line.move_id.name}: {line.product_id.display_name} has no "
        "default equipment category")

to_classify = ref(f"{MODULE}.ecat_to_classify")
for equipment in Equipment.search([("active", "=", True)]):
    category = equipment.category_id
    if not category or category == to_classify or not (category.active and category.assignable):
        error(f"equipment {equipment.name} id={equipment.id} in {category.complete_name or 'no category'}")
for product in Tmpl.search([("equipment_category_id", "!=", False)]):
    if not (product.equipment_category_id.active and product.equipment_category_id.assignable):
        error(f"product {product.display_name}: default equipment category "
              f"{product.equipment_category_id.complete_name} not usable")
for categ in Categ.search([("request_ready", "=", True)]):
    out("READY", categ.complete_name, f"id={categ.id}", f"family={categ._catalogue_family()}",
        f"by {categ.request_ready_user_id.name} on {categ.request_ready_date}")
    if categ._catalogue_family() == "durable_equipment":
        problems = categ._request_problems("durable_equipment", company)
    elif categ._catalogue_family() == "service":
        sold = categ.parent_id == ref(f"{MODULE}.categ_root_sales")
        problems = categ._request_problems("service", company, purchase_ok=not sold, sale_ok=sold)
    else:
        problems = [f"family {categ._catalogue_family()} is not opened by this migration"]
    for problem in problems:
        error(f"category {categ.complete_name}: {problem}")

if errors:
    env.cr.rollback()
    out("END", f"{len(errors)} error(s), {len(changes)} change(s) rolled back, nothing written")
elif APPLY:
    env.cr.commit()
    out("END", f"applied, {len(changes)} change(s) committed")
else:
    env.cr.rollback()
    out("END", f"dry run, {len(changes)} change(s) rolled back")

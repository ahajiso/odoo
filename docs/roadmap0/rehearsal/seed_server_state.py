"""ROADMAP section 0, item 3: LOCAL rehearsal only. Rebuilds on a local copy of the
server's platform (code of main ae31573, maintenance_shareholder_equipment 18.0.4.0.1)
the records of artdubati_test that the migration reads (EXTRACT.md, complement of
11/10/2026): product categories, the 29 imported and the 2 automatic equipment
categories, the 19 products, the four equipment, the stock, the posted bill of the
table saw, the four contract lines. Ids differ from the server's: the migration finds
its records by name and external ID and only compares ids on artdubati_test.

Not reproduced (not read by the migration): P00381 and its receipt, the equipment
operations, the TBER / TIST stocks and their addresses.

Refuses any database except the rehearsal ones. Run with the OLD code:
    odoo shell -c odoo_p4main.conf -d r0mig --no-http < seed_server_state.py
"""
import datetime

assert env.cr.dbname.startswith("r0"), "local rehearsal databases only (r0*)"  # noqa: F821
env = env(context=dict(env.context, tracking_disable=True))  # noqa: F821
company = env.company
company.name = "Docteur Bain"
Account = env["account.account"]


def account(code):
    acc = Account.search([("code", "=", code), ("company_ids", "in", company.id)])
    assert len(acc) == 1, code
    return acc


def xmlid(record, module, name):
    env["ir.model.data"].create({"module": module, "name": name, "model": record._name,
                                 "res_id": record.id, "noupdate": True})


# product categories --------------------------------------------------------------
Categ = env["product.category"]
all_categ = env.ref("product.product_category_all")
all_categ.write({"property_cost_method": "standard", "property_valuation": "manual_periodic",
                 "property_account_expense_categ_id": account("607000").id,
                 "property_account_income_categ_id": account("707000").id})
expenses = env.ref("product.cat_expense")
consumables = Categ.create({"name": "Consumables & Accessories", "parent_id": expenses.id,
                            "property_cost_method": "average"})
xmlid(consumables, "__import__", "cat_consumables")
for code, name in [("20", "Tool Accessories"), ("21", "Tool Consumables"),
                   ("22", "Construction Consumables"), ("23", "Electrical Consumables"),
                   ("24", "Plumbing Consumables"), ("25", "Spare Parts")]:
    xmlid(Categ.create({"name": f"{code} {name}", "parent_id": consumables.id,
                        "property_cost_method": "average"}), "__import__", f"cat_{code}")
overheads = Categ.create({"name": "Frais généraux", "parent_id": expenses.id})
journal = env["account.journal"].search([("type", "=", "general"),
                                         ("company_id", "=", company.id)], limit=1)
profile = env["account.asset.profile"].create({
    "name": "Matériel et outillage (test)", "company_id": company.id,
    "account_asset_id": account("215400").id, "account_depreciation_id": account("281500").id,
    "account_expense_depreciation_id": account("681120").id, "journal_id": journal.id,
    "method": "linear", "method_number": 5, "method_period": "year", "method_time": "year",
    "asset_product_item": True,
})
account("215400").asset_profile_id = profile
fixed = Categ.create({"name": "Fixed Assets", "parent_id": all_categ.id,
                      "property_cost_method": "average", "property_valuation": "manual_periodic",
                      "property_account_expense_categ_id": account("215400").id,
                      "is_fixed_asset_stock": True})

# equipment categories ------------------------------------------------------------
ECat = env["maintenance.equipment.category"]
TREE = [
    ("cat_actif", None, "Assets & Equipment"),
    ("cat_measure", "cat_actif", "Inspection & Measurement"),
    ("cat_11", "cat_measure", "11 Measuring Equipment"),
    ("cat_it_office", "cat_actif", "IT & Office Equipment"),
    ("cat_18", "cat_it_office", "18 Electronic and IT Equipment"),
    ("cat_logistics", "cat_actif", "Logistics Safety & Access"),
    ("cat_14", "cat_logistics", "14 Safety and Personal Protective Equipment"),
    ("cat_15", "cat_logistics", "15 Material Handling Equipment"),
    ("cat_16", "cat_logistics", "16 Ladders Scaffolding and Work at Height"),
    ("cat_power_tools", "cat_actif", "Power & Workshop Tools"),
    ("cat_01", "cat_power_tools", "01 Cordless Tools"),
    ("cat_02", "cat_power_tools", "02 Corded Power Tools"),
    ("cat_03", "cat_power_tools", "03 Hand Tools"),
    ("cat_06", "cat_power_tools", "06 Woodworking Equipment"),
    ("cat_07", "cat_power_tools", "07 Metalworking Equipment"),
    ("cat_17", "cat_power_tools", "17 Small Workshop Machinery"),
    ("cat_19", "cat_power_tools", "19 Batteries and Chargers"),
    ("cat_machinery", "cat_actif", "Site Machinery & Vehicles"),
    ("cat_26", "cat_machinery", "26 Site Machinery"),
    ("cat_27", "cat_machinery", "27 Vehicles"),
    ("cat_site_equip", "cat_actif", "Trade & Site Equipment"),
    ("cat_04", "cat_site_equip", "04 Electrical Equipment"),
    ("cat_05", "cat_site_equip", "05 Plumbing and MEP Equipment"),
    ("cat_08", "cat_site_equip", "08 Painting and Coating Equipment"),
    ("cat_09", "cat_site_equip", "09 Masonry and Tiling Equipment"),
    ("cat_10", "cat_site_equip", "10 Plastering and Drywall Equipment"),
    ("cat_12", "cat_site_equip", "12 Demolition Equipment"),
    ("cat_13", "cat_site_equip", "13 Workshop Cleaning Equipment"),
    ("cat_28", "cat_site_equip", "28 Formwork and Shoring Equipment"),
]
created = {}
for name, parent, label in TREE:
    created[name] = ECat.create({"name": label, "parent_id": parent and created[parent].id})
    xmlid(created[name], "__import__", name)
ecat_all = ECat.create({"name": "All", "product_category_id": all_categ.id})
ecat_fixed = ECat.create({"name": "Fixed Assets", "product_category_id": fixed.id})

# products ------------------------------------------------------------------------
Tmpl = env["product.template"]


HOOK_PRODUCTS = ("Main d'œuvre - Finition / Façade (horaire)",
                 "Matériaux de construction (finition/façade)",
                 "Conseil / Prestation intellectuelle")


def product(name, categ=all_categ, **vals):
    """Products 5 to 7 already exist (lartdubati_facturation's install hook, no
    external ID), as on the server: completed, never duplicated."""
    vals.setdefault("type", "consu")
    existing = Tmpl.search([("name", "=", name)]) if name in HOOK_PRODUCTS else Tmpl
    if existing:
        existing.write(dict(vals, categ_id=categ.id))
        return existing
    return Tmpl.create(dict(vals, name=name, categ_id=categ.id))


saw = product("1800W corded table saw, 254mm blade, with wheeled stand", is_storable=True,
              tracking="serial", maintenance_ok=True, standard_price=329)
product("Computer")
product("Conseil / Prestation intellectuelle", type="service",
        property_account_income_id=account("706000").id)
green = product("Green cross laser", is_storable=True, standard_price=79.99)
product("Laser rangefinder", is_storable=True)
product("Location de matériel (facturée)", type="service",
        property_account_income_id=account("708300").id)
rent_paid = product("Location de matériel (payée)", type="service",
                    property_account_expense_id=account("613500").id)
mac = product("Mac Mini", default_code="MM1220", is_storable=True, tracking="serial",
              maintenance_ok=True, standard_price=0)
product("Main d'œuvre - Finition / Façade (horaire)", type="service",
        property_account_income_id=account("704000").id)
product("Matériaux de construction (finition/façade)",
        property_account_income_id=account("707000").id)
loan = product("Prêt de matériel", type="service")
product("TEST Bought compressor", maintenance_ok=True)
cement = product("TEST Cement bag", is_storable=True, standard_price=8)
scaffold = product("TEST Scaffold rent", type="service")
product("Abonnement téléphonique", overheads, type="service",
        property_account_expense_id=account("626000").id)
product("Frais administratifs", overheads, type="service",
        property_account_expense_id=account("606400").id)
product("Frais bancaires", overheads, type="service",
        property_account_expense_id=account("627800").id)
green360 = product("360° green laser", fixed, default_code="00000002", maintenance_ok=True)
ranger = product("Laser rangefinder", fixed, default_code="00000001", maintenance_ok=True)

# stock (inventory adjustments, superuser; the phase 2 stock rule admits a
# maintainable product only through an operation: flag set back right after)
(saw | mac).maintenance_ok = False
stock = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1).lot_stock_id
Lot = env["stock.lot"]
saw_lot = Lot.create({"name": "1234", "product_id": saw.product_variant_id.id,
                      "company_id": company.id})
mac_lot = Lot.create({"name": "877790", "product_id": mac.product_variant_id.id,
                      "company_id": company.id})
for tmpl, qty, lot in [(saw, 1, saw_lot), (mac, 1, mac_lot), (green, 1, None), (cement, 46, None)]:
    env["stock.quant"].with_context(inventory_mode=True).create({
        "product_id": tmpl.product_variant_id.id, "location_id": stock.id,
        "inventory_quantity": qty, "lot_id": lot and lot.id,
    }).action_apply_inventory()
(saw | mac).maintenance_ok = True

# partners, equipment, bill, contracts --------------------------------------------
Partner = env["res.partner"]
manager = Partner.create({"name": "Manager"})
supplier = Partner.create({"name": "TEST Supplier (owner)"})
responsible = env["res.users"].search([("share", "=", False), ("id", ">", 2)], limit=1) or env.ref("base.user_admin")
Equipment = env["maintenance.equipment"]
common = {"warranty_status": "no_warranty", "insurance_status": "not_insured",
          "owner_user_id": responsible.id, "company_id": company.id}
eq_saw = Equipment.create(dict(common, name="1800W corded table saw – 1234",
                               category_id=ecat_all.id, product_id=saw.product_variant_id.id,
                               stock_lot_id=saw_lot.id))
eq_mac = Equipment.create(dict(common, name="Device 1", category_id=ecat_all.id,
                               product_id=mac.product_variant_id.id, stock_lot_id=mac_lot.id,
                               cost=1850, cost_known=True, cost_provisional=True,
                               cost_source="order", cost_reference="P00381",
                               cost_date=datetime.date(2026, 10, 10)))
third = dict(common, current_location_id=stock.id, owner_partner_id=manager.id,
             replacement_value=100, replacement_currency_id=company.currency_id.id,
             replacement_value_date=datetime.date(2026, 10, 10), category_id=ecat_fixed.id)
eq_green = Equipment.create(dict(third, name="360° green laser", ownership_status="rented",
                                 product_id=green360.product_variant_id.id))
eq_ranger = Equipment.create(dict(third, name="Laser rangefinder", ownership_status="borrowed",
                                  product_id=ranger.product_variant_id.id))
(eq_saw | eq_mac | eq_green | eq_ranger).write({"integration_state": "done"})

# the table saw's bill, posted on 607000; its line keeps the automatic category « All »
saw.maintenance_ok = False  # no equipment created by maintenance_account at posting
bill = env["account.move"].create({
    "move_type": "in_invoice", "partner_id": supplier.id, "invoice_date": "2026-10-09",
    "invoice_line_ids": [(0, 0, {"product_id": saw.product_variant_id.id, "quantity": 1,
                                 "price_unit": 15, "tax_ids": [(6, 0, [])]})],
})
bill.action_post()
saw.maintenance_ok = True
line = bill.invoice_line_ids
line.equipment_category_id = ecat_all
eq_saw.write({"move_line_id": line.id, "cost": 15, "cost_known": True,
              "cost_provisional": False, "cost_source": "bill", "cost_reference": bill.name,
              "cost_date": datetime.date(2026, 10, 9)})
line.equipment_ids = eq_saw

Contract = env["contract.contract"]


def contract(name, partner, product, price, start, equipment=None, nature=None):
    return Contract.create({
        "name": name, "partner_id": partner.id, "contract_type": "purchase",
        "line_recurrence": True, "company_id": company.id,
        "contract_line_ids": [(0, 0, {
            "product_id": product.product_variant_id.id, "name": product.name,
            "quantity": 1, "price_unit": price, "recurring_rule_type": "monthly",
            "recurring_interval": 1, "date_start": start,
            "equipment_id": equipment and equipment.id, "equipment_nature": nature})],
    })


contract("EQOP/2026/0738 – Manager", manager, loan, 0, "2026-10-10", eq_ranger, "loan")
contract("EQOP/2026/0739 – Manager", manager, rent_paid, 10, "2026-10-10", eq_green, "rental")
contract("TEST Cement rental", supplier, cement, 2, "2026-09-01")
contract("TEST Scaffold rental", supplier, scaffold, 250, "2026-09-01")
env.cr.commit()
print("SEED | done | equipment", (eq_saw | eq_mac | eq_green | eq_ranger).ids, "bill", bill.name)

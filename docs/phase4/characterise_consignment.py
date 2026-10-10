"""Phase 4, P4-1 step 1: characterisation of consigned consumables in standard Odoo 18
(docs/phase4/PLAN.md §5, report in docs/phase4/CHARACTERISATION.md).

Run with `odoo shell` on a local database, never on artdubati_test; everything is rolled
back at the end:
    odoo-bin shell -c odoo.conf -d <db> --no-http < characterise_consignment.py

Scenarios, each from a fresh savepoint (same starting stock: 10 owned bought at 5.00,
15 consigned by the consignor received through a standard receipt with an owner):
  S0 the consigned receipt itself;
  S1 consigned quant removed by an inventory adjustment (counted 0);
  S2 consigned goods returned to the consignor: a supplier return (outgoing transfer to
     Partners/Vendors carrying the owner), audit of dff33cb (the first version went to
     the customers location);
  S3 internal transfer on the same location with « Assign Owner » = the company;
  S4 purchase from the consignor (order, receipt, bill), then S1 on the consigned quant;
  S5 inventory adjustment adding 15 owned units (the « swap » done by hand).
For each: move lines (from, to, owner), quants, stock valuation layers, journal items.
"""
from odoo import Command, fields

out = []


def say(*args):
    out.append(" ".join(str(a) for a in args))


company = env.company
if not env["account.account"].search_count([("company_ids", "in", company.ids)]):
    company.country_id = env.ref("base.fr")
    env["account.chart.template"].try_loading("fr", company, install_demo=False)
env.user.groups_id |= (env.ref("stock.group_tracking_owner")
                       | env.ref("stock.group_stock_multi_locations"))
say("Odoo", env["ir.module.module"].search([("name", "=", "base")]).latest_version,
    "| modules:", ", ".join(sorted(env["ir.module.module"].search(
        [("state", "=", "installed"), ("name", "in", (
            "stock_account", "purchase_stock", "l10n_fr", "maintenance_shareholder_equipment",
            "lartdubati_investor_home"))]).mapped("name"))))

warehouse = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
stock = warehouse.lot_stock_id
supplier_loc = env.ref("stock.stock_location_suppliers")
customer_loc = env.ref("stock.stock_location_customers")
categ = env["product.category"].create({
    "name": "Consumables AVCO automated (charac)",
    "property_cost_method": "average", "property_valuation": "real_time",
})
product = env["product.product"].create({
    "name": "Cement bag (charac)", "type": "consu", "is_storable": True,
    "categ_id": categ.id, "standard_price": 5.0,
})
consignor = env["res.partner"].create({"name": "Consignor (charac)"})
vendor = env["res.partner"].create({"name": "Vendor (charac)"})


def picking(picking_type, src, dst, qty, partner=None, owner=None):
    vals = {
        "picking_type_id": picking_type.id, "location_id": src.id,
        "location_dest_id": dst.id, "partner_id": (partner or vendor).id,
        "move_ids": [Command.create({
            "name": product.name, "product_id": product.id, "product_uom_qty": qty,
            "product_uom": product.uom_id.id, "location_id": src.id,
            "location_dest_id": dst.id, "price_unit": product.standard_price})],
    }
    if owner:
        vals["owner_id"] = owner.id
    pick = env["stock.picking"].create(vals)
    pick.action_confirm()
    pick.action_assign()
    for move in pick.move_ids:
        move.quantity = qty
    pick.button_validate()
    return pick


def snapshot(title, since):
    env.flush_all()
    say("")
    say("##", title)
    for ml in env["stock.move.line"].search([("product_id", "=", product.id),
                                             ("id", ">", since["ml"])]):
        say(f"  move line: {ml.location_id.complete_name} -> {ml.location_dest_id.complete_name}"
            f" qty {ml.quantity} owner {ml.owner_id.name or '-'} state {ml.move_id.state}"
            f" [{ml.move_id.reference or ml.move_id.name}"
            f"{', inventory' if ml.move_id.is_inventory else ''}]")
    for q in env["stock.quant"].search([("product_id", "=", product.id),
                                        ("location_id.usage", "=", "internal")]):
        say(f"  quant: {q.location_id.complete_name} qty {q.quantity} "
            f"owner {q.owner_id.name or '-'}")
    for svl in env["stock.valuation.layer"].search([("product_id", "=", product.id),
                                                    ("id", ">", since["svl"])]):
        say(f"  valuation layer: qty {svl.quantity} value {svl.value} "
            f"unit {svl.unit_cost} ({svl.description})")
    for aml in env["account.move.line"].search([("product_id", "=", product.id),
                                                ("id", ">", since["aml"])]):
        say(f"  journal item: {aml.move_id.journal_id.code} {aml.account_id.code} "
            f"{aml.account_id.name} D {aml.debit} C {aml.credit} ({aml.move_id.state})")
    say(f"  product: qty_available {product.with_context(owner_id=False).qty_available} "
        f"average cost {product.standard_price}")


def marks():
    env.flush_all()
    return {
        "ml": max(env["stock.move.line"].search([]).ids or [0]),
        "svl": max(env["stock.valuation.layer"].search([]).ids or [0]),
        "aml": max(env["account.move.line"].search([]).ids or [0]),
    }


def run(title, fn):
    say("")
    say("=" * 78)
    sp = env.cr.savepoint()
    try:
        m = marks()
        fn()
        snapshot(title, m)
    except Exception as error:  # noqa: BLE001 - the refusal is the result
        say("")
        say("##", title)
        say(f"  REFUSED: {type(error).__name__}: {str(error).splitlines()[0][:300]}")
    finally:
        sp.close(rollback=True)
        env.invalidate_all()


# starting stock, kept for every scenario
m0 = marks()
ours = "maintenance_shareholder_equipment" in env.registry._init_modules
consigned_receipt = None
if not ours:
    picking(warehouse.in_type_id, supplier_loc, stock, 10)
    consigned_receipt = picking(warehouse.in_type_id, supplier_loc, stock, 15,
                                partner=consignor, owner=consignor)
    snapshot("S0 starting stock: 10 owned received at 5.00, then 15 received with "
             "« Assign Owner » = consignor", m0)
else:
    # with our modules a supplier receipt goes only through an equipment operation and a
    # consigned receipt is refused: the starting stock is written directly (test data)
    run("S0' standard consigned receipt with our modules", lambda: picking(
        warehouse.in_type_id, supplier_loc, stock, 15, partner=consignor, owner=consignor))
    Quant = env["stock.quant"]
    Quant._update_available_quantity(product, stock, 10)
    Quant._update_available_quantity(product, stock, 15, owner_id=consignor)
    snapshot("S0 starting stock written directly: 10 owned, 15 owned by the consignor", m0)


def s1():
    quant = env["stock.quant"].search([("product_id", "=", product.id),
                                       ("location_id", "=", stock.id),
                                       ("owner_id", "=", consignor.id)])
    quant.inventory_quantity = 0
    quant.action_apply_inventory()


def s2():
    picking(warehouse.out_type_id, stock, supplier_loc, 15, partner=consignor,
            owner=consignor)


def s2b():
    """The standard « Return » wizard on the consigned receipt."""
    wizard = env["stock.return.picking"].with_context(
        active_id=consigned_receipt.id, active_ids=consigned_receipt.ids,
        active_model="stock.picking").create({"picking_id": consigned_receipt.id})
    for line in wizard.product_return_moves:
        line.quantity = 15
    returned = env["stock.picking"].browse(wizard.action_create_returns()["res_id"])
    returned.action_assign()
    for move in returned.move_ids:
        move.quantity = 15
    returned.button_validate()


def s3():
    picking(warehouse.int_type_id, stock, stock, 15, partner=consignor,
            owner=company.partner_id)


def s4():
    po = env["purchase.order"].create({
        "partner_id": consignor.id,
        "order_line": [Command.create({"product_id": product.id, "product_qty": 15,
                                       "price_unit": 6.0})],
    })
    po.button_confirm()
    receipt = po.picking_ids
    for move in receipt.move_ids:
        move.quantity = 15
    receipt.button_validate()
    po.action_create_invoice()
    bill = po.invoice_ids
    bill.invoice_date = fields.Date.today()
    bill.action_post()
    s1()


def s5():
    quant = env["stock.quant"].create({
        "product_id": product.id, "location_id": stock.id, "inventory_quantity": 15})
    quant.action_apply_inventory()


run("S1 consigned quant counted 0 (inventory adjustment)", s1)
run("S2 consigned goods returned to the consignor (supplier return to Partners/Vendors, "
    "owner on the transfer)", s2)
if consigned_receipt:
    run("S2b the same with the standard « Return » wizard on the consigned receipt", s2b)
run("S3 internal transfer on the same location, « Assign Owner » = company", s3)
run("S4 purchase from the consignor (order 15 at 6.00, receipt, bill), then S1", s4)
run("S5 inventory adjustment adding 15 owned units (no owner)", s5)

env.cr.rollback()
print("\n".join(out))

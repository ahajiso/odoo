"""Read-only inventory of the monitor's asset alerts (owner's request, 25/10/2026).

Lists every row of lartdubati.stock.monitor with « Fixed Asset Missing » or « No Fixed
Asset (Expensed) », then for each equipment: product, category and its accounting,
cost, purchase order lines and supplier bill lines. Writes nothing (rollback at the
end). Run: odoo shell -d artdubati_test --no-http < inventory.py
"""
env = env(context=dict(env.context, active_test=False, lang="en_US"))  # noqa: F821


def out(*parts):
    print(" | ".join(str(p) for p in parts))


Monitor = env["lartdubati.stock.monitor"]
rows = Monitor.search(["|", ("alert_asset_missing", "=", 1), ("alert_no_asset", "=", 1)])
out("ROWS", len(rows))
for row in rows:
    eq = row.equipment_id
    out("ROW", f"missing={row.alert_asset_missing}", f"expensed={row.alert_no_asset}",
        f"equipment={eq.id}", eq.name, f"serial={row.serial}", f"stock={row.stock_name}")
    product = eq.product_id or row.product_id
    tmpl = product.product_tmpl_id
    categ = tmpl.categ_id
    acc = categ.property_account_expense_categ_id
    out("  PRODUCT", f"product={product.id}", product.display_name, f"tmpl={tmpl.id}",
        f"type={tmpl.type}", f"storable={tmpl.is_storable}", f"tracking={tmpl.tracking}")
    out("  CATEGORY", f"categ={categ.id}", categ.complete_name,
        f"family={categ._catalogue_family()}", f"fixed_asset_stock={categ.is_fixed_asset_stock}",
        f"valuation={categ.property_valuation}", f"expense={acc.code}",
        f"profile={acc.asset_profile_id.name or '-'}")
    out("  EQUIPMENT", f"ownership={eq.ownership_status}", f"asset={eq.asset_id.display_name or '-'}",
        f"cost={eq.cost}", f"known={eq.cost_known}", f"provisional={eq.cost_provisional}",
        f"source={eq.cost_source}", f"reference={eq.cost_reference}",
        f"ecat={eq.category_id.complete_name if 'complete_name' in eq.category_id._fields else eq.category_id.name}")
    for line in env["purchase.order.line"].search([("product_id", "=", product.id)]):
        out("  PO", line.order_id.name, f"state={line.order_id.state}", f"qty={line.product_qty}",
            f"received={line.qty_received}", f"invoiced={line.qty_invoiced}",
            f"price={line.price_unit}", f"partner={line.order_id.partner_id.name}")
    for line in env["account.move.line"].search([
            ("product_id", "=", product.id),
            ("move_id.move_type", "in", ("in_invoice", "in_refund"))]):
        out("  BILL", line.move_id.name or f"draft id={line.move_id.id}",
            f"state={line.move_id.state}", f"account={line.account_id.code}",
            f"profile={line.account_id.asset_profile_id.name or '-'}",
            f"amount={line.price_subtotal}", f"equipment={line.equipment_ids.ids}",
            f"assets={line.move_id.line_ids.mapped('asset_id').ids if 'asset_id' in line._fields else '-'}")
for code in ("215400", "218300", "606300"):
    a = env["account.account"].search([("code", "=", code)])
    out("ACCOUNT", code, a.name, f"profile={a.asset_profile_id.name or '-'}")
tools = env.ref("catalogue_stock.categ_small_tools", raise_if_not_found=False)
out("TOOLS_CATEGORY", tools.id if tools else "-", tools.complete_name if tools else "-",
    tools.property_account_expense_categ_id.code if tools else "-")
env.cr.rollback()
out("END", "read only, rolled back")

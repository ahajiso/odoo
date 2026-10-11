"""ROADMAP section 0, step 0: read-only inventory of artdubati_test (11/10/2026).

Lists, without writing anything (the transaction is rolled back at the end):
1. product categories: hierarchy, costing and valuation, accounts (and the asset
   profile of the expense account), « fixed-asset stock » flag, linked equipment
   categories, number of products;
2. equipment categories: hierarchy, linked product category, number of equipment,
   origin (external ID, creator, date) - maintenance_account creates one named after
   the product category when a bill line has none;
3. the label of `product.template.maintenance_ok` in the three languages and the
   modules defining the field;
4. the Mac Mini: products, purchase lines, stock moves, bill lines, fixed assets,
   equipment, equipment operations;
5. consignment: the « owner on stock » setting and the quants owned by a third party.

Run through the Odoo shell (no HTTP, nothing written):

    docker exec -i odoo_web odoo shell -d artdubati_test --no-http \
      < /opt/odoo/addons/custom/docs/roadmap0/inventory.py 2>/dev/null \
      | grep -E '^(CATEG|ECATEG|LABEL|MAC|OWNER|END)' > /opt/odoo/logs/roadmap0_inventory.txt
    wc -l /opt/odoo/logs/roadmap0_inventory.txt; tail -1 /opt/odoo/logs/roadmap0_inventory.txt

Output: one line per record, « SECTION | field=value | ... »; the last line is END.
"""


def acc(account):
    if not account:
        return "-"
    profile = getattr(account, "asset_profile_id", False)
    return f"{account.code} {account.name}" + (f" [asset profile: {profile.name}]" if profile else "")


def out(section, *parts):
    print(" | ".join([section] + [str(p) for p in parts]))


def xmlid(record):
    data = env["ir.model.data"].search(  # noqa: F821
        [("model", "=", record._name), ("res_id", "=", record.id)], limit=1)
    return f"{data.module}.{data.name}" if data else "-"


Template = env["product.template"].with_context(active_test=False)  # noqa: F821
Equipment = env["maintenance.equipment"].with_context(active_test=False)  # noqa: F821

# 1. product categories
for categ in env["product.category"].search([], order="complete_name"):  # noqa: F821
    out("CATEG", f"id={categ.id}", categ.complete_name,
        f"cost={categ.property_cost_method}", f"valuation={categ.property_valuation}",
        f"expense={acc(categ.property_account_expense_categ_id)}",
        f"income={acc(categ.property_account_income_categ_id)}",
        f"stock_valuation={acc(categ.property_stock_valuation_account_id)}",
        f"fixed_asset_stock={categ.is_fixed_asset_stock}",
        f"equipment_categories={categ.equipment_category_ids.mapped('name')}",
        f"products={Template.search_count([('categ_id', '=', categ.id)])}",
        f"xmlid={xmlid(categ)}")

# 2. equipment categories
ECateg = env["maintenance.equipment.category"].with_context(active_test=False)  # noqa: F821
for categ in ECateg.search([], order="complete_name"):
    out("ECATEG", f"id={categ.id}", categ.complete_name,
        f"product_category={categ.product_category_id.complete_name or '-'}",
        f"equipment={Equipment.search_count([('category_id', '=', categ.id)])}",
        f"xmlid={xmlid(categ)}", f"created_by={categ.create_uid.login}",
        f"created={categ.create_date:%Y-%m-%d %H:%M}")

# 3. label of « Can be Maintenance »
for lang in ("en_US", "fr_FR", "fa_IR"):
    label = env["product.template"].with_context(lang=lang).fields_get(  # noqa: F821
        ["maintenance_ok"], ["string"])["maintenance_ok"]["string"]
    out("LABEL", lang, label)
field = env["ir.model.fields"].search(  # noqa: F821
    [("model", "=", "product.template"), ("name", "=", "maintenance_ok")])
out("LABEL", "modules", field.modules)

# 4. Mac Mini
products = env["product.product"].with_context(active_test=False).search(  # noqa: F821
    ["|", ("name", "ilike", "mac mini"), ("name", "ilike", "macmini")])
out("MAC", f"products={len(products)}")
for product in products:
    tmpl = product.product_tmpl_id
    out("MAC", "product", f"id={product.id}", product.display_name,
        f"active={product.active}", f"categ={tmpl.categ_id.complete_name}",
        f"type={tmpl.type}", f"storable={tmpl.is_storable}", f"tracking={tmpl.tracking}",
        f"maintenance_ok={tmpl.maintenance_ok}", f"standard_price={product.standard_price}",
        f"expense_account={acc(tmpl.property_account_expense_id)}",
        f"categ_expense_account={acc(tmpl.categ_id.property_account_expense_categ_id)}",
        f"created={product.create_date:%Y-%m-%d}")
    if "purchase.order.line" in env:  # noqa: F821
        for line in env["purchase.order.line"].search([("product_id", "=", product.id)]):  # noqa: F821
            out("MAC", "purchase", line.order_id.name, f"state={line.order_id.state}",
                f"qty={line.product_qty}", f"received={line.qty_received}",
                f"invoiced={line.qty_invoiced}", f"price_unit={line.price_unit}",
                f"subtotal={line.price_subtotal} {line.currency_id.name}",
                f"invoice_status={line.order_id.invoice_status}", f"date={line.order_id.date_order:%Y-%m-%d}")
    for move in env["stock.move"].search([("product_id", "=", product.id)]):  # noqa: F821
        out("MAC", "stock_move", move.reference or "-", f"state={move.state}",
            f"from={move.location_id.complete_name}", f"to={move.location_dest_id.complete_name}",
            f"qty={move.quantity}", f"lots={move.move_line_ids.lot_id.mapped('name')}",
            f"owner={move.move_line_ids.owner_id.mapped('name')}")
    for aml in env["account.move.line"].search([("product_id", "=", product.id)]):  # noqa: F821
        out("MAC", "bill_line", aml.move_id.name or "(draft, no number)", f"type={aml.move_id.move_type}",
            f"state={aml.move_id.state}", f"account={acc(aml.account_id)}",
            f"line_asset_profile={aml.asset_profile_id.name or '-'}",
            f"asset={aml.asset_id.name or '-'}", f"subtotal={aml.price_subtotal}",
            f"equipment={aml.equipment_ids.mapped('name')}")
    for equipment in Equipment.search([("product_id", "=", product.id)]):
        out("MAC", "equipment", f"id={equipment.id}", equipment.name,
            f"active={equipment.active}",
            f"category={equipment.category_id.complete_name or '-'}",
            f"serial={equipment.stock_lot_id.name or equipment.serial_no or '-'}",
            f"ownership={equipment.ownership_status}",
            f"integration={equipment.integration_state}",
            f"cost={equipment.cost} known={equipment.cost_known} "
            f"provisional={equipment.cost_provisional} source={equipment.cost_source} "
            f"ref={equipment.cost_reference or '-'}",
            f"asset={equipment.asset_id.name or '-'}",
            f"bill_line={equipment.move_line_id.move_id.name or '-'}",
            f"location={equipment.current_location_id.complete_name or '-'}")
    for line in env["equipment.operation.line"].search(  # noqa: F821
            ["|", ("product_id", "=", product.id),
             ("equipment_id.product_id", "=", product.id)]):
        op = line.operation_id
        out("MAC", "operation", op.name, f"type={op.operation_type}", f"state={op.state}",
            f"equipment={line.equipment_id.name or '-'}")
    if "account.asset" in env:  # noqa: F821
        assets = env["account.asset"].search(  # noqa: F821
            ["|", ("name", "ilike", "mac mini"),
             ("account_move_line_ids.product_id", "=", product.id)])
        for asset in assets:
            out("MAC", "asset", asset.name, f"state={asset.state}",
                f"profile={asset.profile_id.name}", f"value={asset.purchase_value}")

# 5. consignment
group = env.ref("stock.group_tracking_owner", raise_if_not_found=False)  # noqa: F821
out("OWNER", "setting group_tracking_owner",
    f"users={len(group.users) if group else 'group missing'}")
company_partner = env.company.partner_id  # noqa: F821
for quant in env["stock.quant"].search([("owner_id", "!=", False)]):  # noqa: F821
    out("OWNER", "quant", f"id={quant.id}", quant.product_id.display_name,
        f"location={quant.location_id.complete_name}", f"qty={quant.quantity}",
        f"owner={quant.owner_id.name}",
        f"owner_is_company={quant.owner_id == company_partner}")

env.cr.rollback()  # noqa: F821
out("END", "read-only inventory complete")

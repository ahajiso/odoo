"""ROADMAP section 0, step 0: read-only inventory of artdubati_test (11/10/2026).

Lists, without writing anything (the transaction is rolled back at the end):
1. product categories, per company (company-dependent properties read with
   with_company): hierarchy, costing and valuation, accounts set on the category and
   effective ones (income and expense are inherited from the parent categories, the
   stock accounts are not), stock input / output / valuation accounts, the asset
   profile of each account, « fixed-asset stock » flag, linked equipment categories,
   number of products;
1b. every product, per company: accounts set on the product, effective accounts
   (_get_product_accounts: product, then category hierarchy), asset profile of the
   effective expense account, and the differences with its category (PRODUCT lines,
   « override » when the product sets its own account);
2. equipment categories: hierarchy, linked product category, number of equipment,
   origin (external ID, creator, date) - maintenance_account creates one named after
   the product category when a bill line has none;
3. the label of `product.template.maintenance_ok` in the three languages and the
   modules defining the field;
4. the Mac Mini: products, purchase lines, stock moves, bill lines, fixed assets,
   equipment, equipment operations;
5. consignment: the « owner on stock » setting and the quants owned by a third party.

Run with run_inventory.sh (pipefail, Odoo's exit code, stderr kept, END checked).

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

# 1. product categories, per company
CATEG_ACCOUNTS = ("property_account_income_categ_id", "property_account_expense_categ_id",
                  "property_stock_account_input_categ_id",
                  "property_stock_account_output_categ_id",
                  "property_stock_valuation_account_id")
INHERITED = ("property_account_income_categ_id", "property_account_expense_categ_id")


def categ_account(categ, field_name):
    """Effective category account: income and expense go up the hierarchy
    (product.template._get_category_account), the stock accounts do not."""
    if field_name not in INHERITED:
        return categ[field_name]
    while categ:
        if categ[field_name]:
            return categ[field_name]
        categ = categ.parent_id
    return categ[field_name]


companies = env["res.company"].search([])  # noqa: F821
for company in companies:
    for categ in env["product.category"].with_company(company).search(  # noqa: F821
            [], order="complete_name"):
        accounts = []
        for name in CATEG_ACCOUNTS:
            short = name.replace("property_", "").replace("_categ_id", "").replace(
                "_account_id", "").replace("account_", "")
            own, effective = categ[name], categ_account(categ, name)
            accounts.append(f"{short}={acc(effective)}"
                            + ("" if own == effective else " (inherited)"))
        out("CATEG", f"company={company.name}", f"id={categ.id}", categ.complete_name,
            f"cost={categ.property_cost_method}", f"valuation={categ.property_valuation}",
            *accounts,
            f"fixed_asset_stock={categ.is_fixed_asset_stock}",
            f"equipment_categories={categ.equipment_category_ids.mapped('name')}",
            f"products={Template.search_count([('categ_id', '=', categ.id)])}",
            f"xmlid={xmlid(categ)}")

# 1b. every product, per company: own accounts, effective accounts, differences
for company in companies:
    for tmpl in Template.with_company(company).search(
            ["|", ("company_id", "=", False), ("company_id", "=", company.id)],
            order="categ_id, name"):
        effective = tmpl._get_product_accounts()
        expense = effective["expense"]
        profile = getattr(expense, "asset_profile_id", False)
        overrides = [f"{key}: product {acc(own)} / category "
                     f"{acc(categ_account(tmpl.categ_id, field))}"
                     for key, own, field in (
                         ("income", tmpl.property_account_income_id,
                          "property_account_income_categ_id"),
                         ("expense", tmpl.property_account_expense_id,
                          "property_account_expense_categ_id"))
                     if own and own != categ_account(tmpl.categ_id, field)]
        out("PRODUCT", f"company={company.name}", f"id={tmpl.id}", tmpl.name,
            f"active={tmpl.active}", f"categ={tmpl.categ_id.complete_name}",
            f"type={tmpl.type}", f"storable={tmpl.is_storable}",
            f"maintenance_ok={tmpl.maintenance_ok}",
            f"own_income={acc(tmpl.property_account_income_id)}",
            f"own_expense={acc(tmpl.property_account_expense_id)}",
            f"income={acc(effective['income'])}", f"expense={acc(expense)}",
            f"stock_input={acc(effective.get('stock_input'))}",
            f"stock_output={acc(effective.get('stock_output'))}",
            f"stock_valuation={acc(effective.get('stock_valuation'))}",
            f"expense_asset_profile={profile.name if profile else '-'}",
            f"override={'; '.join(overrides) or '-'}")

# 2. equipment categories
ECateg = env["maintenance.equipment.category"].with_context(active_test=False)  # noqa: F821
for categ in ECateg.search([], order="complete_name"):
    out("ECATEG", f"id={categ.id}", categ.complete_name,
        f"product_category={categ.product_category_id.complete_name or '-'}",
        f"equipment={Equipment.search_count([('category_id', '=', categ.id)])}",
        f"xmlid={xmlid(categ)}", f"created_by={categ.create_uid.login}",
        f"created={categ.create_date:%Y-%m-%d %H:%M}")

# 3. label of maintenance_ok (wanted, ROADMAP 0.1: « Can be maintained », « Peut être
# maintenu », Persian equivalent)
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
        f"created={product.create_date:%Y-%m-%d}")
    for company in companies:
        effective = tmpl.with_company(company)._get_product_accounts()
        profile = getattr(effective["expense"], "asset_profile_id", False)
        out("MAC", "accounts", f"company={company.name}",
            f"expense={acc(effective['expense'])}",
            f"expense_asset_profile={profile.name if profile else '-'}",
            f"stock_valuation={acc(effective.get('stock_valuation'))}")
    if "purchase.order.line" in env:  # noqa: F821
        for line in env["purchase.order.line"].search([("product_id", "=", product.id)]):  # noqa: F821
            out("MAC", "purchase", line.order_id.name, f"state={line.order_id.state}",
                f"qty={line.product_qty}", f"received={line.qty_received}",
                f"invoiced={line.qty_invoiced}", f"price_unit={line.price_unit}",
                f"subtotal={line.price_subtotal} {line.currency_id.name}",
                f"invoice_status={line.order_id.invoice_status}",
                f"company={line.company_id.name}", f"date={line.order_id.date_order:%Y-%m-%d}")
    for move in env["stock.move"].search([("product_id", "=", product.id)]):  # noqa: F821
        out("MAC", "stock_move", move.reference or "-", f"state={move.state}",
            f"from={move.location_id.complete_name}", f"to={move.location_dest_id.complete_name}",
            f"qty={move.quantity}", f"lots={move.move_line_ids.lot_id.mapped('name')}",
            f"owner={move.move_line_ids.owner_id.mapped('name')}")
    for aml in env["account.move.line"].search([("product_id", "=", product.id)]):  # noqa: F821
        out("MAC", "bill_line", aml.move_id.name or "(draft, no number)",
            f"company={aml.company_id.name}", f"type={aml.move_id.move_type}",
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
company_partners = companies.partner_id
for quant in env["stock.quant"].search([("owner_id", "!=", False)]):  # noqa: F821
    out("OWNER", "quant", f"company={quant.company_id.name}", f"id={quant.id}", quant.product_id.display_name,
        f"location={quant.location_id.complete_name}", f"qty={quant.quantity}",
        f"owner={quant.owner_id.name}",
        f"owner_is_a_company={quant.owner_id in company_partners}")

env.cr.rollback()  # noqa: F821
out("END", "read-only inventory complete")

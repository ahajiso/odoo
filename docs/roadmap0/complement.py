"""ROADMAP section 0, step 0b: read-only complement (11/10/2026), for the four
classifications (equipment, product categories, contract natures, business registers).

Lists, without writing anything (rolled back at the end):
- EQUIP: every equipment: category, product and its category, serial, ownership,
  integration, cost, fixed asset, bill line;
- STOCK: every quant of an internal location: category, cost method, quantity, value,
  owner, lot;
- PRICE: the history of P00381 (tracked values and messages of the order; last write of
  each line, which has no chatter)
  and of the Mac Mini equipment's cost;
- SERVICE: every service product: category, accounts set and effective, purchase /
  sale, contract lines using it (by nature);
- CONTRACT: every contract line: contract, type, partner, product, equipment and its
  relation (rental, loan, insurance, maintenance), recurrence, dates, price;
- NATURE: the values of the contract types and of the equipment relation;
- PROFILE / ASSET: asset profiles (accounts, method, duration) and fixed assets;
- ACCOUNT: accounts of classes 20, 21, 60, 61, 62, 66, 67 with type, asset profile and
  number of journal items (which ones exist for IT, software, maintenance, insurance,
  telecom, rentals and leasing, fees, subcontracting, transport, energy, bank fees).

Run: bash run_inventory.sh complement.py  (same checks as the inventory).
"""

Equipment = env["maintenance.equipment"].with_context(active_test=False)  # noqa: F821
companies = env["res.company"].search([])  # noqa: F821


def out(section, *parts):
    print(" | ".join([section] + [str(p) for p in parts]))


def acc(account):
    if not account:
        return "-"
    profile = getattr(account, "asset_profile_id", False)
    return f"{account.code} {account.name}" + (f" [asset profile: {profile.name}]" if profile else "")


def tracking(record):
    """Tracked value changes of a record, oldest first (records with a chatter only)."""
    rows = []
    if "message_ids" not in record._fields:
        return rows
    for message in record.message_ids.sorted("id"):
        for value in message.tracking_value_ids:
            ttype = value.field_id.ttype
            if ttype in ("float", "monetary"):
                old, new = value.old_value_float, value.new_value_float
            elif ttype in ("integer", "boolean"):
                old, new = value.old_value_integer, value.new_value_integer
            else:
                old, new = value.old_value_char, value.new_value_char
            rows.append(f"{message.date:%Y-%m-%d %H:%M} {message.author_id.name}: "
                        f"{value.field_id.name} {old} -> {new}")
    return rows


# EQUIP
for equipment in Equipment.search([], order="id"):
    lot = equipment.stock_lot_id
    quant_location = lot.quant_ids.filtered(lambda q: q.quantity > 0 and q.location_id.usage == "internal").location_id
    out("EQUIP", f"id={equipment.id}", equipment.name, f"active={equipment.active}",
        f"company={equipment.company_id.name}",
        f"category={equipment.category_id.complete_name or '-'}",
        f"product={equipment.product_id.display_name or '-'}",
        f"product_categ={equipment.product_id.categ_id.complete_name or '-'}",
        f"serial={lot.name or equipment.serial_no or '-'}",
        f"stock_location={quant_location.mapped('complete_name') or '-'}",
        f"monitor_location={equipment.current_location_id.complete_name or '-'}",
        f"ownership={equipment.ownership_status}", f"owner={equipment.owner_partner_id.name or '-'}",
        f"integration={equipment.integration_state}",
        f"cost={equipment.cost} provisional={equipment.cost_provisional} "
        f"source={equipment.cost_source} ref={equipment.cost_reference or '-'}",
        f"asset={equipment.asset_id.name or '-'}",
        f"bill={equipment.move_line_id.move_id.name or '-'}")

# STOCK: what is really in the internal locations, with its value and cost method
for quant in env["stock.quant"].search([("location_id.usage", "=", "internal")],  # noqa: F821
                                       order="product_id, location_id"):
    product = quant.product_id
    out("STOCK", f"company={quant.company_id.name}", product.display_name,
        f"categ={product.categ_id.complete_name}",
        f"cost_method={product.categ_id.property_cost_method}",
        f"location={quant.location_id.complete_name}", f"qty={quant.quantity}",
        f"value={quant.value} {quant.currency_id.name}",
        f"unit_cost={product.standard_price}",
        f"owner={quant.owner_id.name or '-'}", f"lot={quant.lot_id.name or '-'}")

# PRICE
order = env["purchase.order"].search([("name", "=", "P00381")])  # noqa: F821
# order lines have no chatter: their last change is shown by « line now » below
for record in order:
    for row in tracking(record):
        out("PRICE", record._name, record.display_name, row)
for message in order.message_ids.sorted("id"):
    body = (message.body or "").replace("\n", " ")
    out("PRICE", "message", f"{message.date:%Y-%m-%d %H:%M}", message.author_id.name,
        message.message_type, body[:160] or "-")
for line in order.order_line:
    out("PRICE", "line now", line.product_id.display_name, f"price_unit={line.price_unit}",
        f"write_date={line.write_date:%Y-%m-%d %H:%M}", f"write_uid={line.write_uid.login}")
for picking in order.picking_ids:
    out("PRICE", "receipt", picking.name, f"state={picking.state}",
        f"done={picking.date_done or '-'}")
for equipment in Equipment.search([("product_id.name", "ilike", "mac mini")]):
    for row in tracking(equipment):
        out("PRICE", "equipment", equipment.name, row)
    out("PRICE", "equipment cost date", equipment.name, f"cost_date={equipment.cost_date}")

# SERVICE
lines_model = env["contract.line"] if "contract.line" in env else None  # noqa: F821
for company in companies:
    Template = env["product.template"].with_company(company).with_context(active_test=False)  # noqa: F821
    for tmpl in Template.search([("type", "=", "service")], order="categ_id, name"):
        effective = tmpl._get_product_accounts()
        natures = {}
        if lines_model is not None:
            for line in lines_model.search([("product_id.product_tmpl_id", "=", tmpl.id)]):
                key = f"{line.contract_id.contract_type}/{line.equipment_nature or '-'}"
                natures[key] = natures.get(key, 0) + 1
        out("SERVICE", f"company={company.name}", f"id={tmpl.id}", tmpl.name,
            f"active={tmpl.active}", f"categ={tmpl.categ_id.complete_name}",
            f"purchase_ok={tmpl.purchase_ok}", f"sale_ok={tmpl.sale_ok}",
            f"own_income={acc(tmpl.property_account_income_id)}",
            f"own_expense={acc(tmpl.property_account_expense_id)}",
            f"income={acc(effective['income'])}", f"expense={acc(effective['expense'])}",
            f"contract_lines={natures or '-'}")

# CONTRACT
if lines_model is not None:
    for line in lines_model.with_context(active_test=False).search([], order="contract_id, id"):
        contract = line.contract_id
        out("CONTRACT", contract.name, f"id={contract.id}", f"active={contract.active}",
            f"type={contract.contract_type}", f"partner={contract.partner_id.name}",
            f"line={line.name.splitlines()[0] if line.name else '-'}",
            f"product={line.product_id.display_name or '-'}",
            f"equipment={line.equipment_id.name or '-'}",
            f"relation={line.equipment_nature or '-'}",
            f"every={line.recurring_interval} {line.recurring_rule_type}",
            f"from={line.date_start}", f"to={line.date_end or '-'}",
            f"price={line.price_unit} {contract.currency_id.name}")

# NATURE
for model, field in (("contract.contract", "contract_type"), ("contract.line", "equipment_nature")):
    if model in env:  # noqa: F821
        values = env[model].fields_get([field], ["selection"])[field]["selection"]  # noqa: F821
        out("NATURE", f"{model}.{field}", values)

# PROFILE / ASSET
if "account.asset.profile" in env:  # noqa: F821
    for profile in env["account.asset.profile"].with_context(active_test=False).search([]):  # noqa: F821
        out("PROFILE", f"id={profile.id}", profile.name, f"company={profile.company_id.name}",
            f"asset_account={acc(profile.account_asset_id)}",
            f"depreciation_account={acc(profile.account_depreciation_id)}",
            f"expense_account={acc(profile.account_expense_depreciation_id)}",
            f"method={profile.method}", f"number={profile.method_number}",
            f"period={profile.method_period}", f"time={profile.method_time}")
    for asset in env["account.asset"].with_context(active_test=False).search([]):  # noqa: F821
        out("ASSET", f"id={asset.id}", asset.name, f"state={asset.state}",
            f"profile={asset.profile_id.name}", f"value={asset.purchase_value}",
            f"start={asset.date_start}",
            f"equipment={Equipment.search([('asset_id', '=', asset.id)]).mapped('name') or '-'}")

# ACCOUNT
AML = env["account.move.line"]  # noqa: F821
for company in companies:
    Account = env["account.account"].with_company(company)  # noqa: F821
    for prefix in ("20", "21", "60", "61", "62", "66", "67"):
        for account in Account.search([("code", "=like", f"{prefix}%")], order="code"):
            out("ACCOUNT", f"company={company.name}", account.code, account.name,
                f"type={account.account_type}",
                f"asset_profile={account.asset_profile_id.name or '-'}",
                f"items={AML.search_count([('account_id', '=', account.id)])}")

env.cr.rollback()  # noqa: F821
out("END", "read-only inventory complete")

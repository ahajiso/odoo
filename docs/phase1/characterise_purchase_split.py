"""Characterisation: purchase order of 3 serial units billed on a fixed-asset account.

Local throw-away database only (creates a French company, rolled back):
    odoo-bin shell -c <conf> -d <local_db> --no-http < characterise_purchase_split.py
Variant with the fix: replace `po.action_create_invoice()` by
`po.with_context(include_business_fields=True).action_create_invoice()`.
Result: docs/phase1/CHARACTERISATION.md.
"""
env = self.env
co = env['res.company'].create({'name': 'LADB test PO', 'country_id': env.ref('base.fr').id, 'currency_id': env.ref('base.EUR').id})
env.user.company_ids |= co
env['account.chart.template'].try_loading('fr', co, install_demo=False)
env = env(context=dict(env.context, allowed_company_ids=[co.id]))
env.user.company_id = co
Acc = env['account.account']
def acc(code): return Acc.search([('code', '=', code), ('company_ids', 'in', co.id)], limit=1)
misc = env['account.journal'].search([('type', '=', 'general'), ('company_id', '=', co.id)], limit=1)
prof = env['account.asset.profile'].create({'name': 'P', 'account_asset_id': acc('215400').id, 'account_depreciation_id': acc('281500').id,
    'account_expense_depreciation_id': acc('681120').id, 'journal_id': misc.id, 'method_number': 5, 'asset_product_item': True})
categ = env['product.category'].create({'name': 'Fixed Assets', 'property_cost_method': 'average', 'property_valuation': 'manual_periodic',
    'property_account_expense_categ_id': acc('215400').id})
prod = env['product.product'].create({'name': 'Drill', 'type': 'consu', 'is_storable': True, 'tracking': 'serial', 'maintenance_ok': True,
    'categ_id': categ.id, 'standard_price': 100, 'purchase_method': 'receive'})
vendor = env['res.partner'].create({'name': 'Vendor'})
wh = env['stock.warehouse'].search([('company_id', '=', co.id)], limit=1) or env['stock.warehouse'].create({'name': 'WH2', 'code': 'W2', 'company_id': co.id})
ptype = wh.in_type_id
po = env['purchase.order'].create({'partner_id': vendor.id, 'picking_type_id': ptype.id, 'order_line': [(0, 0, {'product_id': prod.id, 'product_qty': 3, 'price_unit': 100, 'taxes_id': [(5,)]})]})
po.button_confirm()
pick = po.picking_ids
for i, mv in enumerate(pick.move_ids):
    mv.move_line_ids.unlink()
    for n in range(3):
        env['stock.move.line'].create({'move_id': mv.id, 'picking_id': pick.id, 'product_id': prod.id, 'lot_name': f'SN{n}', 'quantity': 1,
            'location_id': mv.location_id.id, 'location_dest_id': mv.location_dest_id.id, 'product_uom_id': prod.uom_id.id})
pick.button_validate()
print("picking", pick.state, "lots", pick.move_line_ids.lot_id.mapped('name'))
pol = po.order_line
print("PO qty_received", pol.qty_received, "qty_to_invoice", pol.qty_to_invoice)
po.action_create_invoice()
bill = po.invoice_ids
bill.invoice_date = '2026-10-08'
print("bill lines:", [(l.quantity, l.account_id.code, bool(l.purchase_line_id), l.asset_profile_id.name) for l in bill.invoice_line_ids])
print("PO qty_invoiced before post", pol.qty_invoiced, "qty_to_invoice", pol.qty_to_invoice)
bill.action_post()
print("PO qty_invoiced after post", pol.qty_invoiced, "qty_to_invoice", pol.qty_to_invoice, "invoice_status", po.invoice_status)
print("assets", len(env['account.asset'].search([('company_id', '=', co.id)])), "equipment", env['maintenance.equipment'].search_count([('move_id', '=', bill.id)]))
print("stock valuation layers value", sum(env['stock.valuation.layer'].search([('product_id', '=', prod.id)]).mapped('value')))
env.cr.rollback()

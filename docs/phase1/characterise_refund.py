"""Characterisation of supplier refunds on a fixed-asset bill (Odoo 18 + OCA).

Run in `odoo shell` on a LOCAL throw-away database only (it creates a French company
and loads its chart of accounts, then rolls everything back):
    odoo-bin shell -c <conf> -d <local_db> --no-http < characterise_refund.py
Never run it on artdubati or artdubati_test. Result: docs/phase1/CHARACTERISATION.md.
"""
# Characterisation of supplier refunds on a fixed-asset bill (Odoo 18 + OCA), run in odoo shell.
env = self.env
co = env['res.company'].create({'name': 'LADB test', 'country_id': env.ref('base.fr').id, 'currency_id': env.ref('base.EUR').id})
env.user.company_ids |= co
env['account.chart.template'].try_loading('fr', co, install_demo=False)
env = env(context=dict(env.context, allowed_company_ids=[co.id]))
env.user.company_id = co
print("company", co.name, "chart", co.chart_template, "country", co.country_id.code)
Acc = env['account.account']
def acc(code): return Acc.search([('code', '=', code), ('company_ids', 'in', co.id)], limit=1)
a215, a2815, a68112 = acc('215400'), acc('281500'), acc('681120')
print("accounts", a215.code, a2815.code, a68112.code)
misc = env['account.journal'].search([('type', '=', 'general'), ('company_id', '=', co.id)], limit=1)
prof = env['account.asset.profile'].create({
    'name': 'Test profile', 'account_asset_id': a215.id, 'account_depreciation_id': a2815.id,
    'account_expense_depreciation_id': a68112.id, 'journal_id': misc.id, 'method': 'linear',
    'method_time': 'year', 'method_number': 5, 'method_period': 'year', 'prorata': True,
    'open_asset': False, 'asset_product_item': True})
print("profile on account after profile create:", a215.asset_profile_id.name)
a215.asset_profile_id = prof
vendor = env['res.partner'].create({'name': 'Vendor X'})
prod = env['product.product'].create({'name': 'Saw', 'type': 'consu', 'maintenance_ok': True, 'standard_price': 1000})
Asset = env['account.asset']
def snap(label):
    assets = Asset.search([])
    print(f"--- {label}: {len(assets)} asset(s): " + "; ".join(f"id{a.id} value={a.purchase_value} state={a.state}" for a in assets))
bill = env['account.move'].create({'move_type': 'in_invoice', 'partner_id': vendor.id, 'invoice_date': '2026-10-01',
    'invoice_line_ids': [(0, 0, {'product_id': prod.id, 'name': 'Saw', 'quantity': 2, 'price_unit': 1000, 'account_id': a215.id, 'tax_ids': [(5,)]})]})
print("bill lines after create (asset_product_item split):", [(l.quantity, l.asset_profile_id.name) for l in bill.invoice_line_ids])
bill.action_post()
snap("after bill post")
print("equipment from bill:", [(e.name, e.move_line_id.id) for e in env['maintenance.equipment'].search([('move_id', '=', bill.id)])])
wiz = env['account.move.reversal'].with_context(active_model='account.move', active_ids=bill.ids).create({'journal_id': bill.journal_id.id, 'date': '2026-10-05'})
res = wiz.refund_moves()
refund = env['account.move'].browse(res['res_id'])
print("refund", refund.move_type, refund.state, "lines:", [(l.quantity, l.account_id.code, l.asset_profile_id.name, l.asset_id.id, l.equipment_ids.ids) for l in refund.invoice_line_ids])
refund.action_post()
snap("after reversal posted")
print("equipment linked to refund lines:", refund.invoice_line_ids.equipment_ids.ids, "equipment total:", env['maintenance.equipment'].search_count([]))
man = env['account.move'].create({'move_type': 'in_refund', 'partner_id': vendor.id, 'invoice_date': '2026-10-06',
    'invoice_line_ids': [(0, 0, {'name': 'Manual refund', 'quantity': 1, 'price_unit': 300, 'account_id': a215.id, 'tax_ids': [(5,)]})]})
man.action_post()
snap("after manual refund posted")
env.cr.rollback()
print("rolled back")

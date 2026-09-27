# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

AUTOLIQUIDATION_MENTION = (
    "Autoliquidation - Article 283-2 nonies du CGI. "
    "TVA due par le preneur (client donneur d'ordre)."
)


def _find_tax(env, company, type_tax_use, tax_scope, amount):
    """Find a (possibly archived) tax matching the given criteria for the company."""
    tax = env['account.tax'].with_context(active_test=False).search([
        ('company_id', '=', company.id),
        ('type_tax_use', '=', type_tax_use),
        ('tax_scope', '=', tax_scope),
        ('amount_type', '=', 'percent'),
        ('amount', '=', amount),
        ('country_id.code', '=', 'FR'),
    ], limit=1)
    return tax


def _activate_reduced_rate_taxes(env, company):
    """Un-archive the 10% and 5.5% sale taxes (goods 'consu' and service 'S'),
    disabled by default in Odoo's French fiscal templates."""
    to_activate = []
    for tax_scope in ('consu', 'service'):
        for amount in (10.0, 5.5):
            tax = _find_tax(env, company, 'sale', tax_scope, amount)
            if tax and not tax.active:
                to_activate.append(tax.id)
            elif not tax:
                _logger.warning(
                    "lartdubati_facturation: taxe vente %.1f%% (%s) introuvable "
                    "pour la société %s", amount, tax_scope, company.name,
                )
    if to_activate:
        env['account.tax'].browse(to_activate).write({'active': True})
        _logger.info("lartdubati_facturation: %s taxes de vente réactivées (10%%/5.5%%)", len(to_activate))

    # Also un-archive the matching purchase taxes (10%/5.5%, goods and service),
    # needed as source taxes for the subcontracting fiscal position below.
    to_activate_purchase = []
    for tax_scope in ('consu', 'service'):
        for amount in (10.0, 5.5):
            tax = _find_tax(env, company, 'purchase', tax_scope, amount)
            if tax and not tax.active:
                to_activate_purchase.append(tax.id)
    if to_activate_purchase:
        env['account.tax'].browse(to_activate_purchase).write({'active': True})
        _logger.info(
            "lartdubati_facturation: %s taxes d'achat réactivées (10%%/5.5%%)",
            len(to_activate_purchase),
        )


def _create_autoliquidation_taxes(env, company):
    """Create the BTP subcontracting reverse-charge taxes (sale 0% / purchase
    self-assessed 20%, 10%, 5.5%), idempotently."""
    AccountTax = env['account.tax']
    tax_group_20 = env.ref('l10n_fr_account.tax_group_tva_20', raise_if_not_found=False)

    taxes = {}

    # --- Sale side: 0% when acting as subcontractor ---
    sale_tax = AccountTax.with_context(active_test=False).search([
        ('company_id', '=', company.id),
        ('name', '=', 'Autoliquidation sous-traitance BTP (vente 0%)'),
    ], limit=1)
    if not sale_tax:
        sale_tax_vals = {
            'name': 'Autoliquidation sous-traitance BTP (vente 0%)',
            'description': 'Autoliquidation BTP',
            'amount': 0.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'tax_scope': 'service',
            'company_id': company.id,
            'country_id': env.ref('base.fr').id,
            'invoice_label': 'Autoliquidation',
            'invoice_repartition_line_ids': [
                (0, 0, {'factor_percent': 100, 'repartition_type': 'base'}),
                (0, 0, {'factor_percent': 100, 'repartition_type': 'tax'}),
            ],
            'refund_repartition_line_ids': [
                (0, 0, {'factor_percent': 100, 'repartition_type': 'base'}),
                (0, 0, {'factor_percent': 100, 'repartition_type': 'tax'}),
            ],
        }
        if tax_group_20:
            sale_tax_vals['tax_group_id'] = tax_group_20.id
        sale_tax = AccountTax.create(sale_tax_vals)
        _logger.info("lartdubati_facturation: taxe de vente autoliquidation 0%% créée (id=%s)", sale_tax.id)
    taxes['vente_0'] = sale_tax

    # --- Purchase side: self-assessed 20% / 10% / 5.5% when hiring a subcontractor ---
    # Note: since Odoo 17, account.account is shared across companies via
    # 'company_ids' (m2m) rather than a single 'company_id' field.
    acc_444 = env['account.account'].search([
        ('company_ids', 'in', company.id), ('code', 'like', '445662%'),
    ], limit=1)
    acc_445 = env['account.account'].search([
        ('company_ids', 'in', company.id), ('code', 'like', '44521%'),
    ], limit=1)
    if not acc_444 or not acc_445:
        _logger.warning(
            "lartdubati_facturation: comptes 445662 (TVA collectée autoliquidation) et/ou "
            "44521 (TVA déductible autoliquidation) introuvables pour %s ; les taxes d'achat "
            "autoliquidation seront créées SANS compte affecté (à corriger manuellement).",
            company.name,
        )

    for rate, key in ((20.0, 'achat_20'), (10.0, 'achat_10'), (5.5, 'achat_5_5')):
        name = f'Autoliquidation sous-traitance BTP (achat {rate:g}%)'
        purchase_tax = AccountTax.with_context(active_test=False).search([
            ('company_id', '=', company.id), ('name', '=', name),
        ], limit=1)
        if not purchase_tax:
            # Invoice side: +100% collected (445662-type account), -100% deductible (44521-type account).
            invoice_collected = {'factor_percent': 100, 'repartition_type': 'tax'}
            invoice_deductible = {'factor_percent': -100, 'repartition_type': 'tax'}
            # Refund side must use the SAME percentages, in the same order, as the
            # invoice side (Odoo validates this); only the report tags differ, and
            # those are left empty pending the accountant's CA3 box confirmation.
            refund_collected = {'factor_percent': 100, 'repartition_type': 'tax'}
            refund_deductible = {'factor_percent': -100, 'repartition_type': 'tax'}
            if acc_444:
                invoice_collected['account_id'] = acc_444.id
                refund_collected['account_id'] = acc_444.id
            if acc_445:
                invoice_deductible['account_id'] = acc_445.id
                refund_deductible['account_id'] = acc_445.id
            purchase_tax = AccountTax.create({
                'name': name,
                'description': f'Autoliq. BTP {rate:g}%',
                'amount': rate,
                'amount_type': 'percent',
                'type_tax_use': 'purchase',
                'tax_scope': 'service',
                'company_id': company.id,
                'country_id': env.ref('base.fr').id,
                'invoice_label': f'Autoliq. {rate:g}%',
                'invoice_repartition_line_ids': [
                    (0, 0, {'factor_percent': 100, 'repartition_type': 'base'}),
                    (0, 0, invoice_collected),
                    (0, 0, invoice_deductible),
                ],
                'refund_repartition_line_ids': [
                    (0, 0, {'factor_percent': 100, 'repartition_type': 'base'}),
                    (0, 0, refund_collected),
                    (0, 0, refund_deductible),
                ],
            })
            _logger.info("lartdubati_facturation: taxe d'achat autoliquidation %.1f%% créée (id=%s)", rate, purchase_tax.id)
        taxes[key] = purchase_tax

    return taxes


def _create_fiscal_position(env, company, autoliq_taxes):
    FiscalPosition = env['account.fiscal.position']
    existing = FiscalPosition.search([
        ('company_id', '=', company.id),
        ('name', '=', 'Sous-traitance BTP - Autoliquidation (Art. 283-2 nonies CGI)'),
    ], limit=1)
    if existing:
        return existing

    tax_mapping = []

    # Sale side: any normal sale rate -> 0% autoliquidation
    for tax_scope in ('consu', 'service'):
        for amount in (20.0, 10.0, 5.5):
            src = _find_tax(env, company, 'sale', tax_scope, amount)
            if src:
                tax_mapping.append((0, 0, {
                    'tax_src_id': src.id,
                    'tax_dest_id': autoliq_taxes['vente_0'].id,
                }))

    # Purchase side: normal rate -> matching self-assessed autoliquidation rate
    rate_to_key = {20.0: 'achat_20', 10.0: 'achat_10', 5.5: 'achat_5_5'}
    for tax_scope in ('consu', 'service'):
        for amount, key in rate_to_key.items():
            src = _find_tax(env, company, 'purchase', tax_scope, amount)
            if src:
                tax_mapping.append((0, 0, {
                    'tax_src_id': src.id,
                    'tax_dest_id': autoliq_taxes[key].id,
                }))

    fpos = FiscalPosition.create({
        'name': 'Sous-traitance BTP - Autoliquidation (Art. 283-2 nonies CGI)',
        'company_id': company.id,
        'country_id': env.ref('base.fr').id,
        'auto_apply': False,
        'note': AUTOLIQUIDATION_MENTION,
        'fiscal_position_tax_ids': tax_mapping,
    })
    _logger.info("lartdubati_facturation: position fiscale sous-traitance créée (id=%s, %s correspondances)",
                 fpos.id, len(tax_mapping))
    return fpos


def _create_products(env, company):
    Product = env['product.template']
    tax_10_service = _find_tax(env, company, 'sale', 'service', 10.0)
    tax_20_service = _find_tax(env, company, 'sale', 'service', 20.0)

    products_data = [
        {
            'name': "Main d'œuvre - Finition / Façade (horaire)",
            'type': 'service',
            'uom_name': 'Heure(s)',
            'taxes': tax_10_service,
        },
        {
            'name': 'Matériaux de construction (finition/façade)',
            'type': 'consu',
            'uom_name': None,
            'taxes': tax_10_service,
        },
        {
            'name': 'Conseil / Prestation intellectuelle',
            'type': 'service',
            'uom_name': None,
            'taxes': tax_20_service,
        },
    ]

    uom_hour = env.ref('uom.product_uom_hour', raise_if_not_found=False)

    for vals in products_data:
        existing = Product.search([
            ('name', '=', vals['name']), ('company_id', 'in', [company.id, False]),
        ], limit=1)
        if existing:
            continue
        create_vals = {
            'name': vals['name'],
            'type': vals['type'],
            'sale_ok': True,
            'purchase_ok': vals['type'] == 'consu',
            'taxes_id': [(6, 0, vals['taxes'].ids)] if vals['taxes'] else [],
        }
        # 'invoice_policy' only exists once the Sales app ('sale') is installed.
        if 'invoice_policy' in Product._fields:
            create_vals['invoice_policy'] = 'order'
        if vals['uom_name'] == 'Heure(s)' and uom_hour:
            create_vals['uom_id'] = uom_hour.id
            create_vals['uom_po_id'] = uom_hour.id
        product = Product.create(create_vals)
        _logger.info("lartdubati_facturation: article créé: %s (id=%s)", vals['name'], product.id)


def post_init_hook(env):
    company = env.company
    _logger.info("lartdubati_facturation: post_init_hook démarré pour la société %s", company.name)
    _activate_reduced_rate_taxes(env, company)
    autoliq_taxes = _create_autoliquidation_taxes(env, company)
    _create_fiscal_position(env, company, autoliq_taxes)
    _create_products(env, company)
    _logger.info("lartdubati_facturation: post_init_hook terminé")

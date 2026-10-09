"""Stock monitor: one read-only SQL view (docs/phase3/PLAN.md §3).

One row per integrated equipment (id = equipment id × 2) and one row per consumable
quant (id = quant id × 2 + 1). Values follow §3.4, conversions §3.5, rent §3.6 and
alerts §3.7. The only SQL object is the view; no PostgreSQL function.
"""
from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError
from odoo.osv import expression

from odoo.addons.maintenance_shareholder_equipment.models.maintenance_equipment import (
    INSURANCE_STATUS,
    OWNERSHIP_STATUS,
    WARRANTY_STATUS,
)

STAFF = "stock.group_stock_user,account.group_account_readonly"
ACCOUNTANTS = "account.group_account_readonly"

# converted measures: field name -> short name of its source columns in the SQL
MEASURES = {
    "inventory_value": "inventory",
    "replacement_value": "replacement",
    "stock_value": "stock",
    "original_value": "original",
    "depreciated_value": "depreciated",
    "accounting_value": "accounting",
    "rent_monthly": "rent_m",
}
# dashboard filters (§4.3): key -> type of its value; text labels, never ids (ids are
# reserved to staff, a domain on them would be refused to an investor)
FILTER_TYPES = {
    "countries": list, "cities": list, "stocks": list, "families": list,
    "ownerships": list, "alert": str, "search": str,
}
OUTSIDE_STOCK = "__outside__"  # stock filter value of the rows outside any monitor stock
SEARCH_FIELDS = ("product_name", "equipment_name", "serial", "stock_name", "location_name",
                 "category_name")
# rate alerts an investor may see: those of the measures every monitor user sees
PUBLIC_RATE_ALERTS = ("inventory_value_rate_missing", "replacement_value_rate_missing")

# alerts (§3.7); their groups are given on the fields
ALERTS = {
    "alert_rate_missing": STAFF,
    "alert_integrity": STAFF,
    "alert_no_position": STAFF,
    "alert_negative_quantity": STAFF,
    "alert_cost_missing": STAFF,
    "alert_outside_stock": STAFF,
    "alert_rental_ended": STAFF,
    "alert_asset_removed": ACCOUNTANTS,
    "alert_asset_missing": ACCOUNTANTS,
    "alert_replacement_missing": STAFF,
    "alert_replacement_old": STAFF,
    "alert_lent_uninsured": STAFF,
    "alert_rent_period_unsupported": STAFF,
    "alert_no_asset": STAFF,
    "alert_no_responsible": STAFF,
}


def _company_dependent(column, model, field, company, cast):
    """Value of a company-dependent jsonb column for `company`, with the fallback
    Odoo uses (ir.default of the company, then the global one: _get_model_defaults)."""
    return f"""COALESCE(
        ({column} ->> ({company})::text)::{cast},
        (SELECT (d.json_value::jsonb #>> '{{}}')::{cast}
           FROM ir_default d JOIN ir_model_fields f ON f.id = d.field_id
          WHERE f.model = '{model}' AND f.name = '{field}' AND d.user_id IS NULL
            AND d.condition IS NULL AND (d.company_id = ({company}) OR d.company_id IS NULL)
          ORDER BY d.company_id NULLS LAST, d.id LIMIT 1))"""


def _rate_joins(alias, currency, date, root, skip):
    """The two rate rows `_get_rates` looks at for `currency` on `date`: the last one on
    or before the date, else the earliest later one (company rows first). `skip` is a
    condition under which no lookup is needed (same currency on both sides)."""
    return f"""
    LEFT JOIN LATERAL (
        SELECT r.rate FROM res_currency_rate r
         WHERE NOT ({skip}) AND r.currency_id = {currency} AND r.name <= {date}
           AND (r.company_id IS NULL OR r.company_id = {root})
         ORDER BY r.company_id, r.name DESC LIMIT 1) {alias}_b ON TRUE
    LEFT JOIN LATERAL (
        SELECT r.rate FROM res_currency_rate r
         WHERE NOT ({skip}) AND {alias}_b.rate IS NULL AND r.currency_id = {currency}
           AND (r.company_id IS NULL OR r.company_id = {root})
         ORDER BY r.company_id, r.name ASC LIMIT 1) {alias}_a ON TRUE"""


def _conversion(alias, amount, source, target, company_currency):
    """Converted amount, factor and flags of one measure, as `_convert` would compute
    them, except that a currency other than the company's without any rate gives NULL
    and a missing flag instead of Odoo's silent 1.0."""
    same = f"({source} = {target})"
    sb, sa, tb, ta = (f"{alias}_s_b", f"{alias}_s_a", f"{alias}_t_b", f"{alias}_t_a")
    s_none = f"({sb}.rate IS NULL AND {sa}.rate IS NULL)"
    t_none = f"({tb}.rate IS NULL AND {ta}.rate IS NULL)"
    missing = (f"(NOT {same} AND (({s_none} AND {source} <> {company_currency}) "
               f"OR ({t_none} AND {target} <> {company_currency})))")
    rate = f"(COALESCE({tb}.rate, {ta}.rate, 1.0) / COALESCE({sb}.rate, {sa}.rate, 1.0))"
    factor = f"(CASE WHEN {same} THEN 1.0 WHEN {missing} THEN NULL ELSE {rate} END)"
    fallback = (f"(NOT {same} AND NOT {missing} AND (({sb}.rate IS NULL AND {sa}.rate IS NOT "
                f"NULL) OR ({tb}.rate IS NULL AND {ta}.rate IS NOT NULL)))")
    return {
        "value": f"(CASE WHEN {amount} = 0 THEN 0 ELSE {amount} * {factor} END)",
        "rate": f"(CASE WHEN {amount} IS NULL THEN NULL ELSE {factor} END)",
        # a zero or empty amount needs no rate
        "missing": f"(CASE WHEN COALESCE({amount}, 0) <> 0 AND {missing} THEN 1 ELSE 0 END)",
        "fallback": f"(CASE WHEN COALESCE({amount}, 0) <> 0 AND {fallback} THEN 1 ELSE 0 END)",
    }

def _measure(label, groups=None):
    """The columns of one converted measure (§3.3): converted amount, source amount,
    source currency, rate, rate date, « rate missing » and « later rate used » flags,
    and « known » (the ORM reads a NULL Float as 0.0: this flag tells an unknown amount
    from a real zero), all with the groups of the measure."""
    extra = {"groups": groups} if groups else {}
    return (
        fields.Float(string=label, readonly=True, **extra),
        fields.Float(string=f"{label} – Source Amount", readonly=True, aggregator=False,
                     **extra),
        fields.Many2one("res.currency", string=f"{label} – Source Currency", readonly=True,
                        **extra),
        fields.Float(string=f"{label} – Rate", readonly=True, digits=(16, 10),
                     aggregator=False, **extra),
        fields.Date(string=f"{label} – Rate Date", readonly=True, **extra),
        fields.Integer(string=f"{label} – Rate Missing", readonly=True, **extra),
        fields.Integer(string=f"{label} – Later Rate Used", readonly=True, **extra),
        fields.Integer(string=f"{label} – Known", readonly=True, **extra),
    )


class StockMonitor(models.Model):
    _name = "lartdubati.stock.monitor"
    _description = "Stock Monitor"
    _auto = False
    _order = "stock_name, family, product_name, id"
    _rec_name = "product_name"

    # identity and place
    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Stock Currency", readonly=True)
    family = fields.Selection([("asset", "Asset"), ("consumable", "Consumable")],
                              readonly=True)
    ownership_status = fields.Selection(OWNERSHIP_STATUS, readonly=True)
    place_type = fields.Selection(
        [("physical", "Physical"), ("lent_out", "Lent Out"), ("virtual", "Virtual")],
        readonly=True)
    product_name = fields.Char(string="Product", translate=True, readonly=True)
    category_name = fields.Char(string="Product Category", readonly=True)
    equipment_name = fields.Char(string="Equipment", translate=True, readonly=True)
    serial = fields.Char(string="Serial Number", readonly=True)
    stock_name = fields.Char(string="Stock", readonly=True)
    location_name = fields.Char(string="Location", readonly=True)
    country_name = fields.Char(string="Country", translate=True, readonly=True)
    state_name = fields.Char(string="State", readonly=True)
    city = fields.Char(readonly=True)
    uom_name = fields.Char(string="Unit", translate=True, readonly=True)
    warranty_status = fields.Selection(WARRANTY_STATUS, readonly=True)
    insurance_status = fields.Selection(INSURANCE_STATUS, readonly=True)
    asset_count = fields.Integer(string="Items", readonly=True)
    quantity = fields.Float(readonly=True, aggregator=False)
    replacement_value_date = fields.Date(readonly=True)

    # ids: rules, staff navigation and grouping
    stock_id = fields.Many2one("stock.location", string="Stock (record)", readonly=True,
                               groups=STAFF)
    location_id = fields.Many2one("stock.location", string="Location (record)",
                                  readonly=True, groups=STAFF)
    product_id = fields.Many2one("product.product", string="Product (record)",
                                 readonly=True, groups=STAFF)
    equipment_id = fields.Many2one("maintenance.equipment", string="Equipment (record)",
                                   readonly=True, groups=STAFF)
    lot_id = fields.Many2one("stock.lot", string="Serial Number (record)", readonly=True,
                             groups=STAFF)
    country_id = fields.Many2one("res.country", string="Country (record)", readonly=True,
                                 groups=STAFF)
    state_id = fields.Many2one("res.country.state", string="State (record)", readonly=True,
                               groups=STAFF)
    owner_partner_id = fields.Many2one("res.partner", string="Legal Owner", readonly=True,
                                       groups=STAFF)
    owner_name = fields.Char(string="Legal Owner Name", readonly=True, groups=STAFF)
    responsible_name = fields.Char(string="Responsible", readonly=True, groups=STAFF)
    lot_quant_count = fields.Integer(string="Positions of the Serial Number", readonly=True,
                                     groups=STAFF, aggregator=False)

    # asset state and provisional values
    asset_state = fields.Selection(
        [("draft", "Draft"), ("open", "Running"), ("close", "Close"), ("removed", "Removed")],
        readonly=True, groups=ACCOUNTANTS)
    accounting_provisional = fields.Integer(string="Provisional Net Book Value",
                                            readonly=True, groups=ACCOUNTANTS)
    inventory_provisional = fields.Integer(string="Provisional Inventory Value",
                                           readonly=True, groups=STAFF)

    # converted measures (§3.4-3.6)
    (inventory_value, inventory_value_source_amount,
     inventory_value_source_currency_id, inventory_value_rate,
     inventory_value_rate_date, inventory_value_rate_missing, inventory_value_rate_fallback,
     inventory_value_known) = _measure(
        "Inventory Value (excl. tax)")
    (replacement_value, replacement_value_source_amount,
     replacement_value_source_currency_id, replacement_value_rate,
     replacement_value_rate_date, replacement_value_rate_missing, replacement_value_rate_fallback,
     replacement_value_known) = _measure(
        "Replacement Value (excl. tax)")
    (stock_value, stock_value_source_amount,
     stock_value_source_currency_id, stock_value_rate,
     stock_value_rate_date, stock_value_rate_missing, stock_value_rate_fallback,
     stock_value_known) = _measure(
        "Stock Value (excl. tax)", STAFF)
    (original_value, original_value_source_amount,
     original_value_source_currency_id, original_value_rate,
     original_value_rate_date, original_value_rate_missing, original_value_rate_fallback,
     original_value_known) = _measure(
        "Original Value (excl. tax)", ACCOUNTANTS)
    (depreciated_value, depreciated_value_source_amount,
     depreciated_value_source_currency_id, depreciated_value_rate,
     depreciated_value_rate_date, depreciated_value_rate_missing, depreciated_value_rate_fallback,
     depreciated_value_known) = _measure(
        "Accumulated Depreciation", ACCOUNTANTS)
    (accounting_value, accounting_value_source_amount,
     accounting_value_source_currency_id, accounting_value_rate,
     accounting_value_rate_date, accounting_value_rate_missing, accounting_value_rate_fallback,
     accounting_value_known) = _measure(
        "Net Book Value", ACCOUNTANTS)
    (rent_monthly, rent_monthly_source_amount,
     rent_monthly_source_currency_id, rent_monthly_rate,
     rent_monthly_rate_date, rent_monthly_rate_missing, rent_monthly_rate_fallback,
     rent_monthly_known) = _measure(
        "Monthly Rent (excl. tax)", STAFF)

    # active rental line (staff)
    rent_amount = fields.Float(string="Rent per Period (excl. tax)", readonly=True,
                               groups=STAFF, aggregator=False)
    rent_currency_id = fields.Many2one("res.currency", string="Rent Currency", readonly=True,
                                       groups=STAFF)
    rent_rule_type = fields.Char(string="Rent Periodicity", readonly=True, groups=STAFF)
    rent_interval = fields.Integer(string="Rent Interval", readonly=True, groups=STAFF,
                                   aggregator=False)
    rent_start = fields.Date(readonly=True, groups=STAFF)
    rent_end = fields.Date(readonly=True, groups=STAFF)

    # rent paid (accountants), converted bill line by bill line
    rent_paid = fields.Float(string="Rent Paid (excl. tax)", readonly=True,
                             groups=ACCOUNTANTS)
    rent_paid_source_amount = fields.Float(string="Rent Paid (excl. tax, company currency)",
                                           readonly=True, groups=ACCOUNTANTS)
    rent_paid_rate_missing = fields.Integer(string="Rent Paid – Rate Missing", readonly=True,
                                            groups=ACCOUNTANTS)
    rent_paid_rate_fallback = fields.Integer(string="Rent Paid – Later Rate Used",
                                             readonly=True, groups=ACCOUNTANTS)

    # alerts (§3.7): 0/1 integers, summed by read_group
    alert_rate_missing = fields.Integer(string="Rate Missing", readonly=True, groups=STAFF)
    alert_integrity = fields.Integer(string="Integrity", readonly=True, groups=STAFF)
    alert_no_position = fields.Integer(string="No Position", readonly=True, groups=STAFF)
    alert_negative_quantity = fields.Integer(string="Negative Quantity", readonly=True,
                                             groups=STAFF)
    alert_cost_missing = fields.Integer(string="Cost Missing", readonly=True, groups=STAFF)
    alert_outside_stock = fields.Integer(string="Outside Any Monitor Stock", readonly=True,
                                         groups=STAFF)
    alert_rental_ended = fields.Integer(string="Rental Ended", readonly=True, groups=STAFF)
    alert_asset_removed = fields.Integer(string="Fixed Asset Removed", readonly=True,
                                         groups=ACCOUNTANTS)
    alert_asset_missing = fields.Integer(string="Fixed Asset Missing", readonly=True,
                                         groups=ACCOUNTANTS)
    alert_replacement_missing = fields.Integer(string="Replacement Value Missing",
                                               readonly=True, groups=STAFF)
    alert_replacement_old = fields.Integer(string="Replacement Value Too Old",
                                           readonly=True, groups=STAFF)
    alert_lent_uninsured = fields.Integer(string="Lent Out Uninsured", readonly=True,
                                          groups=STAFF)
    alert_rent_period_unsupported = fields.Integer(string="Rent Periodicity Unsupported",
                                                   readonly=True, groups=STAFF)
    alert_no_asset = fields.Integer(string="No Fixed Asset (Expensed)", readonly=True,
                                    groups=STAFF)
    alert_no_responsible = fields.Integer(string="No Responsible", readonly=True,
                                          groups=STAFF)
    alert_count = fields.Integer(string="Alerts", readonly=True, groups=STAFF)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"CREATE OR REPLACE VIEW {self._table} AS ({self._query()})")

    # ------------------------------------------------------------------ SQL

    def _query(self):
        avco = _company_dependent("pp.standard_price", "product.product", "standard_price",
                                  "src.company_id", "numeric")
        valuation = _company_dependent("pc.property_valuation", "product.category",
                                       "property_valuation", "src.company_id", "text")
        joins, selects, missing = [], [], []
        for name, short in MEASURES.items():
            amount = f"b.{short}_amount"
            source, date = f"b.{short}_currency", f"b.{short}_date"
            skip = f"{source} IS NULL OR {source} = b.target_currency"
            joins.append(_rate_joins(f"{short}_s", source, date, "b.root_company", skip))
            joins.append(_rate_joins(f"{short}_t", "b.target_currency", date,
                                     "b.root_company", skip))
            conv = _conversion(short, amount, source, "b.target_currency",
                               "b.company_currency")
            missing.append(conv["missing"])
            selects.append(f"""
           {conv['value']} AS {name},
           {amount} AS {name}_source_amount,
           (CASE WHEN {amount} IS NULL THEN NULL ELSE {source} END)
               AS {name}_source_currency_id,
           {conv['rate']} AS {name}_rate,
           (CASE WHEN {amount} IS NULL THEN NULL ELSE {date} END) AS {name}_rate_date,
           {conv['missing']} AS {name}_rate_missing,
           {conv['fallback']} AS {name}_rate_fallback,
           (CASE WHEN {conv['value']} IS NULL THEN 0 ELSE 1 END) AS {name}_known""")
        alert_sum = " + ".join(f"alerts.{name}" for name in ALERTS)
        return f"""
WITH stocks AS (
    SELECT l.id, l.parent_path, l.complete_name, l.monitor_currency_id, l.address_id
      FROM stock_location l
     WHERE l.is_monitor_stock AND l.active AND l.usage = 'internal'
),
lot_position AS (
    -- one position per serial: the largest positive internal quant, then the lowest id
    SELECT DISTINCT ON (q.lot_id) q.lot_id, q.location_id,
           count(*) OVER (PARTITION BY q.lot_id) AS lot_quant_count
      FROM stock_quant q JOIN stock_location l ON l.id = q.location_id
     WHERE l.usage = 'internal' AND q.quantity > 0 AND q.lot_id IS NOT NULL
     ORDER BY q.lot_id, q.quantity DESC, q.id
),
rental AS (
    -- the active rental line of a supplier contract (unique: phase 1 overlap rule)
    SELECT DISTINCT ON (cl.equipment_id) cl.equipment_id, cl.specific_price,
           cl.quantity, cl.discount, cl.recurring_rule_type, cl.recurring_interval,
           cl.date_start, cl.date_end, cc.equipment_currency_id
      FROM contract_line cl JOIN contract_contract cc ON cc.id = cl.contract_id
     WHERE cl.equipment_id IS NOT NULL AND cl.equipment_nature = 'rental'
       AND cc.contract_type = 'purchase' AND NOT COALESCE(cl.is_canceled, FALSE)
       AND COALESCE(cl.active, TRUE) AND COALESCE(cc.active, TRUE)
       AND cl.date_start <= CURRENT_DATE
       AND (cl.date_end IS NULL OR cl.date_end >= CURRENT_DATE)
     ORDER BY cl.equipment_id, cl.date_start DESC, cl.id DESC
),
last_rental AS (
    SELECT DISTINCT ON (cl.equipment_id) cl.equipment_id, cl.date_end
      FROM contract_line cl JOIN contract_contract cc ON cc.id = cl.contract_id
     WHERE cl.equipment_id IS NOT NULL AND cl.equipment_nature = 'rental'
       AND cc.contract_type = 'purchase' AND NOT COALESCE(cl.is_canceled, FALSE)
     ORDER BY cl.equipment_id, cl.date_start DESC, cl.id DESC
),
equipment_rows AS (
    SELECT e.id * 2 AS id, 'asset' AS family, e.id AS equipment_id,
           e.company_id, e.product_id, e.stock_lot_id AS lot_id,
           (CASE WHEN e.stock_lot_id IS NOT NULL THEN lp.location_id
                 ELSE e.current_location_id END) AS location_id,
           e.ownership_status, e.owner_partner_id, e.owner_user_id,
           1.0 AS quantity, 1 AS asset_count, e.name AS equipment_name,
           COALESCE(lot.name, e.serial_no) AS serial,
           e.warranty_status, e.insurance_status,
           e.cost AS raw_cost, COALESCE(e.cost_known, FALSE) AS cost_known,
           e.cost_date AS raw_cost_date, COALESCE(e.cost_provisional, FALSE) AS cost_provisional,
           NULLIF(e.replacement_value, 0) AS raw_replacement,
           e.replacement_currency_id AS raw_replacement_currency,
           e.replacement_value_date, e.asset_id AS raw_asset_id,
           (e.stock_lot_id IS NOT NULL AND lp.lot_id IS NULL) AS no_lot_position,
           COALESCE(lp.lot_quant_count, 0) AS lot_quant_count,
           FALSE AS third_party_quant
      FROM maintenance_equipment e
      LEFT JOIN lot_position lp ON lp.lot_id = e.stock_lot_id
      LEFT JOIN stock_lot lot ON lot.id = e.stock_lot_id
     WHERE e.active AND e.integration_state = 'done'
),
consumable_rows AS (
    SELECT q.id * 2 + 1 AS id, 'consumable' AS family, NULL::integer AS equipment_id,
           q.company_id, q.product_id, q.lot_id, q.location_id,
           'owned' AS ownership_status, NULL::integer AS owner_partner_id,
           NULL::integer AS owner_user_id, q.quantity, 0 AS asset_count,
           NULL::jsonb AS equipment_name, lot.name AS serial,
           NULL AS warranty_status, NULL AS insurance_status,
           NULL::double precision AS raw_cost, FALSE AS cost_known,
           NULL::date AS raw_cost_date, FALSE AS cost_provisional,
           NULL::double precision AS raw_replacement,
           NULL::integer AS raw_replacement_currency, NULL::date AS replacement_value_date,
           NULL::integer AS raw_asset_id, FALSE AS no_lot_position, 0 AS lot_quant_count,
           (q.owner_id IS NOT NULL AND q.owner_id <> c.partner_id) AS third_party_quant
      FROM stock_quant q
      JOIN stock_location l ON l.id = q.location_id
      JOIN product_product pp ON pp.id = q.product_id
      JOIN product_template pt ON pt.id = pp.product_tmpl_id
      JOIN res_company c ON c.id = q.company_id
      LEFT JOIN stock_lot lot ON lot.id = q.lot_id
     WHERE l.usage = 'internal' AND q.quantity <> 0
       AND NOT COALESCE(pt.maintenance_ok, FALSE)
),
source_rows AS (
    SELECT * FROM equipment_rows UNION ALL SELECT * FROM consumable_rows
),
placed AS (
    -- stock = nearest monitor stock at or above the location (parent_path prefix)
    SELECT src.*, s.id AS stock_id, s.complete_name AS stock_name,
           loc.complete_name AS location_name, loc.place_type,
           c.currency_id AS company_currency,
           split_part(c.parent_path, '/', 1)::integer AS root_company,
           COALESCE(s.monitor_currency_id, c.currency_id) AS target_currency,
           (c.stock_monitor_currency_mode = 'latest') AS latest_mode,
           addr.country_id, addr.state_id, addr.city,
           pt.name AS product_name, pt.uom_id, pc.complete_name AS category_name,
           COALESCE(pc.is_fixed_asset_stock, FALSE) AS fixed_asset_category,
           COALESCE(({valuation}) = 'real_time', FALSE) AS automated_valuation,
           COALESCE({avco}, 0) AS avco
      FROM source_rows src
      JOIN res_company c ON c.id = src.company_id
      LEFT JOIN stock_location loc ON loc.id = src.location_id
      LEFT JOIN LATERAL (
          SELECT st.* FROM stocks st
           WHERE loc.parent_path LIKE st.parent_path || '%'
           ORDER BY length(st.parent_path) DESC LIMIT 1) s ON TRUE
      LEFT JOIN res_partner addr ON addr.id = s.address_id
      LEFT JOIN product_product pp ON pp.id = src.product_id
      LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
      LEFT JOIN product_category pc ON pc.id = pt.categ_id
),
valued AS (
    SELECT p.*, a.state AS raw_asset_state, a.purchase_value, a.value_depreciated,
           a.date_start AS asset_date,
           rl.specific_price * rl.quantity * (1 - COALESCE(rl.discount, 0) / 100.0)
               AS rent_amount,
           rl.equipment_currency_id AS rent_currency_id,
           rl.recurring_rule_type AS rent_rule_type, rl.recurring_interval AS rent_interval,
           rl.date_start AS rent_start, rl.date_end AS rent_end,
           (CASE rl.recurring_rule_type
                 WHEN 'monthly' THEN 1 WHEN 'monthlylastday' THEN 1
                 WHEN 'quarterly' THEN 3 WHEN 'semesterly' THEN 6 WHEN 'yearly' THEN 12
            END) * NULLIF(rl.recurring_interval, 0) AS rent_months,
           lr.date_end AS last_rental_end,
           (p.family = 'asset' AND p.ownership_status IN ('owned', 'lent_out'))
               AS company_asset,
           (p.family = 'asset' AND p.ownership_status IN ('borrowed', 'rented'))
               AS third_party_asset
      FROM placed p
      LEFT JOIN account_asset a ON a.id = p.raw_asset_id
      LEFT JOIN rental rl ON rl.equipment_id = p.equipment_id
      LEFT JOIN last_rental lr ON lr.equipment_id = p.equipment_id
),
b AS (
    -- source amount, currency and date of each measure (§3.4, §3.5)
    SELECT v.*,
        (v.company_asset AND v.raw_asset_id IS NOT NULL) AS with_asset,
        (CASE WHEN v.family = 'consumable' THEN v.quantity * v.avco
              WHEN v.company_asset AND v.raw_asset_id IS NOT NULL THEN v.purchase_value
              WHEN v.company_asset THEN (CASE WHEN v.cost_known THEN v.raw_cost END)
              ELSE v.raw_replacement END) AS inventory_amount,
        (CASE WHEN v.third_party_asset THEN v.raw_replacement_currency
              ELSE v.company_currency END) AS inventory_currency,
        (CASE WHEN v.latest_mode OR v.family = 'consumable' THEN CURRENT_DATE
              WHEN v.company_asset AND v.raw_asset_id IS NOT NULL THEN v.asset_date
              WHEN v.company_asset THEN v.raw_cost_date
              ELSE v.replacement_value_date END) AS inventory_date,
        v.raw_replacement AS replacement_amount,
        v.raw_replacement_currency AS replacement_currency,
        (CASE WHEN v.latest_mode THEN CURRENT_DATE ELSE v.replacement_value_date END)
            AS replacement_date,
        (CASE WHEN v.family = 'consumable' AND v.automated_valuation
                   THEN v.quantity * v.avco
              WHEN v.company_asset AND v.raw_asset_id IS NULL AND NOT v.fixed_asset_category
                   AND v.automated_valuation THEN v.avco
              ELSE 0 END) AS stock_amount,
        v.company_currency AS stock_currency, CURRENT_DATE AS stock_date,
        (CASE WHEN v.company_asset AND v.raw_asset_id IS NOT NULL THEN v.purchase_value END)
            AS original_amount,
        v.company_currency AS original_currency,
        (CASE WHEN v.latest_mode THEN CURRENT_DATE ELSE v.asset_date END) AS original_date,
        (CASE WHEN v.company_asset AND v.raw_asset_id IS NOT NULL
              THEN COALESCE(v.value_depreciated, 0) END) AS depreciated_amount,
        v.company_currency AS depreciated_currency,
        (CASE WHEN v.latest_mode THEN CURRENT_DATE ELSE v.asset_date END)
            AS depreciated_date,
        -- net book value: purchase value minus depreciation (the salvage value stays)
        (CASE WHEN v.family = 'consumable' AND v.automated_valuation
                   THEN v.quantity * v.avco
              WHEN v.company_asset AND v.raw_asset_id IS NOT NULL THEN
                   (CASE WHEN v.raw_asset_state = 'removed' THEN 0
                         ELSE v.purchase_value - COALESCE(v.value_depreciated, 0) END)
              WHEN v.company_asset AND NOT v.fixed_asset_category AND v.automated_valuation
                   THEN v.avco
              ELSE 0 END) AS accounting_amount,
        v.company_currency AS accounting_currency,
        (CASE WHEN NOT v.latest_mode AND v.company_asset AND v.raw_asset_id IS NOT NULL
              THEN v.asset_date ELSE CURRENT_DATE END) AS accounting_date,
        (v.rent_amount / v.rent_months) AS rent_m_amount,
        v.rent_currency_id AS rent_m_currency,
        (CASE WHEN v.latest_mode THEN CURRENT_DATE ELSE v.rent_start END) AS rent_m_date
      FROM valued v
),
measured AS (
    SELECT b.*, b.target_currency AS currency_id,
           {",".join(selects)},
           rp.converted AS rent_paid, rp.source_amount AS rent_paid_source_amount,
           COALESCE(rp.missing, 0) AS rent_paid_rate_missing,
           COALESCE(rp.fallback, 0) AS rent_paid_rate_fallback,
           (CASE WHEN ({" + ".join(missing)}) + COALESCE(rp.missing, 0) > 0
                 THEN 1 ELSE 0 END) AS any_rate_missing
      FROM b
      {"".join(joins)}
      {self._rent_paid_join()}
)
SELECT m.*,
       country.name AS country_name, state.name AS state_name, uom.name AS uom_name,
       owner.name AS owner_name, responsible.name AS responsible_name,
       (CASE WHEN m.company_asset THEN m.raw_asset_state END) AS asset_state,
       (CASE WHEN m.with_asset AND m.raw_asset_state = 'draft' THEN 1 ELSE 0 END)
           AS accounting_provisional,
       (CASE WHEN m.company_asset AND m.raw_asset_id IS NULL AND m.cost_known
                  AND m.cost_provisional THEN 1 ELSE 0 END) AS inventory_provisional,
       alerts.*,
       ({alert_sum}) AS alert_count
  FROM measured m
  LEFT JOIN res_country country ON country.id = m.country_id
  LEFT JOIN res_country_state state ON state.id = m.state_id
  LEFT JOIN uom_uom uom ON uom.id = m.uom_id
  LEFT JOIN res_partner owner ON owner.id = m.owner_partner_id
  LEFT JOIN res_users ru ON ru.id = m.owner_user_id
  LEFT JOIN res_partner responsible ON responsible.id = ru.partner_id
  JOIN res_company co ON co.id = m.company_id
  CROSS JOIN LATERAL (SELECT
       m.any_rate_missing AS alert_rate_missing,
       (CASE WHEN m.lot_quant_count > 1 OR m.third_party_quant THEN 1 ELSE 0 END)
           AS alert_integrity,
       (CASE WHEN m.no_lot_position OR (m.family = 'asset' AND m.location_id IS NULL)
             THEN 1 ELSE 0 END) AS alert_no_position,
       (CASE WHEN m.quantity < 0 THEN 1 ELSE 0 END) AS alert_negative_quantity,
       (CASE WHEN m.company_asset AND m.raw_asset_id IS NULL AND NOT m.cost_known
             THEN 1 ELSE 0 END) AS alert_cost_missing,
       (CASE WHEN m.location_id IS NOT NULL AND m.stock_id IS NULL THEN 1 ELSE 0 END)
           AS alert_outside_stock,
       (CASE WHEN m.ownership_status = 'rented' AND m.rent_start IS NULL
                  AND m.last_rental_end < CURRENT_DATE THEN 1 ELSE 0 END)
           AS alert_rental_ended,
       (CASE WHEN m.with_asset AND m.raw_asset_state = 'removed' THEN 1 ELSE 0 END)
           AS alert_asset_removed,
       (CASE WHEN m.company_asset AND m.raw_asset_id IS NULL AND m.fixed_asset_category
             THEN 1 ELSE 0 END) AS alert_asset_missing,
       (CASE WHEN m.third_party_asset AND m.raw_replacement IS NULL THEN 1 ELSE 0 END)
           AS alert_replacement_missing,
       (CASE WHEN m.third_party_asset AND m.raw_replacement IS NOT NULL
                  AND (m.replacement_value_date IS NULL OR m.replacement_value_date
                       < CURRENT_DATE - make_interval(months =>
                           COALESCE(co.stock_monitor_replacement_max_age, 12)))
             THEN 1 ELSE 0 END) AS alert_replacement_old,
       (CASE WHEN m.ownership_status = 'lent_out'
                  AND COALESCE(m.insurance_status, '') <> 'insured' THEN 1 ELSE 0 END)
           AS alert_lent_uninsured,
       (CASE WHEN m.rent_start IS NOT NULL AND m.rent_months IS NULL THEN 1 ELSE 0 END)
           AS alert_rent_period_unsupported,
       (CASE WHEN m.company_asset AND m.raw_asset_id IS NULL AND NOT m.fixed_asset_category
                  AND NOT m.automated_valuation THEN 1 ELSE 0 END) AS alert_no_asset,
       (CASE WHEN m.family = 'asset' AND m.owner_user_id IS NULL THEN 1 ELSE 0 END)
           AS alert_no_responsible) alerts
"""

    def _rent_paid_join(self):
        """Rent paid: posted supplier bill and refund product lines linked to a rental
        line of the equipment on a supplier contract, each converted at its own date."""
        date = "(CASE WHEN b.latest_mode THEN CURRENT_DATE ELSE aml.date END)"
        skip = "b.company_currency = b.target_currency"
        conv = _conversion("rp", "aml.balance", "b.company_currency", "b.target_currency",
                           "b.company_currency")
        return f"""
  LEFT JOIN LATERAL (
      SELECT SUM(aml.balance) AS source_amount,
             (CASE WHEN bool_or({conv['missing']} = 1) THEN NULL
                   ELSE SUM({conv['value']}) END) AS converted,
             max({conv['missing']}) AS missing, max({conv['fallback']}) AS fallback
        FROM account_move_line aml
        JOIN account_move am ON am.id = aml.move_id
        JOIN contract_line cl ON cl.id = aml.contract_line_id
        JOIN contract_contract cc ON cc.id = cl.contract_id
        {_rate_joins("rp_s", "b.company_currency", date, "b.root_company", skip)}
        {_rate_joins("rp_t", "b.target_currency", date, "b.root_company", skip)}
       WHERE b.equipment_id IS NOT NULL AND cl.equipment_id = b.equipment_id
         AND cl.equipment_nature = 'rental' AND cc.contract_type = 'purchase'
         AND aml.parent_state = 'posted' AND aml.display_type = 'product'
         AND am.move_type IN ('in_invoice', 'in_refund')
       HAVING count(*) > 0) rp ON TRUE"""

    # ------------------------------------------------------------------ dashboard

    def _readable(self, names):
        return [name for name in names if self._fields[name].is_accessible(self.env)]

    @api.model
    def _dashboard_domain(self, filters, skip=()):
        """Domain of the dashboard filters (§4.3). `filters` holds only the keys of
        FILTER_TYPES, with values of their type; anything else is refused. `skip`:
        keys left out (counts of a filter ignore the filter itself)."""
        if not isinstance(filters, dict):
            raise UserError(_("Invalid dashboard filters."))
        for key, value in filters.items():
            kind = FILTER_TYPES.get(key)
            if kind is None or not isinstance(value, kind) or (
                    kind is list and not all(isinstance(item, str) for item in value)):
                raise UserError(_("Invalid dashboard filter: %s", key))
        alert = filters.get("alert")
        if alert and alert not in self._dashboard_alerts():
            raise UserError(_("Invalid dashboard filter: %s", "alert"))
        domain = []
        if filters.get("countries") and "countries" not in skip:
            domain.append([("country_name", "in", filters["countries"])])
        if filters.get("cities") and "cities" not in skip:
            domain.append([("city", "in", filters["cities"])])
        if filters.get("stocks") and "stocks" not in skip:
            stocks = [name for name in filters["stocks"] if name != OUTSIDE_STOCK]
            parts = [[("stock_name", "in", stocks)]] if stocks else []
            if OUTSIDE_STOCK in filters["stocks"]:
                parts.append([("stock_name", "=", False)])
            domain.append(expression.OR(parts))
        if filters.get("families") and "families" not in skip:
            domain.append([("family", "in", filters["families"])])
        if filters.get("ownerships") and "ownerships" not in skip:
            domain.append([("ownership_status", "in", filters["ownerships"])])
        if alert and "alert" not in skip:
            domain.append([(alert, "=", 1)])
        term = (filters.get("search") or "").strip()
        if term and "search" not in skip:
            domain.append(expression.OR([[(name, "ilike", term)] for name in SEARCH_FIELDS]))
        return expression.AND(domain) if domain else []

    @api.model
    def _dashboard_alerts(self):
        """Alert columns the user may read (whitelist of the alert filter)."""
        return self._readable(list(ALERTS) + list(PUBLIC_RATE_ALERTS))

    @api.model
    def get_dashboard_data(self, filters=None):
        """Every aggregate of the dashboard in one call (§4.3), under the user's rights
        and record rules, without sudo. Only the fields the user may read are summed or
        returned. The list page is read separately with the returned domain."""
        filters = filters or {}
        domain = self._dashboard_domain(filters)
        measures = self._readable(list(MEASURES))
        alerts = self._dashboard_alerts()
        staff = self._fields["stock_id"].is_accessible(self.env)

        def by_currency(rows, key="currency_id"):
            return [{"currency_id": currency.id, "amount": amount}
                    for currency, amount in rows if currency]

        # 1. totals per currency, provisional and missing counts
        # « known » counts: a currency whose amounts are all unknown has no total line
        # (read_group returns 0, not NULL, for a sum of NULLs)
        aggregates = ["__count", "asset_count:sum"] + [f"{m}:sum" for m in measures] + [
            f"{m}_rate_missing:sum" for m in measures] + [f"{m}_known:sum" for m in measures]
        if "rent_paid" in self._readable(["rent_paid"]):
            aggregates += ["rent_paid:sum", "rent_paid_rate_missing:sum"]
        if "accounting_value" in measures:
            aggregates.append("accounting_provisional:sum")
        totals = {name: {"lines": [], "missing": [], "provisional": []}
                  for name in measures + self._readable(["rent_paid"])}
        count = assets = 0
        missing_counts = {}
        provisional_count = 0
        for currency, *values in self._read_group(domain, ["currency_id"], aggregates):
            result = dict(zip(aggregates, values))
            count += result["__count"]
            assets += result["asset_count:sum"] or 0
            for name in totals:
                known = result.get(f"{name}_known:sum", 1)  # rent_paid: per bill line
                if name == "rent_paid":
                    known = result.get("rent_paid:sum") is not None and (
                        result["__count"] > (result.get("rent_paid_rate_missing:sum") or 0))
                if currency and known and result.get(f"{name}:sum") is not None:
                    totals[name]["lines"].append(
                        {"currency_id": currency.id, "amount": result[f"{name}:sum"]})
                missing_counts[name] = (missing_counts.get(name, 0)
                                        + (result.get(f"{name}_rate_missing:sum") or 0))
            provisional_count += result.get("accounting_provisional:sum") or 0
        # unconverted amounts, in their source currency (only when some are missing)
        for name, missing in missing_counts.items():
            if not missing:
                continue
            if name == "rent_paid":
                rows = self._read_group(domain + [("rent_paid_rate_missing", "=", 1)],
                                        ["currency_id"], ["rent_paid_source_amount:sum"])
                totals[name]["missing"] = [
                    {"currency_id": self.env.company.currency_id.id, "amount": amount}
                    for _currency, amount in rows]
                continue
            rows = self._read_group(domain + [(f"{name}_rate_missing", "=", 1)],
                                    [f"{name}_source_currency_id"],
                                    [f"{name}_source_amount:sum"])
            totals[name]["missing"] = by_currency(rows)
        if provisional_count:
            rows = self._read_group(domain + [("accounting_provisional", "=", 1)],
                                    ["currency_id"], ["accounting_value:sum"])
            totals["accounting_value"]["provisional"] = by_currency(rows)

        # 2. stock cards: the selection's geography, family and ownership, every stock
        card_domain = self._dashboard_domain(filters, skip=("stocks", "alert", "search"))
        card_aggregates = ["__count", "asset_count:sum", "inventory_value:sum",
                           "inventory_value_rate_missing:sum"]
        if self._readable(["alert_count"]):
            card_aggregates.append("alert_count:sum")
        stocks = []
        for name, city, country, place, currency, *values in self._read_group(
                card_domain, ["stock_name", "city", "country_name", "place_type", "currency_id"],
                card_aggregates):
            result = dict(zip(card_aggregates, values))
            stocks.append({
                "name": name or OUTSIDE_STOCK, "city": city or "", "country": country or "",
                "place_type": place or "", "currency_id": currency.id,
                "count": result["__count"], "assets": result["asset_count:sum"] or 0,
                "inventory_value": result["inventory_value:sum"] or 0.0,
                "missing": result["inventory_value_rate_missing:sum"] or 0,
                "alerts": result.get("alert_count:sum") or 0,
            })

        # 3. alert counts: the selection without the alert filter and the search
        alert_counts = {}
        if alerts:
            alert_domain = self._dashboard_domain(filters, skip=("alert", "search"))
            values = self._read_group(alert_domain, [], [f"{a}:sum" for a in alerts])[0]
            alert_counts = {a: value or 0 for a, value in zip(alerts, values)}

        # 4. counts of the family segment and the ownership chips
        segment_domain = self._dashboard_domain(
            filters, skip=("families", "ownerships", "alert", "search"))
        segments = [{"family": family, "ownership": ownership, "count": number}
                    for family, ownership, number in self._read_group(
                        segment_domain, ["family", "ownership_status"], ["__count"])]

        # 5. choices of the selectors: every stock the user may see
        choices = [{"country": country or "", "city": city or "",
                    "stock": name or OUTSIDE_STOCK, "currency_id": currency.id}
                   for country, city, name, currency, _count in self._read_group(
                       [], ["country_name", "city", "stock_name", "currency_id"], ["__count"])]

        # 6. controls outside the monitor (point 14), staff only, under their own rights
        controls = {}
        if staff:
            Equipment = self.env["maintenance.equipment"]
            if Equipment.has_access("read"):
                controls["to_complete"] = Equipment.search_count(
                    [("integration_state", "!=", "done")])
            Lot = self.env["stock.lot"]
            if Lot.has_access("read"):
                controls["serial_without_equipment"] = Lot.search_count([
                    ("product_id.maintenance_ok", "=", True),
                    ("quant_ids.quantity", ">", 0),
                    ("quant_ids.location_id.usage", "=", "internal"),
                    ("equipment_ids", "=", False),
                ])
        return {
            "domain": domain, "count": count, "assets": assets, "totals": totals,
            "stocks": stocks, "alerts": alert_counts, "segments": segments,
            "choices": choices, "controls": controls, "staff": staff,
            "date": fields.Date.context_today(self),
        }

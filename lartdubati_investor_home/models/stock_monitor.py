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


def _company_default(model, field, company, cast):
    """Fallback Odoo uses for a company-dependent field without a value for `company`
    (ir.default of the company, then the global one: _get_model_defaults)."""
    return f"""(SELECT (d.json_value::jsonb #>> '{{}}')::{cast}
           FROM ir_default d JOIN ir_model_fields f ON f.id = d.field_id
          WHERE f.model = '{model}' AND f.name = '{field}' AND d.user_id IS NULL
            AND d.condition IS NULL AND (d.company_id = {company} OR d.company_id IS NULL)
          ORDER BY d.company_id NULLS LAST, d.id LIMIT 1)"""


def _rate_join(alias, currency, date, root):
    """Join the rate point of `currency` on `date` (computed once in point_rates)."""
    return (f"\n      LEFT JOIN point_rates {alias} ON {alias}.currency = {currency} "
            f"AND {alias}.date = {date} AND {alias}.root = {root}")


def _conversion(alias, amount, source, target, company_currency):
    """Converted amount, factor and flags of one measure, as `_convert` would compute
    them (rate(target) / rate(source), rates as `_get_rates` finds them), except that a
    currency other than the company's without any rate gives NULL and a missing flag
    instead of Odoo's silent 1.0. `{alias}_s` and `{alias}_t` are the rate points of
    the source and target currencies."""
    same = f"({source} = {target})"
    s, t = f"{alias}_s", f"{alias}_t"
    s_none = f"({s}.rate_before IS NULL AND {s}.rate_after IS NULL)"
    t_none = f"({t}.rate_before IS NULL AND {t}.rate_after IS NULL)"
    missing = (f"(NOT {same} AND (({s_none} AND {source} <> {company_currency}) "
               f"OR ({t_none} AND {target} <> {company_currency})))")
    rate = (f"(COALESCE({t}.rate_before, {t}.rate_after, 1.0) "
            f"/ COALESCE({s}.rate_before, {s}.rate_after, 1.0))")
    factor = f"(CASE WHEN {same} THEN 1.0 WHEN {missing} THEN NULL ELSE {rate} END)"
    fallback = (f"(NOT {same} AND NOT {missing} AND (({s}.rate_before IS NULL AND "
                f"{s}.rate_after IS NOT NULL) OR ({t}.rate_before IS NULL AND "
                f"{t}.rate_after IS NOT NULL)))")
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
    rent_paid_known = fields.Integer(string="Rent Paid – Known", readonly=True,
                                     groups=ACCOUNTANTS)
    rent_paid_rate_fallback = fields.Integer(string="Rent Paid – Later Rate Used",
                                             readonly=True, groups=ACCOUNTANTS)

    # alerts (§3.7): 0/1 integers, summed by read_group
    alert_rate_missing = fields.Integer(string="Rate Missing", readonly=True, groups=STAFF,
        help="An amount could not be converted into the stock's currency: it stays in its own "
        "currency, outside the totals.")
    alert_integrity = fields.Integer(string="Integrity", readonly=True, groups=STAFF,
        help="Several positive internal quants for one serial number, or a consumable held for"
        " a third party: one row, values counted once.")
    alert_no_position = fields.Integer(string="No Position", readonly=True, groups=STAFF,
        help="Serial number without any positive quant in an internal location, or non-stock "
        "equipment without a location.")
    alert_negative_quantity = fields.Integer(string="Negative Quantity", readonly=True,
                                             groups=STAFF,
        help="Negative quantity on hand, valued as the stock valuation does.")
    alert_cost_missing = fields.Integer(string="Cost Missing", readonly=True, groups=STAFF,
        help="Company equipment without a fixed asset and without a known cost.")
    alert_outside_stock = fields.Integer(string="Outside Any Monitor Stock", readonly=True,
                                         groups=STAFF,
        help="Internal location without any monitor stock above it.")
    alert_rental_ended = fields.Integer(string="Rental Ended", readonly=True, groups=STAFF,
        help="The rental contract has ended but the item is still in stock.")
    alert_asset_removed = fields.Integer(string="Fixed Asset Removed", readonly=True,
                                         groups=ACCOUNTANTS,
        help="The fixed asset is removed but the item is still in stock.")
    alert_asset_missing = fields.Integer(string="Fixed Asset Missing", readonly=True,
                                         groups=ACCOUNTANTS,
        help="Fixed-asset category without a fixed asset (bill not posted yet).")
    alert_replacement_missing = fields.Integer(string="Replacement Value Missing",
                                               readonly=True, groups=STAFF,
        help="Mandatory for a borrowed or rented item.")
    alert_replacement_old = fields.Integer(string="Replacement Value Too Old",
                                           readonly=True, groups=STAFF,
        help="Older than the validity set in the settings.")
    alert_lent_uninsured = fields.Integer(string="Lent Out Uninsured", readonly=True,
                                          groups=STAFF,
        help="Company property held by a third party, not insured.")
    alert_rent_period_unsupported = fields.Integer(string="Rent Periodicity Unsupported",
                                                   readonly=True, groups=STAFF,
        help="Weekly or daily rent: no monthly equivalent, left out of the current rents.")
    alert_no_asset = fields.Integer(string="No Fixed Asset (Expensed)", readonly=True,
                                    groups=STAFF,
        help="Category without fixed asset: expensed, no accounting value.")
    alert_no_responsible = fields.Integer(string="No Responsible", readonly=True,
                                          groups=STAFF,
        help="An integrated equipment needs a responsible.")
    alert_count = fields.Integer(string="Alerts", readonly=True, groups=STAFF)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"CREATE OR REPLACE VIEW {self._table} AS ({self._query()})")

    # ------------------------------------------------------------------ SQL

    def _query(self):
        # company-dependent values (jsonb by company), with their fallbacks computed once
        # per company in company_defaults
        avco = ("COALESCE((pp.standard_price ->> src.company_id::text)::numeric, "
                "(SELECT cd.avco_default FROM company_defaults cd "
                "WHERE cd.company_id = src.company_id))")
        valuation = ("COALESCE(pc.property_valuation ->> src.company_id::text, "
                     "(SELECT cd.valuation_default FROM company_defaults cd "
                     "WHERE cd.company_id = src.company_id))")
        joins, selects, missing, points = [], [], [], []
        for name, short in MEASURES.items():
            amount = f"b.{short}_amount"
            source, date = f"b.{short}_currency", f"b.{short}_date"
            # the rate points a conversion needs: none when no amount or same currency
            needed = f"COALESCE({amount}, 0) <> 0 AND {source} <> b.target_currency"
            points.append(f"SELECT {source}, {date}, b.root_company FROM b WHERE {needed}")
            points.append(f"SELECT b.target_currency, {date}, b.root_company FROM b "
                          f"WHERE {needed}")
            joins.append(_rate_join(f"{short}_s", source, date, "b.root_company"))
            joins.append(_rate_join(f"{short}_t", "b.target_currency", date,
                                    "b.root_company"))
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
        # rent paid: each bill line at its own date
        rent_needed = "b.company_currency <> b.target_currency"
        points.append(f"SELECT b.company_currency, rl.date, b.root_company FROM rent_lines rl "
                      f"JOIN b ON b.id = rl.row_id WHERE {rent_needed}")
        points.append(f"SELECT b.target_currency, rl.date, b.root_company FROM rent_lines rl "
                      f"JOIN b ON b.id = rl.row_id WHERE {rent_needed}")
        rent_conv = _conversion("rp", "rl.balance", "b.company_currency", "b.target_currency",
                                "b.company_currency")
        alert_sum = " + ".join(ALERTS)
        return f"""
WITH company_defaults AS MATERIALIZED (
    -- fallbacks of the company-dependent fields, computed once per company and read
    -- through scalar subqueries (a join on a materialized CTE spoils the row estimates)
    SELECT c.id AS company_id,
           {_company_default("product.product", "standard_price", "c.id", "numeric")}
               AS avco_default,
           {_company_default("product.category", "property_valuation", "c.id", "text")}
               AS valuation_default
      FROM res_company c
),
stocks AS (
    SELECT l.id, l.parent_path, l.complete_name, l.monitor_currency_id, l.address_id
      FROM stock_location l
     WHERE l.is_monitor_stock AND l.active AND l.usage = 'internal'
),
location_stock AS MATERIALIZED (
    -- nearest monitor stock of every internal location (longest parent_path prefix),
    -- resolved once per location rather than once per row
    SELECT DISTINCT ON (loc.id) loc.id AS location_id, st.id AS stock_id,
           st.complete_name AS stock_name, st.monitor_currency_id, st.address_id
      FROM stock_location loc
      JOIN stocks st ON loc.parent_path LIKE st.parent_path || '%'
     WHERE loc.usage = 'internal'
     ORDER BY loc.id, length(st.parent_path) DESC
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
    SELECT src.*, s.stock_id, s.stock_name,
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
      LEFT JOIN location_stock s ON s.location_id = src.location_id
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
b AS MATERIALIZED (
    -- source amount, currency and date of each measure (§3.4, §3.5); materialized:
    -- read again by the rate points and the rent lines
    SELECT v.*,
        (v.company_asset AND v.raw_asset_id IS NOT NULL) AS with_asset,
        (CASE WHEN v.family = 'consumable' THEN v.quantity * v.avco
              WHEN v.company_asset AND v.raw_asset_id IS NOT NULL THEN v.purchase_value
              WHEN v.company_asset THEN (CASE WHEN v.cost_known THEN v.raw_cost END)
              ELSE v.raw_replacement END) AS inventory_amount,
        (CASE WHEN v.third_party_asset THEN v.raw_replacement_currency
              ELSE v.company_currency END) AS inventory_currency,
        (CASE WHEN v.latest_mode OR v.family = 'consumable' THEN CURRENT_DATE
              WHEN v.company_asset AND v.raw_asset_id IS NOT NULL
                   THEN COALESCE(v.asset_date, CURRENT_DATE)
              WHEN v.company_asset THEN COALESCE(v.raw_cost_date, CURRENT_DATE)
              ELSE COALESCE(v.replacement_value_date, CURRENT_DATE) END) AS inventory_date,
        v.raw_replacement AS replacement_amount,
        v.raw_replacement_currency AS replacement_currency,
        (CASE WHEN v.latest_mode THEN CURRENT_DATE
              ELSE COALESCE(v.replacement_value_date, CURRENT_DATE) END) AS replacement_date,
        (CASE WHEN v.family = 'consumable' AND v.automated_valuation
                   THEN v.quantity * v.avco
              WHEN v.company_asset AND v.raw_asset_id IS NULL AND NOT v.fixed_asset_category
                   AND v.automated_valuation THEN v.avco
              ELSE 0 END) AS stock_amount,
        v.company_currency AS stock_currency, CURRENT_DATE AS stock_date,
        (CASE WHEN v.company_asset AND v.raw_asset_id IS NOT NULL THEN v.purchase_value END)
            AS original_amount,
        v.company_currency AS original_currency,
        (CASE WHEN v.latest_mode THEN CURRENT_DATE ELSE COALESCE(v.asset_date, CURRENT_DATE) END)
            AS original_date,
        (CASE WHEN v.company_asset AND v.raw_asset_id IS NOT NULL
              THEN COALESCE(v.value_depreciated, 0) END) AS depreciated_amount,
        v.company_currency AS depreciated_currency,
        (CASE WHEN v.latest_mode THEN CURRENT_DATE ELSE COALESCE(v.asset_date, CURRENT_DATE) END)
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
              THEN COALESCE(v.asset_date, CURRENT_DATE) ELSE CURRENT_DATE END) AS accounting_date,
        (v.rent_amount / v.rent_months) AS rent_m_amount,
        v.rent_currency_id AS rent_m_currency,
        (CASE WHEN v.latest_mode THEN CURRENT_DATE ELSE COALESCE(v.rent_start, CURRENT_DATE) END)
            AS rent_m_date
      FROM valued v
),
rent_lines AS MATERIALIZED (
    -- rent paid (§3.6): posted supplier bill and refund product lines linked to a rental
    -- line of the equipment on a supplier contract
    SELECT b.id AS row_id, aml.balance,
           (CASE WHEN b.latest_mode THEN CURRENT_DATE ELSE aml.date END) AS date
      FROM b
      JOIN contract_line cl ON cl.equipment_id = b.equipment_id
      JOIN contract_contract cc ON cc.id = cl.contract_id
      JOIN account_move_line aml ON aml.contract_line_id = cl.id
      JOIN account_move am ON am.id = aml.move_id
     WHERE cl.equipment_nature = 'rental' AND cc.contract_type = 'purchase'
       AND aml.parent_state = 'posted' AND aml.display_type = 'product'
       AND am.move_type IN ('in_invoice', 'in_refund')
),
points AS (
    -- the (currency, date) pairs the conversions need, each looked up once
    SELECT DISTINCT * FROM ({" UNION ALL ".join(points)}) p (currency, date, root)
),
point_rates AS MATERIALIZED (
    -- as res.currency._get_rates: the last rate on or before the date (company rows
    -- first), else the earliest later one; none found: both NULL
    SELECT p.currency, p.date, p.root, rb.rate AS rate_before, ra.rate AS rate_after
      FROM points p
      LEFT JOIN LATERAL (
          SELECT r.rate FROM res_currency_rate r
           WHERE r.currency_id = p.currency AND r.name <= p.date
             AND (r.company_id IS NULL OR r.company_id = p.root)
           ORDER BY r.company_id, r.name DESC LIMIT 1) rb ON TRUE
      LEFT JOIN LATERAL (
          SELECT r.rate FROM res_currency_rate r
           WHERE rb.rate IS NULL AND r.currency_id = p.currency
             AND (r.company_id IS NULL OR r.company_id = p.root)
           ORDER BY r.company_id, r.name ASC LIMIT 1) ra ON TRUE
),
rent_paid AS (
    SELECT rl.row_id, SUM(rl.balance) AS source_amount,
           (CASE WHEN bool_or({rent_conv['missing']} = 1) THEN NULL
                 ELSE SUM({rent_conv['value']}) END) AS converted,
           max({rent_conv['missing']}) AS missing, max({rent_conv['fallback']}) AS fallback
      FROM rent_lines rl
      JOIN b ON b.id = rl.row_id
      {_rate_join("rp_s", "b.company_currency", "rl.date", "b.root_company")}
      {_rate_join("rp_t", "b.target_currency", "rl.date", "b.root_company")}
     GROUP BY rl.row_id
),
measured AS (
    SELECT b.*, b.target_currency AS currency_id,
           {",".join(selects)},
           rp.converted AS rent_paid, rp.source_amount AS rent_paid_source_amount,
           COALESCE(rp.missing, 0) AS rent_paid_rate_missing,
           COALESCE(rp.fallback, 0) AS rent_paid_rate_fallback,
           (CASE WHEN rp.converted IS NULL THEN 0 ELSE 1 END) AS rent_paid_known,
           (CASE WHEN ({" + ".join(missing)}) + COALESCE(rp.missing, 0) > 0
                 THEN 1 ELSE 0 END) AS any_rate_missing
      FROM b
      {"".join(joins)}
      LEFT JOIN rent_paid rp ON rp.row_id = b.id
),
alerted AS (
    SELECT m.*,
       country.name AS country_name, state.name AS state_name, uom.name AS uom_name,
       owner.name AS owner_name, responsible.name AS responsible_name,
       (CASE WHEN m.company_asset THEN m.raw_asset_state END) AS asset_state,
       (CASE WHEN m.with_asset AND m.raw_asset_state = 'draft' THEN 1 ELSE 0 END)
           AS accounting_provisional,
       (CASE WHEN m.company_asset AND m.raw_asset_id IS NULL AND m.cost_known
                  AND m.cost_provisional THEN 1 ELSE 0 END) AS inventory_provisional,
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
           AS alert_no_responsible
      FROM measured m
      LEFT JOIN res_country country ON country.id = m.country_id
      LEFT JOIN res_country_state state ON state.id = m.state_id
      LEFT JOIN uom_uom uom ON uom.id = m.uom_id
      LEFT JOIN res_partner owner ON owner.id = m.owner_partner_id
      LEFT JOIN res_users ru ON ru.id = m.owner_user_id
      LEFT JOIN res_partner responsible ON responsible.id = ru.partner_id
      JOIN res_company co ON co.id = m.company_id
)
SELECT a.*, ({alert_sum}) AS alert_count FROM alerted a
"""

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
        returned. The list page is read separately with the returned domain.

        One fine-grained read_group (by country, city, stock, place, currency, family
        and ownership, without the filters) gives the choices, the stock cards, the
        family and ownership counts, the alert counts and, without alert or text
        filter, the totals: the groups are filtered here instead of querying the view
        once per block. Further queries only when needed: totals with an alert or text
        filter, unconverted amounts, provisional net book value."""
        filters = filters or {}
        domain = self._dashboard_domain(filters)
        measures = self._readable(list(MEASURES))
        rent_paid = self._readable(["rent_paid"])
        alerts = self._dashboard_alerts()
        staff = self._fields["stock_id"].is_accessible(self.env)
        accountant = "accounting_value" in measures

        dims = ["country_name", "city", "stock_name", "place_type", "currency_id", "family",
                "ownership_status"]
        sums = ["asset_count"] + measures + [f"{m}_rate_missing" for m in measures] + [
            f"{m}_known" for m in measures] + alerts
        if rent_paid:
            sums += ["rent_paid", "rent_paid_rate_missing", "rent_paid_known"]
        if accountant:
            sums.append("accounting_provisional")
        if self._readable(["alert_count"]):
            sums.append("alert_count")
        aggregates = ["__count"] + [f"{name}:sum" for name in sums]
        groups = []
        for row in self._read_group([], dims, aggregates):
            group = dict(zip(dims, row[:len(dims)]))
            group["currency_id"] = group["currency_id"].id
            group.update(zip(["count"] + sums, row[len(dims):]))
            groups.append(group)

        stock_filter = set(filters.get("stocks") or [])

        def match(group, skip=()):
            checks = {
                "countries": group["country_name"] or "",
                "cities": group["city"] or "",
                "families": group["family"],
                "ownerships": group["ownership_status"],
            }
            for key, value in checks.items():
                if key not in skip and filters.get(key) and value not in filters[key]:
                    return False
            if "stocks" not in skip and stock_filter and (
                    group["stock_name"] or OUTSIDE_STOCK) not in stock_filter:
                return False
            return True

        def total(name, rows):
            by_currency = {}
            for group in rows:
                if group.get(f"{name}_known", 1) and group.get(name) is not None:
                    by_currency[group["currency_id"]] = (
                        by_currency.get(group["currency_id"], 0.0) + (group[name] or 0.0))
            return [{"currency_id": currency, "amount": amount}
                    for currency, amount in by_currency.items()]

        # 1. totals per currency (never added across currencies)
        names = measures + rent_paid
        if filters.get("alert") or (filters.get("search") or "").strip():
            rows = []
            for row in self._read_group(domain, ["currency_id"], aggregates):
                group = {"currency_id": row[0].id}
                group.update(zip(["count"] + sums, row[1:]))
                rows.append(group)
        else:
            rows = [group for group in groups if match(group)]
        totals = {name: {"lines": total(name, rows), "missing": [], "provisional": []}
                  for name in names}
        count = sum(group["count"] for group in rows)
        assets = sum(group["asset_count"] or 0 for group in rows)
        # unconverted amounts, in their source currency, and provisional net book value
        for name in names:
            if not sum(group.get(f"{name}_rate_missing") or 0 for group in rows):
                continue
            if name == "rent_paid":
                amount = self._read_group(domain + [("rent_paid_rate_missing", "=", 1)], [],
                                          ["rent_paid_source_amount:sum"])[0][0]
                totals[name]["missing"] = [
                    {"currency_id": self.env.company.currency_id.id, "amount": amount}]
                continue
            totals[name]["missing"] = [
                {"currency_id": currency.id, "amount": amount}
                for currency, amount in self._read_group(
                    domain + [(f"{name}_rate_missing", "=", 1)],
                    [f"{name}_source_currency_id"], [f"{name}_source_amount:sum"])
                if currency]
        if accountant and sum(group.get("accounting_provisional") or 0 for group in rows):
            totals["accounting_value"]["provisional"] = [
                {"currency_id": currency.id, "amount": amount}
                for currency, amount in self._read_group(
                    domain + [("accounting_provisional", "=", 1)], ["currency_id"],
                    ["accounting_value:sum"])]

        # 2. stock cards: the selection's geography, family and ownership, every stock
        cards = {}
        for group in groups:
            if not match(group, skip=("stocks",)):
                continue
            key = (group["stock_name"] or OUTSIDE_STOCK, group["currency_id"])
            card = cards.setdefault(key, {
                "name": key[0], "city": group["city"] or "",
                "country": group["country_name"] or "", "place_type": group["place_type"] or "",
                "currency_id": group["currency_id"], "count": 0, "assets": 0,
                "inventory_value": 0.0, "missing": 0, "alerts": 0,
            })
            card["count"] += group["count"]
            card["assets"] += group["asset_count"] or 0
            if group["inventory_value_known"]:
                card["inventory_value"] += group["inventory_value"] or 0.0
            card["missing"] += group["inventory_value_rate_missing"] or 0
            card["alerts"] += group.get("alert_count") or 0
        stocks = sorted(cards.values(), key=lambda card: (card["name"] == OUTSIDE_STOCK,
                                                          card["name"]))

        # 3. alert counts: the selection without the alert filter and the search
        alert_counts = dict.fromkeys(alerts, 0)
        for group in groups:
            if match(group):
                for name in alerts:
                    alert_counts[name] += group.get(name) or 0

        # 4. counts of the family segment and the ownership chips
        segment_counts = {}
        for group in groups:
            if match(group, skip=("families", "ownerships")):
                key = (group["family"], group["ownership_status"])
                segment_counts[key] = segment_counts.get(key, 0) + group["count"]
        segments = [{"family": family, "ownership": ownership, "count": number}
                    for (family, ownership), number in segment_counts.items()]

        # 5. choices of the selectors: every stock the user may see
        seen = {}
        for group in groups:
            key = (group["country_name"] or "", group["city"] or "",
                   group["stock_name"] or OUTSIDE_STOCK, group["currency_id"])
            seen[key] = True
        choices = [{"country": country, "city": city, "stock": stock, "currency_id": currency}
                   for country, city, stock, currency in seen]

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
            # « Open the equipment form » only for users who may read equipment
            "equipment_access": staff and self.env["maintenance.equipment"].has_access("read"),
            "date": fields.Date.context_today(self),
            "company_currency_id": self.env.company.currency_id.id,
        }

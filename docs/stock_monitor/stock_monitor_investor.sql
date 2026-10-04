-- Stock monitor (investor version, generated from stock_monitor.sql without the
-- accounting value and rent columns): one row per item in an internal stock (assets + consumables).
-- Used as the query of an OCA bi_sql_editor report (Dashboards > Configuration >
-- SQL Views). Column names must start with x_. Definitions: docs/DEFINITIONS.md.
-- Amounts are in the company currency, converted at the latest rate into the
-- currency of the stock's country (warehouse address); company currency if that
-- currency has no rate.
WITH comp AS (
    SELECT c.id, c.currency_id, p.commercial_partner_id AS partner_id
    FROM res_company c JOIN res_partner p ON p.id = c.partner_id
),
loc AS (
    SELECT l.id, l.place_type, l.warehouse_id, l.company_id,
           wp.country_id, wp.state_id, wp.city
    FROM stock_location l
    LEFT JOIN stock_warehouse w ON w.id = l.warehouse_id
    LEFT JOIN res_partner wp ON wp.id = w.partner_id
    WHERE l.usage = 'internal' AND l.active
),
-- Supplier contract lines (OCA contract): monthly rent per unit, paid amount.
line AS (
    SELECT cl.id, cl.contract_id, cl.product_id, cl.quantity,
           cp.commercial_partner_id AS partner_id,
           cl.specific_price * (1 - COALESCE(cl.discount, 0) / 100.0)
             * CASE cl.recurring_rule_type
                 WHEN 'daily' THEN 30.4375 WHEN 'weekly' THEN 4.348214
                 WHEN 'quarterly' THEN 1 / 3.0 WHEN 'semesterly' THEN 1 / 6.0
                 WHEN 'yearly' THEN 1 / 12.0 ELSE 1 END
             / GREATEST(cl.recurring_interval, 1) AS unit_month,
           cl.date_start <= CURRENT_DATE
             AND (cl.date_end IS NULL OR cl.date_end >= CURRENT_DATE)
             AND NOT COALESCE(cl.is_canceled, FALSE) AS running,
           COALESCE((SELECT SUM(aml.balance) FROM account_move_line aml
                     WHERE aml.contract_line_id = cl.id
                       AND aml.parent_state = 'posted'), 0) AS paid
    FROM contract_line cl
    JOIN contract_contract c ON c.id = cl.contract_id
    JOIN res_partner cp ON cp.id = c.partner_id
    WHERE c.contract_type = 'purchase' AND c.active AND cl.display_type IS NULL
),
-- Equipment rent: contracts linked to the equipment, split equally between
-- the equipment of a same contract.
eq_rent AS (
    SELECT rel.maintenance_equipment_id AS equipment_id,
           SUM(CASE WHEN line.running THEN line.quantity * line.unit_month ELSE 0 END
               / n.n_eq) AS rent_month,
           SUM(line.paid / n.n_eq) AS paid
    FROM contract_contract_maintenance_equipment_rel rel
    JOIN (SELECT contract_contract_id, COUNT(*) AS n_eq
          FROM contract_contract_maintenance_equipment_rel GROUP BY 1) n
      ON n.contract_contract_id = rel.contract_contract_id
    JOIN line ON line.contract_id = rel.contract_contract_id
    GROUP BY 1
),
asset AS (
    SELECT 'asset'::varchar AS family, eq.current_location_id AS location_id,
           COALESCE(eq.company_id, loc.company_id, (SELECT MIN(id) FROM res_company)) AS company_id,
           eq.product_id, COALESCE(eq.name ->> 'fr_FR', eq.name ->> 'en_US') AS item,
           CASE eq.acquisition_mode
               WHEN 'rental' THEN 'rented'
               WHEN 'borrowed' THEN 'borrowed'
               WHEN 'loaned_out' THEN 'lent_out'
               ELSE CASE WHEN COALESCE(eq.owner_type, 'company') = 'company'
                         THEN 'owned' ELSE 'borrowed' END
           END::varchar AS ownership,
           1.0 AS quantity,
           COALESCE(eq.cost, 0) AS own_value,
           COALESCE(eq.replacement_value, 0) AS third_value,
           a.purchase_value - a.value_depreciated AS book_value,
           er.rent_month, er.paid
    FROM maintenance_equipment eq
    JOIN loc ON loc.id = eq.current_location_id
    LEFT JOIN account_move_line ml ON ml.id = eq.move_line_id
    LEFT JOIN account_asset a ON a.id = ml.asset_id
    LEFT JOIN eq_rent er ON er.equipment_id = eq.id
    WHERE eq.active
),
quant AS (
    SELECT q.location_id, q.company_id, q.product_id, q.quantity,
           COALESCE(pt.name ->> 'fr_FR', pt.name ->> 'en_US') AS item,
           COALESCE((pp.standard_price ->> q.company_id::text)::numeric, 0) AS unit_cost,
           op.commercial_partner_id AS owner_id,
           CASE
               WHEN loc.place_type = 'lent_out' THEN 'lent_out'
               WHEN op.id IS NULL OR op.commercial_partner_id = comp.partner_id THEN 'owned'
               WHEN EXISTS (SELECT 1 FROM line
                            WHERE line.running AND line.partner_id = op.commercial_partner_id
                              AND line.product_id = q.product_id) THEN 'rented'
               ELSE 'borrowed'
           END::varchar AS ownership
    FROM stock_quant q
    JOIN loc ON loc.id = q.location_id
    JOIN comp ON comp.id = q.company_id
    JOIN product_product pp ON pp.id = q.product_id
    JOIN product_template pt ON pt.id = pp.product_tmpl_id AND pt.is_storable
    LEFT JOIN res_partner op ON op.id = q.owner_id
    WHERE q.quantity <> 0
),
-- Consumable rent: per owner and product, split between stocks by quantity.
cons_rent AS (
    SELECT partner_id, product_id,
           SUM(CASE WHEN running THEN quantity * unit_month ELSE 0 END) AS rent_month,
           SUM(paid) AS paid
    FROM line GROUP BY 1, 2
),
rented_qty AS (
    SELECT owner_id, product_id, SUM(quantity) AS quantity
    FROM quant WHERE ownership = 'rented' GROUP BY 1, 2
),
consumable AS (
    SELECT 'consumable'::varchar AS family, quant.location_id, quant.company_id,
           quant.product_id, quant.item, quant.ownership, quant.quantity,
           quant.quantity * quant.unit_cost AS own_value,
           -- Replacement price of borrowed/rented consumables: product cost.
           quant.quantity * quant.unit_cost AS third_value,
           quant.quantity * quant.unit_cost AS book_value,
           cr.rent_month * quant.quantity / NULLIF(rq.quantity, 0) AS rent_month,
           cr.paid * quant.quantity / NULLIF(rq.quantity, 0) AS paid
    FROM quant
    LEFT JOIN rented_qty rq ON quant.ownership = 'rented'
         AND rq.owner_id = quant.owner_id AND rq.product_id = quant.product_id
    LEFT JOIN cons_rent cr ON quant.ownership = 'rented'
         AND cr.partner_id = quant.owner_id AND cr.product_id = quant.product_id
),
item AS (
    SELECT * FROM asset UNION ALL SELECT * FROM consumable
)
SELECT
    item.family AS x_family,
    item.ownership AS x_ownership,
    item.location_id AS x_location_id,
    loc.warehouse_id AS x_warehouse_id,
    loc.place_type AS x_place_type,
    loc.country_id AS x_country_id,
    loc.state_id AS x_state_id,
    loc.city AS x_city,
    cur.currency_id AS x_currency_id,
    item.product_id AS x_product_id,
    item.item AS x_item,
    item.quantity AS x_quantity,
    ROUND((cur.factor * CASE WHEN item.ownership IN ('owned', 'lent_out')
                            THEN item.own_value ELSE item.third_value END)::numeric, 2) AS x_inventory_value
FROM item
JOIN loc ON loc.id = item.location_id
JOIN comp ON comp.id = item.company_id
LEFT JOIN res_country ctry ON ctry.id = loc.country_id
LEFT JOIN LATERAL (
    SELECT r.rate FROM res_currency_rate r
    WHERE r.currency_id = ctry.currency_id AND r.name <= CURRENT_DATE
      AND (r.company_id = comp.id OR r.company_id IS NULL)
    ORDER BY r.name DESC LIMIT 1
) to_rate ON TRUE
LEFT JOIN LATERAL (
    SELECT r.rate FROM res_currency_rate r
    WHERE r.currency_id = comp.currency_id AND r.name <= CURRENT_DATE
      AND (r.company_id = comp.id OR r.company_id IS NULL)
    ORDER BY r.name DESC LIMIT 1
) from_rate ON TRUE
CROSS JOIN LATERAL (
    SELECT CASE WHEN ctry.currency_id IS NOT NULL AND ctry.currency_id <> comp.currency_id
                     AND to_rate.rate IS NOT NULL
                THEN ctry.currency_id ELSE comp.currency_id END AS currency_id,
           CASE WHEN ctry.currency_id IS NOT NULL AND ctry.currency_id <> comp.currency_id
                     AND to_rate.rate IS NOT NULL
                THEN to_rate.rate / COALESCE(from_rate.rate, 1) ELSE 1 END AS factor
) cur

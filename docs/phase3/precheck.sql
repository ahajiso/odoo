-- Phase 3 precheck (read-only). Every row is a blocking finding; no row = OK.
-- Run by precheck.sh before the update (docs/phase3/README.md), and by the test
-- test_precheck_finds_blocking_data. Uses only what exists before the update.

-- 1. Views reading a column the update removes (dropped with CASCADE otherwise):
--    the old bi_sql_editor reports read maintenance_equipment.owner_type /
--    acquisition_mode and res_company.stock_monitor_replacement_price.
SELECT 'dependent_view' AS check_name, c.oid::integer AS record_id,
       c.relname || ' reads ' || a.attrelid::regclass || '.' || a.attname AS detail
  FROM pg_depend d
  JOIN pg_rewrite r ON r.oid = d.objid
  JOIN pg_class c ON c.oid = r.ev_class
  JOIN pg_attribute a ON a.attrelid = d.refobjid AND a.attnum = d.refobjsubid
 WHERE d.classid = 'pg_rewrite'::regclass AND d.refclassid = 'pg_class'::regclass
   AND c.relname <> 'lartdubati_stock_monitor'
   AND ((a.attrelid = 'maintenance_equipment'::regclass
         AND a.attname IN ('owner_type', 'acquisition_mode'))
        OR (a.attrelid = 'res_company'::regclass
            AND a.attname = 'stock_monitor_replacement_price'))
UNION ALL
-- 2. Equipment linked to contracts by maintenance_equipment_contract (unqualified
--    many2many, replaced by contract.line.equipment_id): its rows must be decided and
--    the module uninstalled first. The table may not exist: counted only if it does.
SELECT 'equipment_contract_rel', n, n || ' row(s) in contract_contract_maintenance_equipment_rel'
  FROM (SELECT CASE WHEN to_regclass('contract_contract_maintenance_equipment_rel') IS NULL
                    THEN 0
                    ELSE (xpath('/row/n/text()', query_to_xml(
                          'SELECT count(*) AS n FROM contract_contract_maintenance_equipment_rel',
                          false, true, '')))[1]::text::integer END AS n) rel
 WHERE n > 0
UNION ALL
-- 3. Candidate monitor stocks (warehouse stocks, lent-out locations) without an address
--    with a city and a country: the post-migration would stop on them.
SELECT 'stock_address', l.id,
       l.complete_name || ': ' || CASE WHEN p.id IS NULL THEN 'no address'
                                       WHEN COALESCE(p.city, '') = '' THEN 'no city'
                                       ELSE 'no country' END
  FROM stock_location l
  LEFT JOIN res_partner p ON p.id = l.address_id
 WHERE l.active AND l.usage = 'internal'
   AND (l.id IN (SELECT lot_stock_id FROM stock_warehouse WHERE active)
        OR l.place_type = 'lent_out')
   AND (p.id IS NULL OR COALESCE(p.city, '') = '' OR p.country_id IS NULL)
ORDER BY 1, 2;

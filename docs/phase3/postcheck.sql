-- Phase 3 check AFTER the update (docs/phase3/README.md). Every row is a finding;
-- no row = OK.
SELECT 'monitor_view_missing' AS check_name, 0 AS record_id,
       'the view lartdubati_stock_monitor does not exist' AS detail
 WHERE to_regclass('lartdubati_stock_monitor') IS NULL
UNION ALL
SELECT 'obsolete_column', 0, table_name || '.' || column_name || ' still exists'
  FROM information_schema.columns
 WHERE (table_name = 'maintenance_equipment' AND column_name IN ('owner_type', 'acquisition_mode'))
    OR (table_name = 'res_company' AND column_name = 'stock_monitor_replacement_price')
UNION ALL
SELECT 'asset_rows', 0, 'monitor ' || m || ' asset rows, ' || e || ' integrated equipment'
  FROM (SELECT (SELECT count(*) FROM lartdubati_stock_monitor WHERE family = 'asset') AS m,
               (SELECT count(*) FROM maintenance_equipment
                 WHERE active AND integration_state = 'done') AS e) x
 WHERE m <> e
UNION ALL
SELECT 'consumable_rows', 0, 'monitor ' || m || ' consumable rows, ' || q || ' quants'
  FROM (SELECT (SELECT count(*) FROM lartdubati_stock_monitor WHERE family = 'consumable') AS m,
               (SELECT count(*) FROM stock_quant q
                  JOIN stock_location l ON l.id = q.location_id
                  JOIN product_product pp ON pp.id = q.product_id
                  JOIN product_template pt ON pt.id = pp.product_tmpl_id
                 WHERE l.usage = 'internal' AND q.quantity <> 0
                   AND NOT COALESCE(pt.maintenance_ok, FALSE)) AS q) x
 WHERE m <> q
UNION ALL
SELECT 'monitor_stock', l.id, l.complete_name || ': candidate not flagged as monitor stock'
  FROM stock_location l
 WHERE l.active AND l.usage = 'internal' AND NOT COALESCE(l.is_monitor_stock, FALSE)
   AND (l.id IN (SELECT lot_stock_id FROM stock_warehouse WHERE active)
        OR l.place_type = 'lent_out')
ORDER BY 1, 2;

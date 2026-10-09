-- Phase 2f precheck (read-only). Every row is a blocking finding; no row = OK.
-- Run by precheck.sh before the update, and by the test test_precheck_finds_legacy_data.
-- Uses only columns that exist before the update (phase 2 schema).
SELECT 'responsible' AS check_name, e.id AS record_id, e.name->>'en_US' AS detail
  FROM maintenance_equipment e
  LEFT JOIN res_users u ON u.id = e.owner_user_id
 WHERE e.active AND e.integration_state = 'done'
   AND (u.id IS NULL OR NOT u.active OR u.share
        OR (e.company_id IS NOT NULL AND NOT EXISTS (
              SELECT 1 FROM res_company_users_rel r
               WHERE r.user_id = u.id AND r.cid = e.company_id)))
UNION ALL
SELECT 'open_receipt', p.id, p.name
  FROM stock_picking p
  JOIN stock_picking_type t ON t.id = p.picking_type_id
 WHERE t.code = 'incoming' AND p.state NOT IN ('done', 'cancel')
   AND p.equipment_operation_id IS NULL
ORDER BY 1, 2;

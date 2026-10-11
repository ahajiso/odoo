-- ROADMAP section 0, items 1 and 2 (docs/roadmap0/README.md): read-only precheck.
-- After the update, a receipt or a bill of a maintainable product without a default
-- equipment category is refused (no equipment category is ever created silently any
-- more). The products of artdubati_test get their category in item 3 (migration).
-- Every row is an open document that would be blocked: to finish or to keep in mind
-- before the update. No row: nothing in progress is affected.

-- equipment operations not executed with a maintainable product
SELECT 'open_operation' AS check, o.name, o.state, pt.name->>'en_US' AS product
  FROM equipment_operation o
  JOIN equipment_operation_line l ON l.operation_id = o.id
  JOIN product_product pp ON pp.id = l.product_id
  JOIN product_template pt ON pt.id = pp.product_tmpl_id
 WHERE o.state NOT IN ('done', 'cancel') AND pt.maintenance_ok
UNION ALL
-- draft supplier bills with a maintainable product and no equipment category yet
SELECT 'draft_bill', m.name, m.state, pt.name->>'en_US'
  FROM account_move_line aml
  JOIN account_move m ON m.id = aml.move_id
  JOIN product_product pp ON pp.id = aml.product_id
  JOIN product_template pt ON pt.id = pp.product_tmpl_id
 WHERE m.state = 'draft' AND m.move_type IN ('in_invoice', 'in_refund')
   AND pt.maintenance_ok AND aml.equipment_category_id IS NULL
ORDER BY 1, 2;

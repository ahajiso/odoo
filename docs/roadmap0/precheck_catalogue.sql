-- ROADMAP section 0, items 1 to 3 (docs/roadmap0/README.md): read-only precheck, run
-- BEFORE the update. After the update a receipt or a bill of a maintainable product
-- without a default equipment category is refused (no category created silently); the
-- migration of item 3, in the same window, gives the products their category. Before
-- the update the field does not exist: no product has one yet, so every maintainable
-- product counts as « without category » here. Every row is an open document that the
-- update blocks until the migration: to finish before, or to know about. No row:
-- nothing in progress is affected.

-- equipment operations not executed with a maintainable product (all without a default
-- equipment category before the update)
SELECT 'open_operation' AS check, o.name, o.state, pt.name->>'en_US' AS product
  FROM equipment_operation o
  JOIN equipment_operation_line l ON l.operation_id = o.id
  JOIN product_product pp ON pp.id = l.product_id
  JOIN product_template pt ON pt.id = pp.product_tmpl_id
 WHERE o.state NOT IN ('done', 'cancel') AND pt.maintenance_ok
UNION ALL
-- draft supplier bills: blocked only if the line has no equipment category of its own
-- (maintenance_account's field) and its product none either (none before the update)
SELECT 'draft_bill', m.name, m.state, pt.name->>'en_US'
  FROM account_move_line aml
  JOIN account_move m ON m.id = aml.move_id
  JOIN product_product pp ON pp.id = aml.product_id
  JOIN product_template pt ON pt.id = pp.product_tmpl_id
 WHERE m.state = 'draft' AND m.move_type IN ('in_invoice', 'in_refund')
   AND pt.maintenance_ok AND aml.equipment_category_id IS NULL
ORDER BY 1, 2;

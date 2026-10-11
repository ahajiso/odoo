-- ROADMAP section 0, items 1 and 2: post-update check (read-only). Every row is a
-- problem; no row = OK.
SELECT 'missing_data' AS check, d.name, '' AS detail FROM (VALUES
    ('group_product_catalogue_manager'), ('module_category_product_catalogue'),
    ('seq_product_creation_request'), ('seq_product_structural_correction'),
    ('categ_root_fixed_assets'), ('categ_root_small_equipment'), ('categ_root_materials'),
    ('categ_root_consumables'), ('categ_root_goods'), ('categ_root_services_purchased'),
    ('categ_root_sales'), ('categ_root_intangible'), ('ecat_to_classify'),
    ('ecat_it_computers'), ('ecat_measuring'), ('ecat_workshop_wood'),
    ('rule_product_creation_request_company'), ('rule_product_creation_request_own'),
    ('rule_product_creation_request_manager')) d(name)
 WHERE NOT EXISTS (SELECT 1 FROM ir_model_data x
                    WHERE x.module = 'maintenance_shareholder_equipment' AND x.name = d.name)
UNION ALL
-- the equipment tree: 27 categories of the module, « To Classify » not usable
SELECT 'equipment_tree', count(*)::text, 'expected 27'
  FROM ir_model_data x
 WHERE x.module = 'maintenance_shareholder_equipment' AND x.model = 'maintenance.equipment.category'
HAVING count(*) <> 27
UNION ALL
SELECT 'to_classify_usable', c.id::text, ''
  FROM maintenance_equipment_category c
  JOIN ir_model_data x ON x.res_id = c.id AND x.model = 'maintenance.equipment.category'
   AND x.module = 'maintenance_shareholder_equipment' AND x.name = 'ecat_to_classify'
 WHERE c.assignable
UNION ALL
-- the three partial unique indexes of the executed requests
SELECT 'missing_index', i.name, '' FROM (VALUES
    ('product_creation_request_key_default_code_done_uniq'),
    ('product_creation_request_key_barcode_done_uniq'),
    ('product_creation_request_key_supplier_done_uniq')) i(name)
 WHERE NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = i.name)
UNION ALL
-- no product created since the update outside a request (the update itself excepted)
SELECT 'product_outside_request', t.id::text, t.name->>'en_US'
  FROM product_template t
 WHERE t.create_date > (SELECT max(write_date) FROM ir_module_module
                         WHERE name = 'maintenance_shareholder_equipment')
   AND NOT EXISTS (SELECT 1 FROM product_creation_request r WHERE r.product_tmpl_id = t.id);

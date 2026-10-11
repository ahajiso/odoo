-- ROADMAP section 0, items 1 to 3: post-update and post-migration check (read-only),
-- run after the migration's --apply. Every row is a problem; no row = OK.
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
   AND NOT EXISTS (SELECT 1 FROM product_creation_request r WHERE r.product_tmpl_id = t.id)
UNION ALL
-- item 3: the records created by the migration (external IDs roadmap0.*)
SELECT 'missing_migration_data', d.name, '' FROM (VALUES
    ('asset_profile_it'), ('categ_fixed_it'), ('categ_fixed_plant'), ('categ_svc_rentals'),
    ('categ_svc_telecom'), ('categ_svc_bank'), ('categ_svc_admin'),
    ('categ_sale_consulting'), ('categ_sale_works'), ('categ_sale_rentals')) d(name)
 WHERE NOT EXISTS (SELECT 1 FROM ir_model_data x WHERE x.module = 'roadmap0' AND x.name = d.name)
UNION ALL
-- item 3: the migration's categories are open for requests, and only them
SELECT 'request_ready', c.id::text, c.complete_name
  FROM product_category c
  LEFT JOIN ir_model_data x ON x.model = 'product.category' AND x.res_id = c.id
   AND x.module = 'roadmap0'
 WHERE coalesce(c.request_ready, false) <> (x.id IS NOT NULL)
UNION ALL
-- item 3: every active equipment in an active, usable category of the module's tree
SELECT 'equipment_category', e.id::text, e.name->>'en_US'
  FROM maintenance_equipment e
  LEFT JOIN maintenance_equipment_category c ON c.id = e.category_id
 WHERE e.active AND (c.id IS NULL OR NOT c.active OR NOT c.assignable
       OR NOT EXISTS (SELECT 1 FROM ir_model_data x WHERE x.model = 'maintenance.equipment.category'
                       AND x.res_id = c.id AND x.module = 'maintenance_shareholder_equipment'))
UNION ALL
-- item 3: no old equipment category left active (imported or automatic)
SELECT 'old_equipment_category', c.id::text, c.complete_name
  FROM maintenance_equipment_category c
 WHERE c.active AND NOT EXISTS (SELECT 1 FROM ir_model_data x
                                 WHERE x.model = 'maintenance.equipment.category'
                                   AND x.res_id = c.id
                                   AND x.module = 'maintenance_shareholder_equipment')
UNION ALL
-- item 3: account 218300 carries the IT test profile (company-dependent fields: jsonb
-- keyed by the company id; one company)
SELECT 'account_218300_profile', a.id::text, coalesce(a.asset_profile_id->>c.id::text, 'none')
  FROM account_account a, (SELECT id FROM res_company ORDER BY id LIMIT 1) c
 WHERE a.code_store->>c.id::text = '218300'
   AND NOT EXISTS (SELECT 1 FROM ir_model_data x WHERE x.module = 'roadmap0'
                    AND x.name = 'asset_profile_it'
                    AND x.res_id::text = a.asset_profile_id->>c.id::text);

-- Phase 4 precheck, information only: menus hidden by base_menu_visibility_restriction
-- (run only when the module's table exists). Its uninstallation is the owner's choice
-- once nothing but the four investor exclusions of the old setup script uses it.
SELECT 'menu exclusion', m.name->>'en_US', g.name->>'en_US'
  FROM ir_ui_menu m
  JOIN ir_ui_menu_excluded_group_rel r ON r.menu_id = m.id
  JOIN res_groups g ON g.id = r.gid
ORDER BY 2;

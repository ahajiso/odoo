-- Phase 4 post-update check (read-only): every row is a problem; no row = OK.
SELECT 'home_record_not_adopted', d.name, '' FROM (VALUES
    ('investor_home_screen'), ('investor_button_financial'),
    ('investor_button_administrative'), ('investor_button_commerce'),
    ('investor_button_production'), ('action_investor_home'), ('action_coming_soon')) d(name)
 WHERE NOT EXISTS (SELECT 1 FROM ir_model_data x
                    WHERE x.module = 'lartdubati_investor_home' AND x.name = d.name)
UNION ALL
-- every screen or button not bound to our external IDs: a duplicate the adoption missed
SELECT 'unbound_' || t.tbl, t.id::text, t.name
  FROM (SELECT 'quick_start_screen' AS tbl, id, name->>'en_US' AS name FROM quick_start_screen
        UNION ALL
        SELECT 'quick_start_screen_action', id, name->>'en_US' FROM quick_start_screen_action) t
 WHERE NOT EXISTS (SELECT 1 FROM ir_model_data x
                    WHERE x.module = 'lartdubati_investor_home' AND x.res_id = t.id
                      AND x.model = replace(t.tbl, '_', '.'))
UNION ALL
SELECT 'investor_home_action', u.login, COALESCE(a.name->>'en_US', '-')
  FROM res_users u
  JOIN res_groups_users_rel inv ON inv.uid = u.id
   AND inv.gid = (SELECT res_id FROM ir_model_data
                   WHERE module = 'lartdubati_investor_home' AND name = 'group_stock_investor')
  LEFT JOIN ir_actions a ON a.id = u.action_id
 WHERE u.active AND u.action_id IS DISTINCT FROM (
       SELECT res_id FROM ir_model_data
        WHERE module = 'lartdubati_investor_home' AND name = 'action_investor_home')
UNION ALL
SELECT 'missing_rule', d.name, '' FROM (VALUES
    ('rule_menu_investor'), ('rule_users_investor'), ('rule_partner_investor'),
    ('rule_quick_start_action_investor'), ('rule_discuss_channel_investor'),
    ('rule_mail_message_investor')) d(name)
 WHERE NOT EXISTS (SELECT 1 FROM ir_model_data x
                    WHERE x.module = 'lartdubati_investor_home' AND x.name = d.name);

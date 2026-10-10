-- Phase 4 post-update check (read-only): every row is a problem; no row = OK.
SELECT 'home_record_not_adopted', d.name, '' FROM (VALUES
    ('investor_home_screen'), ('investor_button_financial'),
    ('investor_button_administrative'), ('investor_button_commerce'),
    ('investor_button_production'), ('action_investor_home'), ('action_coming_soon')) d(name)
 WHERE NOT EXISTS (SELECT 1 FROM ir_model_data x
                    WHERE x.module = 'lartdubati_investor_home' AND x.name = d.name)
UNION ALL
-- the investor screen holds exactly the module's four buttons
SELECT 'investor_screen_buttons', string_agg(r.quick_start_screen_action_id::text, ', '), ''
  FROM quick_start_screen_quick_start_screen_action_rel r
 WHERE r.quick_start_screen_id = (SELECT res_id FROM ir_model_data
        WHERE module = 'lartdubati_investor_home' AND name = 'investor_home_screen')
HAVING array_agg(r.quick_start_screen_action_id ORDER BY r.quick_start_screen_action_id) IS DISTINCT FROM (
       SELECT array_agg(res_id ORDER BY res_id) FROM ir_model_data
        WHERE module = 'lartdubati_investor_home' AND name LIKE 'investor_button_%')
UNION ALL
-- no second screen named like the investor screen (a duplicate the adoption missed);
-- other profiles' screens are not concerned
SELECT 'duplicate_investor_screen', s.id::text, s.name->>'en_US'
  FROM quick_start_screen s
 WHERE (s.name->>'en_US' = ANY(ARRAY['Investor Home', 'Accueil investisseur', 'خانه سرمایه‌گذار'])
        OR s.name->>'fr_FR' = ANY(ARRAY['Investor Home', 'Accueil investisseur', 'خانه سرمایه‌گذار'])
        OR s.name->>'fa_IR' = ANY(ARRAY['Investor Home', 'Accueil investisseur', 'خانه سرمایه‌گذار']))
   AND s.id <> (SELECT res_id FROM ir_model_data
                 WHERE module = 'lartdubati_investor_home' AND name = 'investor_home_screen')
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
-- Q6: every active investor account holds « Access to export feature » (implied by the
-- investor group since 18.0.3.0.1)
SELECT 'investor_without_export', u.login, ''
  FROM res_users u
  JOIN res_groups_users_rel inv ON inv.uid = u.id
   AND inv.gid = (SELECT res_id FROM ir_model_data
                   WHERE module = 'lartdubati_investor_home' AND name = 'group_stock_investor')
 WHERE u.active AND NOT EXISTS (
       SELECT 1 FROM res_groups_users_rel e
        WHERE e.uid = u.id AND e.gid = (SELECT res_id FROM ir_model_data
                                         WHERE module = 'base' AND name = 'group_allow_export'))
UNION ALL
SELECT 'missing_rule', d.name, '' FROM (VALUES
    ('rule_menu_investor'), ('rule_users_investor'), ('rule_partner_investor'),
    ('rule_quick_start_action_investor'), ('rule_discuss_channel_investor'),
    ('rule_mail_message_investor'), ('rule_exports_investor')) d(name)
 WHERE NOT EXISTS (SELECT 1 FROM ir_model_data x
                    WHERE x.module = 'lartdubati_investor_home' AND x.name = d.name);

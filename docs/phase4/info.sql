-- Phase 4 precheck, information only (not blocking): investor accounts, their home
-- action and profile.
SELECT 'investor', u.login, COALESCE(a.name->>'en_US', '-') AS home_action,
       COALESCE(p.name->>'en_US', 'NO PROFILE: sees no stock') AS profile
  FROM res_users u
  JOIN res_groups_users_rel inv ON inv.uid = u.id
   AND inv.gid = (SELECT res_id FROM ir_model_data
                   WHERE module = 'lartdubati_investor_home' AND name = 'group_stock_investor')
  LEFT JOIN ir_actions a ON a.id = u.action_id
  LEFT JOIN lartdubati_stock_access p ON p.id = u.stock_access_id
 WHERE u.active
ORDER BY 2;

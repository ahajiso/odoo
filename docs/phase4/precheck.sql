-- Phase 4 precheck (read-only). Every row is a blocking finding; no row = OK.
-- Run by precheck.sh before the update (docs/phase4/README.md).

-- groups an investor account may hold: the investor group, Internal User and every group
-- it implies (transitively), « Access to export feature » (docs/phase4/PLAN.md §2, P4-5)
WITH RECURSIVE ids AS (
    SELECT (SELECT res_id FROM ir_model_data
             WHERE module = 'base' AND name = 'group_user') AS internal,
           (SELECT res_id FROM ir_model_data
             WHERE module = 'lartdubati_investor_home' AND name = 'group_stock_investor')
               AS investor,
           (SELECT res_id FROM ir_model_data
             WHERE module = 'base' AND name = 'group_allow_export') AS export
),
implied(gid) AS (
    SELECT internal FROM ids
    UNION
    SELECT r.hid FROM res_groups_implied_rel r JOIN implied i ON r.gid = i.gid
),
allowed AS (
    SELECT gid FROM implied
    UNION SELECT investor FROM ids
    UNION SELECT export FROM ids
)
-- 1. investor accounts holding another right: the owner removes it (Settings → Users)
SELECT 'forbidden_group' AS check_name, u.id AS record_id,
       u.login || CASE WHEN u.active THEN '' ELSE ' (archived)' END || ': '
           || string_agg(COALESCE(c.name->>'en_US' || ' / ', '')
                         || COALESCE(g.name->>'en_US', g.id::text), ', ') AS detail
  FROM res_users u
  JOIN res_groups_users_rel inv ON inv.uid = u.id AND inv.gid = (SELECT investor FROM ids)
  JOIN res_groups_users_rel rg ON rg.uid = u.id
  JOIN res_groups g ON g.id = rg.gid
  LEFT JOIN ir_module_category c ON c.id = g.category_id
 WHERE rg.gid NOT IN (SELECT gid FROM allowed)
 GROUP BY u.id, u.login, u.active
UNION ALL
-- 2. home page records the update adopts by name (in any of the three languages the
--    setup script wrote): at most one of each
SELECT 'home_record_duplicate', n, label || ': ' || n || ' records'
  FROM (SELECT names[1] AS label, tbl,
               CASE WHEN to_regclass(tbl) IS NULL THEN 0 ELSE
               (xpath('/row/n/text()', query_to_xml(format(
                 'SELECT count(*) AS n FROM %I WHERE name->>''en_US'' = ANY(%L::text[])'
                 ' OR name->>''fr_FR'' = ANY(%L::text[]) OR name->>''fa_IR'' = ANY(%L::text[])',
                 tbl, names, names, names), false, true, '')))[1]::text::int END AS n
          FROM (VALUES
            ('quick_start_screen', ARRAY['Investor Home', 'Accueil investisseur', 'خانه سرمایه‌گذار']),
            ('quick_start_screen_action', ARRAY['Financial', 'Financier', 'مالی']),
            ('quick_start_screen_action', ARRAY['Administrative', 'Administratif', 'اداری']),
            ('quick_start_screen_action', ARRAY['Commerce & Services', 'Commerce et services',
                                                'بازرگانی و خدمات']),
            ('quick_start_screen_action', ARRAY['Production', 'تولید'])) v(tbl, names)
       ) counts
 WHERE n > 1
ORDER BY 1, 2;

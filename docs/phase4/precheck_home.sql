-- Phase 4 precheck, home page records (read-only; run by precheck.sh when the OCA table
-- exists). Same checks as the pre-migration (lartdubati_investor_home/migrations/
-- 18.0.3.0.0/pre-migrate.py): every row is blocking; no row = OK.
-- 1. the old investor screen: at most one quick start screen named « Investor Home » in
--    any of the three languages (another profile's screen is not concerned);
-- 2. its buttons, searched only among that screen's buttons: each found at most once,
--    with its sequence and one of its expected actions.
WITH labels(name, names) AS (VALUES
    ('screen', ARRAY['Investor Home', 'Accueil investisseur', 'خانه سرمایه‌گذار'])),
screens AS (
    SELECT s.id FROM quick_start_screen s, labels l
     WHERE l.name = 'screen' AND (s.name->>'en_US' = ANY(l.names)
        OR s.name->>'fr_FR' = ANY(l.names) OR s.name->>'fa_IR' = ANY(l.names))
),
bound AS (
    SELECT res_id FROM ir_model_data
     WHERE module = 'lartdubati_investor_home' AND name = 'investor_home_screen'
),
screen AS (
    SELECT COALESCE((SELECT res_id FROM bound),
                    (SELECT id FROM screens WHERE (SELECT count(*) FROM screens) = 1)) AS id
),
soon AS (
    SELECT 'ir.actions.server,' || id AS ref FROM ir_act_server
     WHERE name->>'en_US' = 'Investor Home: coming soon'
    UNION SELECT 'ir.actions.client,' || res_id FROM ir_model_data
     WHERE module = 'lartdubati_investor_home' AND name = 'action_coming_soon'
),
financial AS (
    SELECT 'ir.actions.server,' || res_id AS ref FROM ir_model_data
     WHERE module = 'lartdubati_investor_home' AND name = 'action_server_stock_monitor'
    UNION SELECT 'ir.actions.client,' || res_id FROM ir_model_data
     WHERE module = 'lartdubati_investor_home' AND name = 'action_stock_monitor'
),
buttons(label, names, seq, kind) AS (VALUES
    ('Financial', ARRAY['Financial', 'Financier', 'مالی'], 10, 'financial'),
    ('Administrative', ARRAY['Administrative', 'Administratif', 'اداری'], 20, 'soon'),
    ('Commerce & Services', ARRAY['Commerce & Services', 'Commerce et services',
                                  'بازرگانی و خدمات'], 30, 'soon'),
    ('Production', ARRAY['Production', 'تولید'], 40, 'soon')),
found AS (
    SELECT b.label, b.seq, b.kind, a.id, a.sequence, a.action_ref_id
      FROM buttons b
      JOIN quick_start_screen_quick_start_screen_action_rel r
        ON r.quick_start_screen_id = (SELECT id FROM screen)
      JOIN quick_start_screen_action a ON a.id = r.quick_start_screen_action_id
     WHERE a.name->>'en_US' = ANY(b.names) OR a.name->>'fr_FR' = ANY(b.names)
        OR a.name->>'fa_IR' = ANY(b.names)
)
SELECT 'home_screen_ambiguous', count(*)::text,
       'quick start screens named Investor Home: ' || string_agg(id::text, ', ')
  FROM screens WHERE NOT EXISTS (SELECT 1 FROM bound) HAVING count(*) > 1
UNION ALL
SELECT 'home_button_duplicate', label, count(*) || ' buttons on the investor screen'
  FROM found GROUP BY label HAVING count(*) > 1
UNION ALL
SELECT 'home_button_mismatch', label,
       'button ' || id || ': sequence ' || sequence || ' (expected ' || seq || '), action '
       || COALESCE(action_ref_id, '-')
  FROM found
 WHERE sequence <> seq
    OR action_ref_id NOT IN (SELECT ref FROM soon WHERE kind = 'soon'
                             UNION SELECT ref FROM financial WHERE kind = 'financial')
ORDER BY 1, 2;

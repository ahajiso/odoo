-- Phase 3: addresses of the candidate monitor stocks (read-only, not blocking).
-- Printed by precheck.sh for the owner to confirm each city and country (the precheck
-- can only check that they are filled; e.g. TBER/Stock must read Berlin, DE).
SELECT l.complete_name, COALESCE(p.city, '-'), COALESCE(c.code, '-'),
       COALESCE(p.name, '(no address)')
  FROM stock_location l
  LEFT JOIN res_partner p ON p.id = l.address_id
  LEFT JOIN res_country c ON c.id = p.country_id
 WHERE l.active AND l.usage = 'internal'
   AND (l.id IN (SELECT lot_stock_id FROM stock_warehouse WHERE active)
        OR l.place_type = 'lent_out')
 ORDER BY l.complete_name;

# Production deployment: investor home and stock monitor

Checklist for deploying to the production database `artdubati` what was built and
tested on `artdubati_test`. **Run nothing here without the owner's explicit go.**

## 0. Mandatory prerequisite: separate test and production environments

Today one container `odoo_web` and one addons folder serve both databases: a `git pull`
for the test changes the code production runs, and a restart would load it against a
production schema that was not updated. Acceptable only while there is no real
production (situation on 08/10/2026, audit of phase 1). **Before any production use,
and before this checklist:**
- [ ] two Odoo services, e.g. `odoo_test_web` and `odoo_prod_web`, each with its own
  configuration file and `dbfilter` limited to its database (`list_db = False`);
- [ ] two independent code folders (custom and OCA addons), production pinned to a commit
  or tag already validated on test;
- [ ] two databases, `artdubati_test` and `artdubati` (they may stay on the same
  PostgreSQL server at first);
- [ ] two filestores (separate data volumes);
- [ ] independent backups of each database and filestore, restore tested;
- [ ] controlled promotion: the commit tested on `artdubati_test` (tests green, owner's
  checks) is the one checked out in the production folder, then the production modules
  are updated with production stopped, after a backup.

The steps below assume this separation: « the code » means the production folder, and
the commands use the production service.

References: `CLAUDE.md` (decisions), `docs/DEFINITIONS.md`, `docs/stock_monitor/README.md`,
`docs/investor_home/README.md`, manual cards ADM-10 to ADM-12, INV-01 to INV-04,
PARC-10, PARC-11, CPT-14, CPT-15.

## 1. Before the day
- [ ] All tests green on artdubati_test:
  `docker exec -i odoo_web odoo -d artdubati_test -u lartdubati_investor_home --test-enable --test-tags /lartdubati_investor_home --workers 0 --http-port 8079 --stop-after-init 2>&1 | tail -40`
- [ ] Owner has checked the test database in the three languages, logged in as an investor.
- [ ] Accountant's answers received, or deliberately postponed: asset profiles
  (account_asset_management), currency conversion choice, replacement price choice.
  The defaults (latest rate, product cost) can stay until then.
- [ ] Production code folder on the validated commit (section 0), and the OCA clones
  in `/opt/odoo/addons/` (contract-18, reporting-engine-18, web-18, server-ux-18, and
  the ones of maintenance_account and account_asset_management) are in the addons_path
  of `/opt/odoo/config/odoo.conf` (already true, since artdubati_test uses them).
- [ ] Users warned of a short interruption (two restarts).

## 2. Read-only pre-checks on production
Run in `docker exec -i odoo_db psql -U odoo -d artdubati`. Fix the data in Odoo (not in SQL)
before installing.

```sql
-- a) Active equipment without an internal stock: invisible in the monitor, and the
--    new constraint blocks their next edit. Give each one a stock (ADM-06, PARC-03).
SELECT e.id, e.name, l.complete_name, l.usage
FROM maintenance_equipment e LEFT JOIN stock_location l ON l.id = e.current_location_id
WHERE e.active AND (l.id IS NULL OR l.usage <> 'internal');

-- b) Warehouses without an address country: their stocks have no country/currency
--    in the monitor and escape country filters of access profiles.
SELECT w.code, w.name, p.name AS address, p.country_id
FROM stock_warehouse w LEFT JOIN res_partner p ON p.id = w.partner_id
WHERE w.active AND (p.id IS NULL OR p.country_id IS NULL);

-- c) Stock owned by a third party (shows as borrowed/rented in the monitor).
SELECT q.owner_id, count(*) FROM stock_quant q
WHERE q.owner_id IS NOT NULL
  AND q.owner_id NOT IN (SELECT partner_id FROM res_company)
GROUP BY q.owner_id;

-- d) Cost method of product categories (consumables must be average cost).
SELECT id, complete_name, property_cost_method FROM product_category ORDER BY id;
```

## 3. Backup (the rollback depends on it)
```
docker exec odoo_db pg_dump -U odoo -Fc artdubati > artdubati_$(date +%Y%m%d_%H%M).dump
docker exec odoo_web tar czf - -C /var/lib/odoo/.local/share/Odoo/filestore artdubati \
  > artdubati_filestore_$(date +%Y%m%d_%H%M).tgz
```
- [ ] Both files exist, have a sensible size, and are copied off the server.

## 4. Install
One command, dependencies are pulled in automatically (base_maintenance,
sql_request_abstract, report_xlsx, …):
```
docker exec -i odoo_web odoo -d artdubati -i account_asset_management,contract,maintenance_equipment_contract,maintenance_account,bi_sql_editor,web_quick_start_screen,base_menu_visibility_restriction,lartdubati_investor_home --stop-after-init 2>&1 | grep -E "ERROR|CRITICAL|Traceback" ; docker restart odoo_web
```
- [ ] No ERROR / CRITICAL / Traceback. French and Persian translations load with the install.

## 5. Configure (as administrator, in this order)
1. [ ] Inventory > Configuration > Settings: tick **Consignment** (owner on receipts).
2. [ ] Consumable product categories (look them up by name, check the ids from query 2d,
   never assume they equal the test ids 11-17): Costing Method = **Average Cost (AVCO)**.
   Accountant's approval first if stock already exists in them.
3. [ ] Settings > Inventory > **Stock Monitor**: currency conversion and replacement price
   (defaults: Latest Rate, Product Cost) — ADM-12.
4. [ ] Inventory > Configuration > Locations: Place Type **Lent Out** on stocks lent to a
   third party (others stay Physical) — ADM-06.
5. [ ] Asset profiles (account_asset_management) as given by the accountant — CPT-01, CPT-03.
6. [ ] Supplier contracts for rented equipment and consumables (Invoicing > Vendors >
   Supplier Contracts), linked to the equipment — PARC-11, CPT-14.
7. [ ] The two SQL reports: Dashboards > Configuration > SQL Views, exactly as in
   `docs/stock_monitor/README.md` (not materialized, domain, menus, field mapping), then
   their translations:
   `ODOO_URL=https://erp.lartdubati.com ODOO_DB=artdubati ODOO_LOGIN=… ODOO_PASSWORD=… python3 docs/stock_monitor/apply_translations.py`
8. [ ] Home page and hidden menus:
   `ODOO_URL=https://erp.lartdubati.com ODOO_DB=artdubati ODOO_LOGIN=… ODOO_PASSWORD=… python3 docs/investor_home/setup_investor_home.py`
   (after step 7: it needs the Stock Monitor action).
9. [ ] Stock access profiles (Settings > Users & Companies > Stock Access Profiles) — ADM-11.
10. [ ] Investor users (`docs/investor_home/README.md`, ADM-10): group Stock Monitor Investor
    only, a profile, home page; or `setup_investor_home.py <login> …`.

Credentials are passed in the environment of the one command, never written to a file.

## 6. Post-checks
- [ ] As administrator: Dashboards > Stock Monitor - Values & Rent opens; totals per stock
  match Inventory > Reporting > Stock (quantities, values) for two sample stocks.
- [ ] As one investor, in their language: home page with 4 buttons; Financial opens the
  monitor; the 3 others show "coming soon"; only the profile's stocks, families and
  ownerships appear; no Inventory, Maintenance or Discuss menu; no accounting/rent columns.
- [ ] An investor with no profile sees no stock.
- [ ] Create then cancel a test receipt and a test equipment (constraint: stock required).
- [ ] Odoo log quiet: `docker logs --since 30m odoo_web 2>&1 | grep -E "ERROR|CRITICAL"`.

## 7. Rollback
Light (configuration wrong, data fine): fix in the UI, or uninstall
`lartdubati_investor_home` then the OCA modules from Apps (reverse order of section 4).
Uninstalling removes the place types, profiles, settings and the two reports.

Full (data damaged): restore the backup of section 3.
```
docker stop odoo_web
docker exec odoo_db dropdb -U odoo artdubati
docker exec odoo_db createdb -U odoo -O odoo artdubati
docker exec -i odoo_db pg_restore -U odoo -d artdubati --no-owner < artdubati_<stamp>.dump
docker start odoo_web
docker exec odoo_web sh -c 'rm -rf /var/lib/odoo/.local/share/Odoo/filestore/artdubati'
docker exec -i odoo_web tar xzf - -C /var/lib/odoo/.local/share/Odoo/filestore < artdubati_filestore_<stamp>.tgz
docker restart odoo_web
```

## 8. After deployment
- [ ] Manual (FR, then EN/FA): remove "artdubati_test only / pending deployment" from the
  Investor intro, ADM-10 to ADM-12, PARC-10, PARC-11, CPT-14, CPT-15 and REF-08; update the
  module table of `docs/manual/definitions-manuel.md` §4; changelog line; regenerate
  /manuel (`docs/manual/maintenance-manuel-odoo.md`).
- [ ] CLAUDE.md: mark phase 5 done and production deployed (date).
- [ ] Ask the owner whether to delete the TEST data and test users of artdubati_test.

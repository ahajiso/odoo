# Phase 1 – data model on artdubati_test

Plan: `PLAN.md`. Characterisations: `CHARACTERISATION.md`. Run by the owner on the
server, in this order, only after the audit and once the code is on `main`.

Rehearsed locally on 08/10/2026 (Odoo 18 + OCA heads, database installed with the
previous versions of both modules, test data, and the two stock monitor queries of
`docs/stock_monitor/` created as SQL views): preparation script, update of both
modules, 37 tests passing, both monitor views intact.

Do not restart `odoo_web` between the `git pull` (step 2) and the module update
(step 6): the new Python code would be loaded against the old database.

## 1. Backup

```bash
set -o pipefail
mkdir -p /opt/odoo/backups /opt/odoo/logs
docker exec odoo_db pg_dump -U odoo -Fc artdubati_test \
  > /opt/odoo/backups/artdubati_test_$(date +%F_%H%M)_phase1.dump && echo BACKUP OK
```

## 2. Code

```bash
cd /opt/odoo/addons/custom && git pull && git log --oneline -1
```

## 3. Preparation script, dry run

```bash
cd /opt/odoo/addons/custom/docs/phase1
export ODOO_URL=https://erp.lartdubati.com ODOO_DB=artdubati_test ODOO_LOGIN=<admin login>
read -s ODOO_PASSWORD && export ODOO_PASSWORD
python3 setup_phase1.py
```

It lists every equipment with its bill line, contracts and maintenance requests, the
lent-out locations, and the maintainable storable products not tracked by serial
number (one known: « 1800W corded table saw, 254mm blade, with wheeled stand »). For
each such product, choose in Odoo: tracking by unique serial number, archive, or
delete; then rerun until « All checks passed ».

## 4. SQL views before the update

The update drops removed columns with `CASCADE`, and Odoo drops any view reading a
column whose type it converts. Save the list of views that depend on the tables the
modules change:

```bash
cat > /opt/odoo/logs/views.sql <<'SQL'
SELECT DISTINCT v.relname
FROM pg_depend d
JOIN pg_rewrite r ON r.oid = d.objid
JOIN pg_class v ON v.oid = r.ev_class
JOIN pg_class t ON t.oid = d.refobjid
WHERE d.classid = 'pg_rewrite'::regclass AND v.relname <> t.relname
  AND t.relname IN ('maintenance_equipment', 'maintenance_request', 'stock_location',
                    'contract_line', 'contract_contract', 'account_move_line',
                    'product_category', 'product_template', 'stock_move_line',
                    'res_company')
ORDER BY 1;
SQL
docker exec -i odoo_db psql -U odoo -d artdubati_test -At < /opt/odoo/logs/views.sql \
  | tee /opt/odoo/logs/views_before_phase1.txt
```

Expected: the two stock monitor reports (`x_bi_sql_view_stock_monitor`,
`x_bi_sql_view_stock_monitor_full`) and standard Odoo report views such as
`report_stock_quantity` (Odoo recreates its own report views at each update).

## 5. Preparation script, apply

```bash
python3 setup_phase1.py --apply
python3 setup_phase1.py          # control: 0 equipment, nothing left to do
```

## 6. Module update and tests

```bash
set -o pipefail
LOG=/opt/odoo/logs/phase1_update_$(date +%F_%H%M).log
docker exec -i odoo_web odoo -d artdubati_test \
  -u maintenance_shareholder_equipment,lartdubati_investor_home \
  --stop-after-init 2>&1 | tee "$LOG" && echo "UPDATE COMMAND OK"
grep -E " (ERROR|CRITICAL) " "$LOG" && echo "PROBLEM FOUND" || echo "no ERROR/CRITICAL line"

LOGT=/opt/odoo/logs/phase1_tests_$(date +%F_%H%M).log
docker exec -i odoo_web odoo -d artdubati_test \
  -u maintenance_shareholder_equipment,lartdubati_investor_home --test-enable \
  --test-tags /maintenance_shareholder_equipment,/lartdubati_investor_home \
  --workers 0 --http-port 8079 --stop-after-init 2>&1 | tee "$LOGT" | grep -E "tests when|FAIL:|ERROR:"
docker restart odoo_web
```

Expected: « UPDATE COMMAND OK », « no ERROR/CRITICAL line », then
« 0 failed, 0 error(s) of 37 tests ». One log line « duplicate key value violates
unique constraint "maintenance_equipment_stock_lot_uniq" » is normal: it is the test
of that constraint. A warning « no account 613500 » is not expected on artdubati_test
(the account exists).

## 7. SQL views after the update

```bash
docker exec -i odoo_db psql -U odoo -d artdubati_test -At < /opt/odoo/logs/views.sql \
  > /opt/odoo/logs/views_after_phase1.txt
diff /opt/odoo/logs/views_before_phase1.txt /opt/odoo/logs/views_after_phase1.txt \
  && echo "SAME VIEWS"
```

Expected: « SAME VIEWS ». If a monitor view is missing, open its report in
**Dashboards → Configuration → SQL Views**, set it back to draft and validate it again
(bi_sql_editor recreates the view), then tell Claude.

## 8. Checks in the interface

- **Maintenance → Equipment**: a new equipment shows the « To Complete » state, the
  « Ownership and Stock » tab, and the « Integrate » button.
- **Settings → Invoicing**: block « Equipment (test choices, see the accountant) »
  with the rental account 613500 and the refund option off.
- **Inventory → Configuration → Locations**: `Bg/TEST Lent out` archived.

Send Claude: the outputs of steps 3, 5 and 7, and the test line of step 6.

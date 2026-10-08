# Phase 1 – data model on artdubati_test

Plan: `PLAN.md`. Characterisations: `CHARACTERISATION.md`. Run by the owner on the
server, in this order, only after the audit and once the code is on `main`.

Rehearsed locally on 08/10/2026 (Odoo 18 + OCA heads, database installed with the
previous versions of both modules, test data, and the two stock monitor queries of
`docs/stock_monitor/` created as SQL views): preparation script, update of both
modules, tests passing (47 after the audit fixes), deploy_phase1.sh rehearsed with a fake docker (success, update failure, test failure,
stop / start failure, network count), both monitor views intact.

Do not restart `odoo_web` between the `git pull` (step 2) and the module update
(step 6): the new Python code would be loaded against the old database.

Order: 1 backup, 2 code, 3 preparation dry run, 4 views before, 5 preparation apply,
6 update and tests (service stopped; 6b rollback if it fails), flag of the fixed-asset
category, 7 views after, 8 interface checks.

## 1. Backup

```bash
set -o pipefail
mkdir -p /opt/odoo/backups /opt/odoo/logs
docker exec odoo_db pg_dump -U odoo -Fc artdubati_test \
  > /opt/odoo/backups/artdubati_test_$(date +%F_%H%M)_phase1.dump && echo BACKUP OK
```

## 2. Code

```bash
cd /opt/odoo/addons/custom && git rev-parse HEAD > /opt/odoo/logs/phase1_previous_commit
git pull && git log --oneline -1
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

## 6. Module update and tests, service stopped

The update must not run while the application serves requests. `odoo_web` serves every
database of the server, so **all of them are unavailable during this step** (a few
minutes). Acceptable only because there is no real production yet: separate test and
production environments are a mandatory prerequisite before any production use
(`docs/deployment/investor_home.md`, section 0). `deploy_phase1.sh` runs the update and the tests in a one-off
container with the same image, volumes, network and environment as `odoo_web`.

Check first what will be reused (prints names, not the secret values):

```bash
docker inspect -f 'image={{.Config.Image}}' odoo_web
docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}network={{$k}} {{end}}' odoo_web
docker inspect -f '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}' odoo_web
docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' odoo_web | cut -d= -f1
```

Expected: one image, one network, the mounts of `/etc/odoo`, `/mnt/extra-addons` and the
data volume, and environment variable names: either `HOST`, `USER`, `PASSWORD`, or only
`ODOO_RC` (database settings then read from the mounted configuration file, as on the
test server on 08/10/2026). If the output differs, stop and send it to Claude.

Then, with the backup file of step 1:

```bash
bash /opt/odoo/addons/custom/docs/phase1/deploy_phase1.sh /opt/odoo/backups/<backup of step 1>.dump
```

The script stops `odoo_web`, updates both modules, runs the tests and restarts
`odoo_web` only if everything passed. Expected last lines: « UPDATE OK »,
« TESTS OK: 0 failed, 0 error(s) of 47 tests », « odoo_web started ». One log line
« duplicate key value violates unique constraint "maintenance_equipment_stock_lot_uniq" »
in the test log is normal: it is the test of that constraint.

At the first failure it prints « FAILED: … » and **leaves `odoo_web` stopped**: go to
6b. The temporary file holding `odoo_web`'s environment is always removed.

### 6b. Rollback (only after a FAILED)

Odoo commits after each module, so a failure can leave the database partly updated:
restore the backup and the previous code before restarting. `odoo_web` is stopped.

```bash
set -euo pipefail
BACKUP=/opt/odoo/backups/<backup of step 1>.dump
cd /opt/odoo/addons/custom && git checkout "$(cat /opt/odoo/logs/phase1_previous_commit)"
docker exec odoo_db dropdb -U odoo artdubati_test
docker exec odoo_db createdb -U odoo artdubati_test
docker exec -i odoo_db pg_restore -U odoo -d artdubati_test --no-owner < "$BACKUP" \
  && echo "RESTORE OK"
docker start odoo_web
```

Then send Claude the two logs named by the script. The repository is left in
« detached HEAD »; `git checkout main` brings it back once the fix is pushed.

Then flag the fixed-asset category (dry run, then apply):

```bash
cd /opt/odoo/addons/custom/docs/phase1
python3 setup_phase1.py --after-update
python3 setup_phase1.py --after-update --apply
```

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

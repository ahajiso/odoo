# Phase 3 – deployment on artdubati_test

Stock monitor on revision 2: a module model on one SQL view (`lartdubati.stock.monitor`),
an OWL dashboard as the main interface, the standard views as the secondary one, access
profiles enforced by global rules. Plan: `docs/phase3/PLAN.md` revision 5; decisions in
`docs/DEFINITIONS.md` (Stock, Measures, Currency, Access) and the accountant's questions
in `docs/QUESTIONS_COMPTABLE.md` (C12, C19, C20, C21, C22).

Modules:
- `maintenance_shareholder_equipment` 18.0.3.1.0 → 18.0.4.0.0 (monitor stocks, stored
  contract currency, obsolete fields removed);
- `lartdubati_investor_home` 18.0.1.6.0 → 18.0.2.0.0 (monitor, dashboard, access).

Expected tests: **191 tests** (both modules). They include 3 tour tests and the
Hoot tests of the dashboard, which need Chrome and the Python module `websocket-client`:
without them in `odoo_web` (the case of the 2f deployment) they are counted as skipped,
and the interface checks of step 8 cover them. The performance test (`monitor_perf`) is
not in this count; it runs only on request.

Screenshots on local demo data: `docs/phase3/screenshots/` (en_US, fr_FR, fa_IR at 1440,
1024 and 768 px, and the detail panel at 1440 px; fa_IR mirrored right to left).

**Run nothing before the audit of the code and the owner's go.**

## 0. Before the deployment (owner's decisions, the running version keeps serving)

### 0a. Equipment linked by OCA maintenance_equipment_contract
The monitor reads the rent from `contract.line.equipment_id` (phase 1), not from this
module's many-to-many table. List what it still holds (read-only):

```bash
docker exec -i odoo_db psql -U odoo -d artdubati_test -c "
select r.contract_contract_id, c.name as contract, r.maintenance_equipment_id,
       e.name->>'en_US' as equipment
  from contract_contract_maintenance_equipment_rel r
  join contract_contract c on c.id = r.contract_contract_id
  join maintenance_equipment e on e.id = r.maintenance_equipment_id;"
```

For each row: either the contract already has a line with this equipment (Contract →
line → Equipment and Equipment Relation), or it is old test data. Send the list to
Claude if a line must be created. Then uninstall the module (Apps → OCA
« Maintenance Equipment Contract » → Uninstall). An error « relation does not exist » on
the query means it is already gone.

### 0b. The two old reports (OCA bi_sql_editor)
Dashboards → Configuration → SQL Views: open « Stock Monitor » (`stock_monitor`) and
« Stock Monitor - Values & Rent » (`stock_monitor_full`), set each back to draft (this
drops its SQL view and its menu), then delete it. They read columns the update removes;
the precheck refuses to go on while a view still reads them. Uninstalling
`bi_sql_editor` itself is the owner's choice (P5).

### 0c. Stock addresses
Every warehouse stock and lent-out location becomes a monitor stock: each needs an
address with a city and a country. Set on 09/10/2026 for Bg/Stock (Bougival, FR),
TIST/Stock (Istanbul, TR) and TBER/Stock (DE); TBER/Stock's contact first read
« PARIS CEDEX 20 », corrected to Berlin by the owner on 09/10/2026. The precheck can
only check that city and country are filled: it prints every candidate stock with its
address (step 3), to confirm by eye, TBER/Stock with **Berlin | DE**. To read it now:

```bash
docker exec -i odoo_db psql -U odoo -d artdubati_test -At -F ' | ' \
  < /tmp/phase3/docs/phase3/stock_addresses.sql   # after step 2
```

## 1. Backup (database and filestore)

```bash
set -o pipefail
mkdir -p /opt/odoo/backups /opt/odoo/logs
STAMP=$(date +%F_%H%M)
docker exec odoo_db pg_dump -U odoo -Fc artdubati_test \
  > /opt/odoo/backups/artdubati_test_${STAMP}_phase3.dump && echo DB BACKUP OK
FS=/var/lib/odoo/.local/share/Odoo/filestore
docker exec odoo_web ls -d $FS/artdubati_test   # must print the folder
docker exec odoo_web tar -czf - -C $FS artdubati_test \
  > /opt/odoo/backups/artdubati_test_${STAMP}_phase3_filestore.tar.gz && echo FILESTORE BACKUP OK
ls -l /opt/odoo/backups/*phase3*
cd /opt/odoo/addons/custom && git rev-parse HEAD > /opt/odoo/logs/phase3_previous_commit
```

## 2. Fetch the new code without touching the working tree

```bash
cd /opt/odoo/addons/custom
git fetch origin +refs/heads/main:refs/remotes/origin/main
git log -1 --oneline origin/main        # must be the commit announced by Claude
rm -rf /tmp/phase3 && mkdir -p /tmp/phase3
git archive origin/main docs/phase3 docs/investor_home docs/deploy_modules.sh \
  | tar -x -C /tmp/phase3
ls /tmp/phase3/docs/phase3/             # precheck.sh  precheck.sql  stock_addresses.sql ...
git status --short | head               # nothing changed in the working tree
```

## 3. Precheck (must print PRECHECK OK)

```bash
bash /tmp/phase3/docs/phase3/precheck.sh artdubati_test
```

It first prints the addresses of the candidate stocks: check each city and country
(TBER/Stock: Berlin | DE); if one is wrong, correct the contact and run it again.
It refuses (exit 1) while a view still reads a removed column (step 0b), the
equipment-contract table holds rows (0a), or a candidate stock has no address with a
city and a country (0c). Fix what it lists and run it again. Do not go on.

## 4 to 6. Stop, update the working tree, update and test, restart

One command, run from the copy of step 2 (the working tree still holds the previous
script), with the commit announced by Claude:

```bash
bash /tmp/phase3/docs/deploy_modules.sh \
  /opt/odoo/backups/<dump of step 1> 191 phase3 <commit announced by Claude>
```

In this order, nothing changed until the stop (audit of 643f95e, point 3):
1. checks before anything: the commit is `origin/main`, the working tree has no local
   change, the commit follows the current one (fast-forward);
2. stops `odoo_web` and checks it is stopped: the running server never reads the new
   files;
3. moves the working tree to the commit (`git merge --ff-only`) and checks `HEAD`;
4. updates both modules (the migration flags the monitor stocks in company currency and
   moves a company still on « No Conversion » to « Latest Rate »);
5. runs the tests;
6. restarts `odoo_web` only if everything passed.

A refusal at 1 changes nothing (`odoo_web` keeps running). On « FAILED » from 2 on, it
leaves `odoo_web` stopped: go to the rollback.

### Rollback (only after a FAILED)

```bash
BACKUP=/opt/odoo/backups/<dump of step 1>
cd /opt/odoo/addons/custom && git checkout "$(cat /opt/odoo/logs/phase3_previous_commit)"
docker exec odoo_db dropdb -U odoo artdubati_test
docker exec odoo_db createdb -U odoo artdubati_test
docker exec -i odoo_db pg_restore -U odoo -d artdubati_test --no-owner < "$BACKUP" \
  && echo RESTORE OK
docker start odoo_web
```

The filestore is not changed by this update. Then send Claude the two logs named by the
script.

## 7. Post-update check (must print no row)

```bash
docker exec -i odoo_db psql -U odoo -d artdubati_test -At -F ' | ' \
  < /opt/odoo/addons/custom/docs/phase3/postcheck.sql
```

It lists: a missing monitor view, an obsolete column still there, a difference between
the monitor's asset or consumable rows and their source tables, a candidate stock not
flagged.

## 8. Home page and interface checks

Repoint the Financial button of the investor home page to the dashboard (same script as
before, credentials typed, never stored):

```bash
cd /tmp/phase3/docs/investor_home
read -r -p "Login: " ODOO_LOGIN && read -r -s -p "Password: " ODOO_PASSWORD && echo
export ODOO_URL=https://erp.lartdubati.com ODOO_DB=artdubati_test ODOO_LOGIN ODOO_PASSWORD
python3 setup_investor_home.py
unset ODOO_PASSWORD
```

Then, with the profiles (Playwright with their passwords, never stored):
1. **investor without Inventory rights** (`test_investor`): home page → Financial opens
   the dashboard; only the stocks of the profile; cards « Items » and « Inventory
   value » only; no stock value, net book value or rent; « Detailed analysis » opens the
   list without those columns; no error.
2. **Inventory user**: stock value and current rents; staff alerts and controls; the
   « Outside any monitor stock » card if any.
3. **accountant** (Accounting / Read-only): net book value with « of which …
   provisional », rent paid.
4. In Persian (fa_IR): the dashboard is mirrored (right to left). If it is not, the
   `rtlcss` command is missing in `odoo_web` (PLAN.md §9).
5. Figures to compare with Inventory: Bg/Stock quantities; the saw (equipment 484):
   inventory value 15 € HT, stock value 0, net book value 0, alert « No fixed asset
   (expensed) » for staff.

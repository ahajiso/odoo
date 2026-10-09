# Phase 2 – equipment operations on artdubati_test

Plan: `PLAN.md` (revision 4, development authorised on 08/10/2026). Run by the owner on
the server, in this order, only after the audit of the code and once it is on `main`.

Rehearsed locally on 08/10/2026 (Odoo 18 + OCA heads): update from the phase 1
database (18.0.2.0.0 → 18.0.3.0.0) with the two stock monitor queries as SQL views
(views unchanged), 89 tests passing, `docs/deploy_modules.sh` with a fake docker
running the real update and tests, `setup_phase2.py` dry run, apply (on a scratch copy
allowing the local database) and control run, operation form opened in a browser.

**What changes for the users at once:** after the update, supplier receipts and
acquisitions, consumables included, can only be validated through an **equipment
operation** (Inventory → Operations → Equipment Operations); the standard « Validate »
of a supplier receipt is refused. Nobody can execute an operation before being given
the group « Equipment Operator » (step 7). Internal transfers and physical inventory
counts of consumables stay standard.

Production: one `odoo_web` serves every database, so the site is unavailable during
step 4 (a few minutes). Acceptable only while there is no real production
(`docs/deployment/investor_home.md`, section 0).

Prerequisites (true on artdubati_test, checked by the tests and the script): the
French localisation `l10n_fr_account` installed (the tests build a French company with
its chart of accounts); every warehouse receives in one step (« Receive goods directly »),
since the equipment operations refuse receipts in several steps.

Order: 1 backup, 2 code, 3 views before, 4 update and tests (4b rollback if it fails),
5 settings script, 6 views after, 7 groups, 8 interface checks.

## 1. Backup

```bash
set -o pipefail
mkdir -p /opt/odoo/backups /opt/odoo/logs
docker exec odoo_db pg_dump -U odoo -Fc artdubati_test \
  > /opt/odoo/backups/artdubati_test_$(date +%F_%H%M)_phase2.dump && echo BACKUP OK
ls -l /opt/odoo/backups/*phase2.dump
```

## 2. Code

```bash
cd /opt/odoo/addons/custom && git rev-parse HEAD > /opt/odoo/logs/phase2_previous_commit
git pull && git log --oneline -1
```

Do not restart `odoo_web` before step 4.

## 3. SQL views before the update

The query file of phase 1 is reused (`/opt/odoo/logs/views.sql`):

```bash
docker exec -i odoo_db psql -U odoo -d artdubati_test -At < /opt/odoo/logs/views.sql \
  | tee /opt/odoo/logs/views_before_phase2.txt
```

Expected: the same four views as after phase 1 (`report_stock_quantity`,
`vendor_delay_report`, `x_bi_sql_view_stock_monitor`, `x_bi_sql_view_stock_monitor_full`).

## 4. Module update and tests, service stopped

Check first, as in phase 1, that nothing changed in the container (prints names only):

```bash
docker inspect -f 'image={{.Config.Image}}' odoo_web
docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}network={{$k}} {{end}}' odoo_web
docker inspect -f '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}' odoo_web
docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' odoo_web | cut -d= -f1
```

Expected (08/10/2026): image `odoo-web`, network `odoo_default`, the mounts of
`/mnt/extra-addons`, `/var/lib/odoo` and `/etc/odoo`, variables `PATH`, `LANG`,
`ODOO_VERSION`, `ODOO_RC`. If the output differs, stop and send it to Claude.

Then, with the backup of step 1 and the expected number of tests (89):

```bash
bash /opt/odoo/addons/custom/docs/deploy_modules.sh /opt/odoo/backups/<backup of step 1>.dump 89 phase2
```

Expected last lines: « UPDATE OK », « TESTS OK: 0 failed, 0 error(s) of 89 tests »,
« odoo_web started. Update phase2 done. ». Log lines with « ERROR » inside the test log
are normal when they belong to tests checking a refusal (the script only fails on the
exit code or on a wrong count).

At the first failure it prints « FAILED: … » and **leaves `odoo_web` stopped**: go to 4b.

### 4b. Rollback (only after a FAILED)

```bash
set -euo pipefail
BACKUP=/opt/odoo/backups/<backup of step 1>.dump
cd /opt/odoo/addons/custom && git checkout "$(cat /opt/odoo/logs/phase2_previous_commit)"
docker exec odoo_db dropdb -U odoo artdubati_test
docker exec odoo_db createdb -U odoo artdubati_test
docker exec -i odoo_db pg_restore -U odoo -d artdubati_test --no-owner < "$BACKUP" \
  && echo "RESTORE OK"
docker start odoo_web
```

Then send Claude the two logs named by the script. `git checkout main` brings the
repository back once the fix is pushed.

## 5. Settings script (after the update)

```bash
cd /opt/odoo/addons/custom/docs/phase2
export ODOO_URL=https://erp.lartdubati.com ODOO_DB=artdubati_test ODOO_LOGIN=<admin login>
read -s ODOO_PASSWORD && export ODOO_PASSWORD
python3 setup_phase2.py            # dry run
python3 setup_phase2.py --apply
python3 setup_phase2.py            # control: everything « found », « already flagged »
```

The dry run checks the accounts 613500, 708300, 778000, 455100, 603200, then shows what
it would create: the three service products (« Prêt de matériel », « Location de
matériel (payée) » on 613500, « Location de matériel (facturée) » on 708300), the three
acquisition locations (« Acquisitions - Don » 778000, « … Apport en compte courant »
455100, « … Régularisation » 603200), and the flag on `WH/Chez tiers`. It also lists,
without changing anything (and stops on a warehouse receiving in several steps): serial numbers in stock without equipment (expected none),
**open receipts** (to be received through operations from now on), lent-out locations
without address, the incoming operation types and the members of the two new groups.
Any error stops it before writing. Accounting choices: test choices, see
`docs/QUESTIONS_COMPTABLE.md` (C10, C16, C17).

## 6. SQL views after the update

```bash
docker exec -i odoo_db psql -U odoo -d artdubati_test -At < /opt/odoo/logs/views.sql \
  > /opt/odoo/logs/views_after_phase2.txt
diff /opt/odoo/logs/views_before_phase2.txt /opt/odoo/logs/views_after_phase2.txt \
  && echo "SAME VIEWS"
```

## 7. Groups (owner's choice)

**Settings → Users → <user> → Maintenance**: « Equipment Operator » (prepares and
executes; implies Inventory / User) and/or « Equipment Operations Approver » (approves
orders, bills, contracts, acquisitions; moves no stock). For the interface tests, four
profiles are useful: operator only, approver only, both, and an Inventory user with
neither.

## 8. Checks in the interface

- **Inventory → Operations → Equipment Operations**: the list opens; « New » shows the
  form with the statuses Draft / To Approve / Approved / Done.
- **Settings → Invoicing**, block « Equipment »: the three contract products and the
  three acquisition sources are filled.
- **Inventory → Configuration → Locations → WH/Chez tiers**: « Parent of Off-Site
  Stocks » ticked.
- A standard « Validate » on an open supplier receipt is refused with a message
  pointing to the equipment operations (try it only on a receipt you will then receive
  through an operation).

Send Claude: the outputs of steps 3, 5 (dry run, apply, control) and 6, and the last
lines of step 4.

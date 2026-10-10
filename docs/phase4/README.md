# Phase 4 – deployment on artdubati_test

Investor accounts read only the stock monitor; the investor home page is versioned in
the module. Plan: `docs/phase4/PLAN.md` (revision 5, implementation notes §9);
characterisation of P4-1: `docs/phase4/CHARACTERISATION.md` (no code yet, separate plan);
HTTP routes and investor accounts: `docs/phase4/ROUTES.md`.

Module: `lartdubati_investor_home` 18.0.2.0.0 → 18.0.3.0.0 (new dependency
`web_quick_start_screen`, already installed on artdubati_test).
`maintenance_shareholder_equipment` is updated too (approver: read access with an empty
scope on repair and sale orders; new dependencies `repair` and `sale_stock`, both
installed on the server).

Expected tests on the server: **231 tests** (both modules; 232 locally on a
database with the server's 122 modules, log kept in `docs/phase4/test_logs/`). The tours
and the Hoot tests need Chrome and `websocket-client`: without them in `odoo_web` they
are counted as skipped, as in phases 2f and 3; the interface checks of step 9 cover
them. The real websocket test class is skipped as a whole and not counted (first
attempt: 229 for 230), hence one less on the server. The JSON-RPC, action, URL and
password tests of the investor security do not need a browser; the websocket channel
list is also tested without `websocket-client` (`TestInvestorBusChannels`).

**Run nothing before the audit of the code and the owner's go. One atomic update: no
partial deployment.** Every script below stops at the first problem; nothing here has a
name to type by hand.

## 0. Before the deployment (the running version keeps serving)

Q7: `test_investor` must hold no right other than the investor group (and what Odoo
gives every internal user). Settings → Users → `test_investor` → Access Rights:
Purchase empty, then Save. The precheck (step 3) refuses the update until every
investor account is clean; nothing is removed automatically.

## 1. Fetch the new code without touching the working tree

```bash
cd /opt/odoo/addons/custom
git fetch origin +refs/heads/main:refs/remotes/origin/main
git log -1 --oneline origin/main        # must be the commit announced by Claude
rm -rf /tmp/phase4 && mkdir -p /tmp/phase4
git archive origin/main docs/phase4 docs/deploy_modules.sh docs/backup_db.sh \
  docs/restore_db.sh | tar -x -C /tmp/phase4
ls /tmp/phase4/docs/ /tmp/phase4/docs/phase4/
git status --short | head               # nothing changed in the working tree
```

## 2. Same modules as the tested database (must print MODULES OK)

```bash
bash /tmp/phase4/docs/phase4/check_modules.sh before
```

It compares, name and version, every module installed on artdubati_test with
`docs/phase4/modules.txt` (the 122 modules of the local database that ran the tests; the
two updated modules must still be at their current versions). Any difference stops
(first deployment attempt, 10/10/2026: the tests had run on another set of modules).
It also prints the image of `odoo_web` and its Odoo version, for the record; the Odoo
and OCA revisions of the tested code are at the top of `modules.txt`.

## 3. Precheck (must print PRECHECK OK)

```bash
bash /tmp/phase4/docs/phase4/precheck.sh artdubati_test
```

It prints, for information, the investor accounts (home action, profile) and the menus
hidden by `base_menu_visibility_restriction`, then refuses (exit 1) while (precheck.sql,
precheck_home.sql):
- an investor account holds a forbidden right (`forbidden_group`, with the groups to
  remove): fix it in Settings → Users, run it again;
- the old investor screen is ambiguous or one of its buttons does not match its
  expected name, sequence and action (`home_screen_ambiguous`, `home_button_duplicate`,
  `home_button_mismatch`): send it to Claude (the update would stop). Other profiles'
  quick start screens are not concerned.

## 4. Backup, checked (must print BACKUP OK)

```bash
bash /tmp/phase4/docs/backup_db.sh phase4
```

`backup_db.sh` (`set -euo pipefail`): dump and filestore archive under temporary
names; the dump read back (`pg_restore --list`) and **restored completely into a
temporary database**, whose modules and record counts are compared with artdubati_test,
then dropped; the archive listed (`tar -tzf`) and its files counted; then the final
names, their SHA-256, and last the manifest `/opt/odoo/logs/phase4_backup`. Any failure
leaves no manifest, so neither the deployment nor the rollback can use a bad backup.
Read-only for artdubati_test (a few minutes; it needs free disk space for one more copy
of the database).

## 5 to 7. Stop, update the working tree, update and test, restart

```bash
BACKUP=$(sed -n 's/^DUMP=//p' /opt/odoo/logs/phase4_backup)
COMMIT=$(git -C /opt/odoo/addons/custom rev-parse --short origin/main)
echo "$BACKUP $COMMIT"     # the dump of step 4 and the commit announced by Claude
bash /tmp/phase4/docs/deploy_modules.sh "$BACKUP" 231 phase4 "$COMMIT"
```

Same script as phase 3: checks first, stops `odoo_web`, moves the working tree to the
commit, updates both modules, runs the tests, restarts only if everything passed. The
update adopts the home page records of the old setup script (found by their name in
English, French or Persian: the script could leave the Persian name in the English
value), rewrites their English names, keeps their French and Persian ones, and gives
every investor account the new home action. On « FAILED » it leaves `odoo_web`
stopped: send the logs to Claude, then the rollback.

### Rollback (only after a FAILED)

```bash
bash /tmp/phase4/docs/restore_db.sh phase4
```

`restore_db.sh` changes nothing before every check passed (manifest, both files and
their SHA-256, dump and archive readable, code commit, clean working tree). Then, with
`odoo_web` stopped: the dump is restored into a new database, and only when that
succeeded the current database is **renamed** (kept, not dropped) and the restored one
takes its name; the filestore is restored the same way (the current one renamed, kept);
the code goes back to the commit of the backup; `odoo_web` is started. It prints the
versions of the two modules: `18.0.2.0.0` and `18.0.4.0.0`. The kept database
(`artdubati_test_before_restore_<stamp>`) and filestore are removed later, by hand,
once Claude has read the logs. Rehearsed locally (backup, damage to the database, the
filestore and the code, refused restore with a wrong checksum, restore, every damage
undone; failed backup leaving no manifest): PLAN.md §9.

## 8. Post-update checks (must print MODULES OK, then no row)

```bash
bash /tmp/phase4/docs/phase4/check_modules.sh after
docker exec -i odoo_db psql -U odoo -d artdubati_test -At -F ' | ' \
  < /opt/odoo/addons/custom/docs/phase4/postcheck.sql
```

It lists: a home record not adopted, an investor screen whose buttons are not exactly
the module's four, a second screen named like the investor screen, an investor account
without the new home action, a missing rule.

## 9. Probe and interface checks

The probe as `test_investor` (read-only, password typed, never stored):

```bash
read -r -p "Login: " ODOO_LOGIN && read -r -s -p "Password: " ODOO_PASSWORD && echo
export ODOO_URL=https://erp.lartdubati.com ODOO_DB=artdubati_test ODOO_LOGIN ODOO_PASSWORD
export ODOO_EXPECT_LOGIN=test_investor
python3 /tmp/phase4/docs/phase4/probe_investor.py
unset ODOO_PASSWORD
```

Expected: « Groups: not readable », root menus « Stock Monitor » only; ACL `r...` and
records for: the monitor (the profile's rows), `quick.start.screen` (1),
`quick.start.screen.action` (4), `res.users` (1), `res.partner` (own and company's),
`res.company`, `res.currency`, `mail.message` (0), `discuss.channel` (0); « not
installed or refused » for every other model (the call itself is refused since P4-2e).

The route inventory (read-only), to compare with `ROUTES.md`: every route other than
the 16 authenticated and 11 public ones listed must read « refused » (or « no user »). Send the output to Claude if a route of
a module not in the local inventory appears:

```bash
docker exec -i odoo_web odoo shell -d artdubati_test --no-http \
  < /opt/odoo/addons/custom/docs/phase4/routes.py 2>/dev/null | grep '^ROUTE' \
  > /opt/odoo/logs/phase4_routes.txt
cut -d'|' -f4 /opt/odoo/logs/phase4_routes.txt | sort | uniq -c
grep '| user | .* | allowed\|| bearer | .* | allowed' /opt/odoo/logs/phase4_routes.txt | wc -l   # must print 16
grep '| public | .* | allowed' /opt/odoo/logs/phase4_routes.txt | wc -l   # must print 11
```

Then in the browser:
1. `test_investor` (English, then French, then Persian after logging in again): the
   home page opens with the 4 buttons; Financial opens the dashboard, « ← Investor
   Home » (arrow mirrored in Persian) goes back; the 3 other buttons show « Coming
   soon »; Detailed analysis opens (export to CSV / XLSX and the pivot download work);
   no error dialog; only the « Stock Monitor » menu. Preferences → Account Security →
   Change password: the password check, then the new password, then logging in again
   with it (then set it back as the owner wishes). Afterwards, the log must show no
   route refused during these checks:
   `docker logs odoo_web --since 30m 2>&1 | grep -E "Investor route refused|websocket request handling"`
   (empty; otherwise send it to Claude).
2. An Inventory user and an accountant: menus and screens as before; the dashboard as
   after phase 3.
3. As administrator: Settings → Users → `test_investor`: adding Purchase / User is
   refused (message naming the group); a new investor user without profile shows the
   warning banner; the old « Investor Home: coming soon » server action is no longer
   used by any button (kept until phase 5).

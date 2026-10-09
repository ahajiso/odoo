# Phase 2f – deployment on artdubati_test

Corrections to phase 2: responsible required, equipment cost with date and provisional
flag, accounting treatment shown in the receipt and frozen in the approval,
read-only approver limited to the documents of the operations. Plan:
`docs/phase2f/PLAN.md` revision 3.

Modules:
- `maintenance_shareholder_equipment` 18.0.3.0.0 → 18.0.3.1.0;
- `lartdubati_investor_home` 18.0.1.5.0 → 18.0.1.6.0 (its bill-to-cost hook moved to
  module 1).

Expected tests: **141 tests** (both modules), including the 3 interface tours. They are
counted even when skipped: the tours need Chrome, which the `odoo_web` image may not
have.

**Run nothing before the audit of the code and the owner's go.**

**Fetching the code is not deploying it.** Steps 2 to 4 run while the current version
keeps serving; the modules change only at step 6.

## 1. Backup (database and filestore)

```bash
set -o pipefail
mkdir -p /opt/odoo/backups /opt/odoo/logs
STAMP=$(date +%F_%H%M)
docker exec odoo_db pg_dump -U odoo -Fc artdubati_test \
  > /opt/odoo/backups/artdubati_test_${STAMP}_phase2f.dump && echo DB BACKUP OK
docker exec odoo_web ls -d /var/lib/odoo/filestore/artdubati_test   # must print the folder
docker exec odoo_web tar -czf - -C /var/lib/odoo/filestore artdubati_test \
  > /opt/odoo/backups/artdubati_test_${STAMP}_phase2f_filestore.tar.gz && echo FILESTORE BACKUP OK
ls -l /opt/odoo/backups/*phase2f*
cd /opt/odoo/addons/custom && git rev-parse HEAD > /opt/odoo/logs/phase2f_previous_commit
```

If `ls -d` prints an error, the filestore lies elsewhere: send the output to Claude
before going on.

## 2. Fetch the new code without touching the working tree

```bash
cd /opt/odoo/addons/custom
git fetch origin +refs/heads/main:refs/remotes/origin/main
git log -1 --oneline origin/main        # must be the commit announced by Claude
rm -rf /tmp/phase2f && mkdir -p /tmp/phase2f
git archive origin/main docs/phase2f | tar -x -C /tmp/phase2f
ls /tmp/phase2f/docs/phase2f/           # precheck.sh  precheck.sql  setup_phase2f.py ...
git status --short | head               # nothing changed in the working tree
```

The running Odoo and the checked out files are unchanged.

## 3. Prepare the data (owner's decisions D1 to D5)

The script reads first, then writes only with `--apply`, on artdubati_test only. Use an
administrator that is not in « Stock Monitor Investor ». The password is typed, never
stored:

```bash
cd /tmp/phase2f/docs/phase2f
read -r -p "Login: " ODOO_LOGIN && read -r -s -p "Password: " ODOO_PASSWORD && echo
export ODOO_URL=https://erp.lartdubati.com ODOO_DB=artdubati_test ODOO_LOGIN ODOO_PASSWORD
python3 setup_phase2f.py                          # dry run: lists D1 to D5
```

Owner's decisions (09/10/2026):
- D1, equipment 484: responsible set in the interface. The dry run must show
  « D1 – 0 integrated equipment without a valid responsible ». Otherwise:
  `python3 setup_phase2f.py --responsible 484=<login>` (dry run), then the same with
  `--apply`.
- D3: the « Test… » equipment was deleted. The dry run must show « D3 – 0 ».
- D4: Bg/IN/00004 is **kept**. Nothing to do here; it is named at step 4. It can no
  longer be validated with the standard button (phase 2): when the goods arrive, it is
  received through Inventory → Operations → Transfers → Equipment Operations, receipt
  type « Purchase », « Existing Order » = its order: the operation takes this receipt
  over (no second receipt).

```bash
unset ODOO_PASSWORD
```

- D2 (addresses of the stocks): not needed for 2f, needed before phase 3. For each
  stock listed « NO ADDRESS »: Inventory → Configuration → Locations → open the
  location (for example Bg/Stock) → field **Address** (under « Location
  Type ») → choose the contact of the site. The city and country come from that
  contact (Contacts → the contact → address). Set it on the stock location itself:
  Bg/Stock is outside the warehouse root, so it inherits nothing.
- D5 (investor group): the dry run prints, under « D5 – investors », each account in
  « Stock Monitor Investor ». An account flagged « HAS INVENTORY RIGHTS » (typically
  an administrator or storekeeper added to the group for a test) has its stocks
  filtered by its access profile; without a profile it sees no internal stock, so
  its Inventory work breaks. Unless that account must really act as an investor:
  Settings → Users & Companies → Users → the account → tab « Access Rights » →
  section « Investor » → empty the field, Save. An account flagged only « no access
  profile » sees nothing in the monitor until it gets a profile (phase 4).

## 4. Precheck (must print PRECHECK OK)

```bash
bash /tmp/phase2f/docs/phase2f/precheck.sh artdubati_test --keep-receipt Bg/IN/00004
```

`--keep-receipt` (D4) lists that receipt as kept instead of blocking; a name that is
not an open receipt of the list makes the precheck fail. If it prints PRECHECK FAILED,
fix what it lists (step 3) and run it again. Do not go on.

## 5 to 7. Stop, update the working tree, update and test, restart

```bash
cd /opt/odoo/addons/custom && git merge --ff-only origin/main && git log -1 --oneline
bash /opt/odoo/addons/custom/docs/deploy_modules.sh \
  /opt/odoo/backups/<dump of step 1> 141 phase2f
```

`deploy_modules.sh`:
- stops `odoo_web`;
- updates both modules (the post-migration fills the cost of the existing equipment);
- runs the tests;
- restarts only if the update and every test passed.

On « FAILED » it leaves `odoo_web` stopped: go to the rollback.

### Rollback (only after a FAILED)

```bash
BACKUP=/opt/odoo/backups/<dump of step 1>
cd /opt/odoo/addons/custom && git checkout "$(cat /opt/odoo/logs/phase2f_previous_commit)"
docker exec odoo_db dropdb -U odoo artdubati_test
docker exec odoo_db createdb -U odoo artdubati_test
docker exec -i odoo_db pg_restore -U odoo -d artdubati_test --no-owner < "$BACKUP" \
  && echo RESTORE OK
docker start odoo_web
```

The filestore is not changed by this update. Its backup is kept for safety. Then send
Claude the two logs named by the script; `git checkout main` brings the branch back
once fixed.

## 8. Checks after the update

1. Operations already approved before the update: the setup script listed them.
   Their approval is cancelled at execution (their approval has no treatment
   signature). They are approved again.
2. Equipment 484: tab « Ownership and Stock », group Cost. Expected: cost known,
   provisional (source « Purchase Order (estimate) »), unless its bill was posted.
3. Interface, with the four profiles (Playwright with their passwords, never stored):
   - **operator**: a new purchase receipt; the line sheet shows « Planned treatment
     under the current configuration: … »; for the saw (category « All »), the box
     « Confirmed: no fixed asset » is required;
   - **approver alone**: opens the operation and its lines without an access error and
     approves; cannot change the header;
   - **operator and approver**: approves and executes;
   - **investor without Inventory rights**: no Equipment Operations menu; a JSON-RPC
     `search_read` on `stock.move.line` returns nothing.

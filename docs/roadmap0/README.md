# ROADMAP section 0, items 1 to 3 – deployment on artdubati_test

## Deployment record (recorded 12/10/2026)

**Deployed: code 5823e71** (maintenance_shareholder_equipment 18.0.5.0.0,
lartdubati_investor_home 18.0.3.0.1), items 1 and 2 and the migration of item 3 in one
window.

- First window (7a5ea9b, 11/10/2026): steps 0 to 4 conform, then the migration's dry
  run refused before any change (`ERROR | equipment saw: 0 record(s)`: name abridged in
  the script, MIGRATION.md §7.00); rolled back with `restore_db.sh roadmap0`. The
  rollback's `umask 077` left the restored code unreadable by odoo_web (the platform
  check failed, safely, before the next backup); permissions normalised on the server
  and fixed in `restore_db.sh` (5823e71).
- Second window: precheck no row; PLATFORM OK before (122 modules); BACKUP OK
  (`roadmap0b`, 552 files, 0 attachment file missing); update OK; **270 tests, 0 failed**;
  migration dry run 77, `--apply` **77 committed**; an accidental second `--apply` gave
  **0 change** (idempotence, the script's own count check); `finish_window.sh`: control
  dry run 0, post-check no row, **270 tests, 0 failed on the migrated data**, start,
  /web/health, PLATFORM OK after, post-check no row: **WINDOW OK**.
- Read-only check of the database afterwards (owner, Odoo API): labels « Can be
  maintained » / « Peut être maintenu » / « قابل تعمیر و نگهداری است »; 9 categories
  available for requests; profile « Matériel informatique (test) » 218300 / 281800 /
  681120, linear 3 years, one asset per item; 8 contract tags; equipment category
  `All` archived, `Fixed Assets` deleted; Computer, TEST Bought compressor, TEST
  Scaffold rent and the contract TEST Scaffold rental archived; table saw in Workshop
  Machinery / Wood (cost 15 € excl. tax, final, from its bill); Mac Mini in IT &
  Communications / Computers & Servers, product in Fixed Assets / IT Equipment; lasers
  in Measuring, Inspection & Setting-out.
- Kept until the acceptance below is done: the backups `roadmap0` and `roadmap0b` and
  the copies kept by the first rollback (`artdubati_test_before_restore_*`).

**Open after the deployment (blocking the use, not the code):**
- the group « Product Catalogue Manager » has **no member**: nobody can approve and
  execute a request. Name at least one manager; the acceptance needs two accounts (the
  requester never approves his own request);
- functional acceptance: **0 request so far**. Scenarios: a service in Telecom &
  Internet (requested, approved by another user, executed, product checked); an IT
  equipment request; a family waiting for C24 / C25 refused; the investor's monitor
  unchanged. « Abonnement téléphonique » already exists in Services Purchased /
  Telecom & Internet: not to be requested again;
- Mac Mini (item 4): P00381 1 100 € excl. tax, received, to invoice, no bill, no fixed
  asset; equipment cost still provisional 1 850 € excl. tax (source: order); stock 1 in
  Bg/Stock valued 0 €; the IT profile is ready on 218300. Next: draft bill from P00381,
  posted by an authorised accounting user; expected: fixed asset on 218300 with the IT
  profile, `asset_id` on the equipment, final cost 1 100 € excl. tax;
- ergonomics (owner's proposal, to plan): the requests are under Inventory → Products →
  Product Requests, not intuitive for services and subscriptions; rename the menu
  « Item and Service Requests » and expose the same action under Purchase (and possibly
  Invoicing → Vendors), no new model nor rule. A real subscription (supplier, amount,
  period, renewal, documents, bills) belongs to phase A, not to the request;
- the rest of the nomenclature (insurance, maintenance, software and SaaS including
  ChatGPT, energy and charges, leasing, subcontracting, transport, materials and
  consumables, workwear, supplier consignment): not opened by this deployment.

Label « Can be maintained », product creation requests, catalogue guards
(docs/roadmap0/PLAN.md revision 5; audit of 7f352aa: green light for items 1 and 2).
Module `maintenance_shareholder_equipment` 18.0.4.0.1 → **18.0.5.0.0** (new dependency
`maintenance_equipment_category_hierarchy`, already installed on artdubati_test);
`lartdubati_investor_home` unchanged (18.0.3.0.1, its tests run again).

Expected tests on the server: **270** (271 locally on the server's exact code with the
seeded data, before and after the migration, MIGRATION.md §7; the real websocket test
class is skipped on the server and not counted, hence one less).

What changes for the users, from the update:
- nobody creates a product directly any more (form, quick creation in a purchase line,
  import, duplication): Inventory → Products → **Product Requests**; the « Product
  Catalogue Manager » group approves (never his own request) and executes;
- the structural fields of a product (category, type, tracking, units, accounts,
  equipment category, maintainable, internal reference, barcode) and the supplier,
  product and supplier reference of its supplier lines are locked; only the default
  equipment category is corrected, through Inventory → Products → **Structural
  Corrections** (catalogue managers, with a reason); the other fields by the audited
  migration, then by the future modification request;
- « Available for Product Requests » on a product category: accounting administrators
  only, traced (who, when);
- a receipt or a bill of a maintainable product **without a default equipment
  category** is refused (no category created silently). The existing products get theirs
  in item 3 (migration): step 3 lists what is in progress;
- no family is executable until a product category is configured and made « Available
  for Product Requests » (D8): the categories of item 3 for services and the Mac Mini,
  the others after C24 / C25.

No new HTTP route (no controller added): the investor route lists are unchanged.

## Procedure (one window: code of items 1 and 2, then the migration of item 3)

**Executed** (second window, record above); kept as the reference procedure. Rehearsed locally in the same order (MIGRATION.md §7,
`rehearsal/rehearse.sh`). `odoo_web` stays **stopped** from the update to the end of
the migration: nobody works between the update and the migration (a receipt or a bill
of a maintainable product would be refused in that interval).

```bash
# 0. read-only precheck, before the window (audited commit bb2c857; no row expected)
cd /opt/odoo/addons/custom
git fetch origin claude/clever-rubin-z76iba
git show bb2c857:docs/roadmap0/precheck_catalogue.sql \
  | docker exec -i odoo_db psql -U odoo -d artdubati_test -At -F ' | '

# 1. fetch the code without touching the working tree (COMMIT = the commit announced
#    by Claude after the audit, fast-forward of main)
COMMIT=<commit>
git fetch origin +refs/heads/main:refs/remotes/origin/main
git log -1 --oneline origin/main                      # must be $COMMIT
rm -rf /tmp/roadmap0 && mkdir -p /tmp/roadmap0
git archive origin/main docs/roadmap0 docs/phase4 docs/deploy_modules.sh \
  docs/backup_db.sh docs/restore_db.sh | tar -x -C /tmp/roadmap0
git status --short | head                             # nothing

# 2. platform (must print PLATFORM OK (before))
bash /tmp/roadmap0/docs/phase4/check_modules.sh before

# 3. backup, checked (must print BACKUP OK)
bash /tmp/roadmap0/docs/backup_db.sh roadmap0

# 4. stop, code, update, tests; odoo_web LEFT STOPPED (must end with
#    « odoo_web left STOPPED on request »)
BACKUP=$(sed -n 's/^DUMP=//p' /opt/odoo/logs/roadmap0_backup)
KEEP_STOPPED=1 bash /tmp/roadmap0/docs/deploy_modules.sh "$BACKUP" 270 roadmap0 "$COMMIT"

# 5. migration dry run (one-shot container, odoo_web stopped): must print
#    MIGRATION OK (dryrun) and « END | dry run, 77 change(s) rolled back »
bash /tmp/roadmap0/docs/roadmap0/run_migration.sh

# 6. apply: « END | applied, 77 change(s) committed » (the script itself refuses the
#    commit on any ERROR, KEPT, BLOCKED or count other than the expected one)
bash /tmp/roadmap0/docs/roadmap0/run_migration.sh --apply

# 7. end of the window, odoo_web still stopped: control dry run (0 change), post-check
#    (no row), the 270 tests on the migrated data; only then start, /web/health,
#    PLATFORM OK (after), post-check again; odoo_web stopped again on any failure.
#    Must end with « WINDOW OK »
bash /tmp/roadmap0/docs/roadmap0/finish_window.sh 270
```

Expected in the dry run of step 5 (artdubati_test, inventory of 11/10/2026): `COUNTS |
M1=2 M2=18 M3=9 M4=4 M5=5 M6=31 M7=8 | expected 77`; `FOUND` with the inventory's ids;
`CONTRACT | TEST Scaffold rental … lines=1 checked=OK`; `M6`: `All` (89) **archived**
(bill line of BILL/2026/10/0006), `Fixed Assets` (481) and the 29 imported
**deleted**; `M3`: the Mac Mini « stock 1.0 … cost of 0.0 », no journal entry;
`WAITING` 6 lines; `H3` the table saw's layers and bill.

**Stop rules, automated (audit of 9c407ae).** `migrate_catalogue.py` turns into `ERROR`,
and rolls back before any commit: a `KEPT` product, a `BLOCKED` document, a section
count other than the one above (first run) or any change at all (migrated database), a
TEST Scaffold rental contract differing from the inventory (server id 1, company,
partner, type, EUR, one line « TEST Scaffold rental », product, no equipment, quantity,
price 250, every 1 month from 01/09/2026, no end). `run_migration.sh`
refuses the same lines and any total other than 77 / 0 as a second protection.
`deploy_modules.sh` and `finish_window.sh` stop at the first failure. After any
FAILED: nothing more is run, `odoo_web` stays (or is put back) stopped, the outputs
(`/opt/odoo/logs/roadmap0_*`) go to Claude; then the rollback below. Without the
migration the code of items 1 and 2 must not stay in service (« Not deployed alone »).

Not tried with Docker (no Docker in the development session): the one-shot container
of `run_migration.sh` and `finish_window.sh`, `KEEP_STOPPED=1`. They copy the `docker
run` of `deploy_modules.sh`, already used on the server; step 5 (a dry run, rolled
back) is the first use and writes nothing: if it fails, the window stops there.

### Rollback (only after a FAILED or a stop rule)

```bash
bash /tmp/roadmap0/docs/restore_db.sh roadmap0
```

Back to ae31573 (code), the database and the filestore of step 3 (`restore_db.sh`
checks everything before changing anything; current copies kept). It also restores
the worktree permissions from Git's executable bits before starting Odoo; this avoids
the unreadable manifests caused by the script's protective `umask 077` during the
first rollback of 11/10/2026.

### Interface checks after « WINDOW OK » (owner, browser)

- a catalogue manager creates a request for a service (« Telecom & Internet »),
  another approves, it is executed: one product created, in its category;
- a request for « IT Equipment » shows the family rules (storable, serial, maintainable,
  equipment category); a family waiting for C24 / C25 is refused with its message;
- equipment list: Scie sur table – 1234, Mac Mini – 877790 (fr_FR and en_US), the two
  lasers in Measuring, Inspection & Setting-out; old categories gone or archived;
- stock monitor unchanged for the investor (same rows as before the window).

# ROADMAP section 0, items 1 and 2 – deployment on artdubati_test

**Not deployed alone (audit of dad9933, point 7).** After items 1 and 2 alone no family
is usable, direct creation is already refused and some receipts and bills of
maintainable products would be blocked until the migration. The code of items 1 and 2
is deployed **in the same window as the migration of item 3** (its plan and script to
come and to audit); the procedure below is completed then. If the label « Can be
maintained » is wanted earlier, it can be a separate micro-fix (owner's decision).

Label « Can be maintained », product creation requests, catalogue guards
(docs/roadmap0/PLAN.md revision 5; audit of 7f352aa: green light for items 1 and 2).
Module `maintenance_shareholder_equipment` 18.0.4.0.1 → **18.0.5.0.0** (new dependency
`maintenance_equipment_category_hierarchy`, already installed on artdubati_test);
`lartdubati_investor_home` unchanged (18.0.3.0.1, its tests run again).

Expected tests on the server: to be stated with the deployment of item 3 (local count
on a clean checkout, log in `docs/roadmap0/test_logs/`; the real websocket test class is skipped on the server as
before, hence one less).

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

**Not authorised yet**: written for the joint audit of the migration and of this
procedure (MIGRATION.md). Rehearsed locally in the same order (MIGRATION.md §7,
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
KEEP_STOPPED=1 bash /tmp/roadmap0/docs/deploy_modules.sh "$BACKUP" TESTCOUNT roadmap0 "$COMMIT"

# 5. migration dry run (one-shot container, odoo_web stopped): must print
#    MIGRATION OK (dryrun) and « END | dry run, 77 change(s) rolled back »
bash /tmp/roadmap0/docs/roadmap0/run_migration.sh

# 6. compare with the expected lines below; then apply (« END | applied, 77 change(s)
#    committed »), then the control dry run (« END | dry run, 0 change(s) rolled back »)
bash /tmp/roadmap0/docs/roadmap0/run_migration.sh --apply
bash /tmp/roadmap0/docs/roadmap0/run_migration.sh

# 7. start, platform after, post-check (PLATFORM OK (after), then no row)
docker start odoo_web
bash /tmp/roadmap0/docs/phase4/check_modules.sh after
docker exec -i odoo_db psql -U odoo -d artdubati_test -At -F ' | ' \
  < /tmp/roadmap0/docs/roadmap0/postcheck_catalogue.sql
```

Expected in the dry run of step 5 (artdubati_test, inventory of 11/10/2026), by section
(the launcher prints the counts): `M1 2`, `M2 18`, `M3 9`, `M4 4`, `M5 5`, `M6 31`,
`M7 8`; no `ERROR`, no `KEPT`, no `BLOCKED` (otherwise: the lines are read before
going on); `FOUND` with the inventory's ids (checked by the script); `M6`: `All` (89)
**archived** (bill line of BILL/2026/10/0006), `Fixed Assets` (481) and the 29
imported **deleted**; `M3`: the Mac Mini « stock 1.0 … cost of 0.0 », no journal
entry; `WAITING` 6 lines; `H3` the table saw's layers and bill.

**Stop rules.** Any FAILED, unexpected count, `ERROR`, `KEPT` or `BLOCKED` line in
steps 4 to 6: nothing more is run, `odoo_web` stays stopped, the outputs
(`/opt/odoo/logs/roadmap0_*`) go to Claude; then the rollback below. Without the
migration the code of items 1 and 2 must not stay in service (« Not deployed alone »).

### Rollback (only after a FAILED or a stop rule)

```bash
bash /tmp/roadmap0/docs/restore_db.sh roadmap0
```

Back to ae31573 (code), the database and the filestore of step 3 (`restore_db.sh`
checks everything before changing anything; current copies kept).

### Interface checks after step 7 (owner, browser)

- a catalogue manager creates a request for a service (« Telecom & Internet »),
  another approves, it is executed: one product created, in its category;
- a request for « IT Equipment » shows the family rules (storable, serial, maintainable,
  equipment category); a family waiting for C24 / C25 is refused with its message;
- equipment list: Scie sur table – 1234, Mac Mini – 877790 (fr_FR and en_US), the two
  lasers in Measuring, Inspection & Setting-out; old categories gone or archived;
- stock monitor unchanged for the investor (same rows as before the window).

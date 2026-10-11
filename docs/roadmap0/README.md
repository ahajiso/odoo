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

**Run nothing before the audit of this commit and the owner's go.**

```bash
# 1. fetch the code without touching the working tree
cd /opt/odoo/addons/custom
git fetch origin +refs/heads/main:refs/remotes/origin/main
git log -1 --oneline origin/main        # the commit announced by Claude
rm -rf /tmp/roadmap0 && mkdir -p /tmp/roadmap0
git archive origin/main docs/phase4 docs/roadmap0 docs/deploy_modules.sh \
  docs/backup_db.sh docs/restore_db.sh | tar -x -C /tmp/roadmap0
git status --short | head               # nothing

# 2. platform (must print PLATFORM OK (before))
bash /tmp/roadmap0/docs/phase4/check_modules.sh before

# 3. what the update would block (read-only): open operations and draft bills of
#    maintainable products; no row = nothing in progress is affected
docker exec -i odoo_db psql -U odoo -d artdubati_test -At -F ' | ' \
  < /tmp/roadmap0/docs/roadmap0/precheck_catalogue.sql

# 4. backup, checked (must print BACKUP OK, 0 missing attachment file)
bash /tmp/roadmap0/docs/backup_db.sh roadmap0

# 5 to 7. stop, code, update, tests, restart
BACKUP=$(sed -n 's/^DUMP=//p' /opt/odoo/logs/roadmap0_backup)
COMMIT=$(git -C /opt/odoo/addons/custom rev-parse --short origin/main)
echo "$BACKUP $COMMIT"
bash /tmp/roadmap0/docs/deploy_modules.sh "$BACKUP" 259 roadmap0 "$COMMIT"

# 8. post-update checks: PLATFORM OK (after), then no row
bash /tmp/roadmap0/docs/phase4/check_modules.sh after
docker exec -i odoo_db psql -U odoo -d artdubati_test -At -F ' | ' \
  < /opt/odoo/addons/custom/docs/roadmap0/postcheck_catalogue.sql
```

Step 3 rows: send them to Claude before going on (an open receipt of a maintainable
product would be refused until item 3).

Rollback, only after a FAILED and Claude's reading of the logs:
`bash /tmp/roadmap0/docs/restore_db.sh roadmap0`.

9. Interface checks (after the go of the audit):
- Settings → Users: give « Product Catalogue Manager » to the manager who will approve;
- as a buyer or an operator: Inventory → Products → Product Requests → New: the form,
  the accounting treatment shown, the duplicates; Submit refused with « waits for the
  accountant » (no category available yet: expected until item 3);
- as anybody: Products → New, or a new product typed in a purchase line: refused with
  the message pointing to the requests;
- a product form: the label « Can be maintained » (« Peut être maintenu »,
  « قابل تعمیر و نگهداری است »), changing its category refused, its name allowed;
- the log: `docker logs odoo_web --since 30m 2>&1 | grep -E "ERROR|Traceback"` (only
  the expected lines of the tests, none from the interface checks).

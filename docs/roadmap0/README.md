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

## Procedure

**No deployment procedure yet.** The deployment steps (backup, update, tests, post-check,
interface checks) are written with item 3, after its audit, for one window: code of
items 1 and 2 and the migration together. Until then only the read-only precheck below
may be run, for information.

```bash
# read-only: open operations and draft bills of maintainable products that the update
# would block until the migration; no row = nothing in progress is affected
# (read from the audited commit bb2c857, immutable; the working tree is untouched)
cd /opt/odoo/addons/custom
git fetch origin claude/clever-rubin-z76iba
git show bb2c857:docs/roadmap0/precheck_catalogue.sql \
  | docker exec -i odoo_db psql -U odoo -d artdubati_test -At -F ' | '
```

The post-check (`postcheck_catalogue.sql`, read-only) is kept for that procedure.

# ROADMAP section 0, item 3 – migration plan (revision 1, 11/10/2026)

Basis: PLAN.md §3 (revision 5, validated), NOMENCLATURE.md, REPORT.md, EXTRACT.md
(inventory and complement of 11/10/2026). Script: `migrate_catalogue.py`, launcher
`run_migration.sh`. **Nothing is run on artdubati_test before the joint audit of this
migration and of its deployment procedure (README.md).**

## 1. Execution model

- Odoo shell inside `odoo_web` (superuser mode): the catalogue guards of items 1 and 2
  (product creation, structural fields, `request_ready`) admit only superuser mode, so
  the migration cannot go through JSON-RPC like the phase 2f script. Through
  `run_migration.sh`, same checks as the inventory launcher (exit code, stderr, no
  Python error, last line).
- **Dry run = the real migration, rolled back**: every change is written in the
  transaction, so the model constraints (family rules, fixed-asset category checks,
  stock revaluation of the Mac Mini, equipment constraints) run exactly as with
  `--apply`; then `ROLLBACK`. `--apply` runs the same code and commits only if no
  `ERROR` line was printed. A **control dry run** after `--apply` must end with
  « 0 change(s) » (every step first compares the wanted state with the current one).
- Preconditions refused before any change: database `artdubati` (production), any
  database other than artdubati_test without `ROADMAP0_REHEARSAL=1`, module not
  installed in 18.0.5.0.0, more than one company.
- **No guessed id**: records are found by external ID, or by exact name and parent
  (category, product category); each one is printed with its id (`FOUND`). On
  artdubati_test the ids must also be those of the inventory (EXTRACT.md: products 8,
  837, 7, 824, 823, 127, 126, 843, 5, 6, 125, 13, 10, 11, 3, 4, 1, 836, 828; equipment
  484, 869, 870, 871; equipment categories 89, 481; product categories 18, 19; profile
  4), otherwise `ERROR` and nothing is written. Accounts are found by code, printed with
  name, type and id, and their type is checked.
- Records created by the migration get external IDs in the module name `roadmap0`
  (owned by no installed module: never removed by a module update), so the audit, the
  post-check and item 4 refer to them without ids.

## 2. Changes

| Step | What | Test choices (QUESTIONS_COMPTABLE.md) |
|---|---|---|
| M1 | Asset profile « Matériel informatique (test) » (`roadmap0.asset_profile_it`): copy of profile 4 (same journal and options), asset account 218300, depreciation 281800 (French chart: « same allocation as for account 218 »), expense 681120, linear, **3 years**, one asset per item; set on account 218300 | C25: account and duration of IT |
| M2 | Product categories under the roots of item 2, made « Available for Product Requests » (superuser, traced: who, when): Fixed Assets (catalogue) / **IT Equipment** (218300) and **Plant & Tools** (215400, profile 4, 5 years): fixed-asset flag, average cost, manual valuation; Services Purchased / **Equipment Rentals & Loans** (613500), **Telecom & Internet** (626000), **Bank Services** (627800), **Administrative Supplies & Fees** (606400); Sales / **Consulting** (706000), **Works** (704000), **Equipment Rentals** (708300) | C25 |
| M3 | Products moved now (no stock account involved): the 8 services to their category; Mac Mini to Fixed Assets / IT Equipment with default equipment category IT & Communications / Computers & Servers. The Mac Mini's stock (1 unit, standard price 0) is emptied and replenished by Odoo at the same cost: value 0 before and after, manual valuation, **no journal entry** | – |
| M4 | Equipment: 484 → Workshop Machinery / Wood, renamed « Scie sur table – 1234 »; 871 → IT & Communications / Computers & Servers, renamed « Mac Mini – 877790 »; 869, 870 → Measuring, Inspection & Setting-out | – |
| M5 | Archived **only if nothing depends on them** (stock, open moves, open purchase or sale lines, active contracts, active equipment, draft entries, open equipment operations; otherwise listed `KEPT`): Laser rangefinder 823 (duplicate), Computer 837 (D5), TEST Bought compressor 13, TEST Scaffold rent 11 **with** its contract « TEST Scaffold rental » (no draft bill of the contract) | – |
| M6 | Old equipment categories (29 imported `__import__.cat_*`, `All` 89, `Fixed Assets` 481): leaves first; **archived** while anything references them (every stored many2one / many2many to `maintenance.equipment.category` found through `ir.model.fields`, archived records included, or a remaining child: `parent_id` is `ondelete="cascade"`, so a parent with children is never deleted), **deleted** otherwise (their `__import__` external ID goes with them). A posted accounting line is never modified. Defaults (`ir.default`) and saved filters on these fields are listed | – |
| M7 | OCA contract tags: Insurance, Maintenance, Rental, Leasing, Telecom & Internet, Software & SaaS, Energy & Charges, Other Subscription (company Docteur Bain) | – |

Expected on artdubati_test: `All` (89) archived (posted bill line of the table saw,
BILL/2026/10/0006); `Fixed Assets` (481) deleted (its two lasers moved, no bill line);
the 29 imported deleted (0 equipment, no reference); 0 equipment left in an old
category. The script prints each decision with its reason and the old code →
new category correspondence (§4).

Product category names are not translatable in Odoo 18 (`product.category.name` has no
`translate`): they are English, like the roots of item 2 and the existing categories.

## 3. Not done by this migration (listed by the script)

- `WAITING`: table saw 8 (C24), Green cross laser 824 (D5), lasers 836 / 828 (D3,
  anomaly 1), TEST Cement bag 10 (consignment, §5), Matériaux de construction 6
  (generic goods sold: goods family, C25). They keep their product category, valuation
  and settings; no default equipment category yet, so a receipt or a bill of a
  maintainable one among them stays refused until then (`BLOCKED` lists the open
  documents concerned; expected none).
- `H3` (read only): the table saw's standard price, valuation layers and bill lines,
  to explain 329 € against 15 € (D4: no automatic alignment).
- Mac Mini bill (item 4), consignment (item 5): their own plans.
- Intangible assets: no category opened (PLAN.md §2.9: profile and duration not
  decided; §3.1 listed it among the branches, §2.9 prevails).
- Old product categories (`All / Expenses / …` 11 to 18, `All / Fixed Assets` 19,
  `All / Saleable`) are left as they are: 19 keeps the two lasers, the others are empty
  or historical; Odoo has no archiving of product categories. To decide with C25.
- Products keep their own account overrides; the script notes any that differs from
  its new category (expected none: every override equals the category's account).

## 4. Old imported codes → business tree (informative, 0 equipment today)

| Code | Old category | New category |
|---|---|---|
| 01 | Cordless Tools | Tools / Cordless Power Tools |
| 02 | Corded Power Tools | Tools / Corded Power Tools |
| 03 | Hand Tools | Tools / Hand Tools Tracked Individually |
| 04, 05, 08, 09, 10 | Electrical, Plumbing & MEP, Painting, Masonry & Tiling, Plastering | trades, not branches: by physical nature |
| 06 | Woodworking Equipment | Workshop Machinery / Wood |
| 07 | Metalworking Equipment | Workshop Machinery / Metal |
| 11 | Measuring Equipment | Measuring, Inspection & Setting-out |
| 12 | Demolition Equipment | Site Machinery & Equipment |
| 13 | Workshop Cleaning Equipment | Cleaning & Extraction |
| 14 | Safety and PPE | Durable, Inspected Safety Equipment (PPE: workwear register) |
| 15 | Material Handling | Handling & Lifting |
| 16 | Ladders, Scaffolding, Work at Height | Access & Work at Height |
| 17 | Small Workshop Machinery | Workshop Machinery / Other |
| 18 | Electronic and IT | IT & Communications (sub-category by item) |
| 19 | Batteries and Chargers | Tools / Batteries & Chargers Tracked Individually |
| 26 | Site Machinery | Site Machinery & Equipment |
| 27 | Vehicles | Vehicles |
| 28 | Formwork and Shoring | Formwork & Shoring |

## 5. Final checks of the script (ERROR if not met)

- every active equipment in an active, usable category of the tree (not « To
  Classify », not archived, not automatic);
- every product's default equipment category usable;
- every category « Available for Product Requests » passes the request checks of its
  family (`_request_problems`), and only durable equipment and services are opened;
- each moved product passes its family rules.

## 6. Local rehearsal

Platform: a database built on the server's exact code (main ae31573,
`maintenance_shareholder_equipment` 18.0.4.0.1, the pinned OCA versions of
platform_expected.txt, the same 122 modules as `srv2`), in three steps (`base`; French
chart loaded on the company; the other modules: a single `-i` of the 122 fails because
`lartdubati_facturation` creates its taxes before a chart exists), fr_FR and fa_IR
loaded, default language en_US as in `srv2`. Then `rehearsal/seed_server_state.py`
(old code) recreates the records of the inventory (ids differ; the three products of
`lartdubati_facturation`'s install hook already exist and are completed, as on the
server). Then `rehearsal/rehearse.sh`, in the order of the window (README.md):
precheck, update to 18.0.5.0.0, tests, dry run, `--apply`, control dry run,
post-check, tests again on the migrated data.

## 7. Rehearsal results (11/10/2026, commit 0f8650d, logs in test_logs/rehearsal_0f8650d/)

- Precheck: no row. Update: no error.
- Tests before the migration: **0 failed, 0 error(s) of 271 tests** (on the server 270:
  the real websocket class is skipped there and not counted, as in phase 4).
- Dry run: **77 changes** (M1 2, M2 18, M3 9, M4 4, M5 5, M6 31, M7 8), no `ERROR`,
  `KEPT` or `BLOCKED`; `All` archived (its posted bill line), `Fixed Assets` and the
  29 imported deleted; Mac Mini: two valuation layers −1 / +1 at 0, no journal entry.
- `--apply`: the same 77, committed. Control dry run: **0 change(s)**.
- Post-check: no row.
- Tests after the migration: **0 failed, 0 error(s) of 271 tests**.

Found and corrected during the rehearsal (before this commit):
1. The equipment name is translatable (jsonb): renaming in en_US only would have left
   the old name to French users (the seeded names had an fr_FR value). M4 now writes
   the new name in every active language and compares each one.
2. The control dry run looked for `Fixed Assets` (481) after its deletion: that lookup
   is now required only before the migration (`STATE` line).
3. Account 218300 gets the IT profile from `account_asset_management` itself when the
   profile is created (the account had none): reported as such (M1, 2 lines).
4. The post-check read company-dependent fields (jsonb) and `request_ready` (NULL on
   the existing categories) correctly only after correction; it lists every missing
   item on a non-migrated database and nothing after the migration.

Rehearsal environment findings (not migration defects, for the audit):
- With fr_FR as default language (first rebuild), 21 to 44 tests fail: their messages
  are compared with English expressions. The server passed its 235 tests in phase 4,
  so its test users get en_US; the rehearsal uses en_US like `srv2`. The test suite
  depends on that default (to know, not changed here).
- A PostgreSQL crash of the local container (session restart) left one seeded copy
  with sequences behind their tables; detected by the update (duplicate key),
  rebuilt from the clean base and checked (no sequence behind any table) before the
  final run.

Not verified locally: the server's real records beyond the inventory (the script
stops on any id or count difference), the one-shot container of `run_migration.sh`
(no Docker here; the same `docker run` as `deploy_modules.sh`), `KEEP_STOPPED=1`
(two lines, read by the audit).

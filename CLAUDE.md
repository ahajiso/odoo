# Project: Investor Home and Stock Monitor (L'Art du Bâti, Odoo 18 CE)

## Context
- Odoo 18.0 Community, Docker (container odoo_web), VPS. Prod DB: artdubati. Test DB: artdubati_test.
- This repo is the custom addons folder: each module sits at the repo root and is cloned
  on the server at /opt/odoo/addons/custom. Modules: maintenance_shareholder_equipment,
  lartdubati_investor_home, lartdubati_facturation, lartdubati_env_ribbon,
  lartdubati_manual, plus OCA account_asset_management (with report_xlsx, report_xlsx_helper).
- Installed on artdubati_test (OCA, not in this repo, checked by the owner):
  account_asset_management, maintenance_product, maintenance_account, maintenance_partner,
  maintenance_request_repair, maintenance_equipment_category_hierarchy, and the modules
  used by the current monitor and home page (bi_sql_editor, contract,
  maintenance_equipment_contract, web_quick_start_screen, base_menu_visibility_restriction;
  see docs/stock_monitor/README.md and docs/investor_home/README.md).
- OCA modules to add for revision 2 (18.0): contract_line_successor (OCA/contract),
  maintenance_equipment_usage, maintenance_request_purchase (OCA/maintenance),
  stock_location_address (OCA/stock-logistics-transport). To drop: maintenance_equipment_contract
  (unqualified many2many). Not used: maintenance_purchase.
- Warehouse « Bougival 1 » (code Bg): its stock Bg/Stock is outside its root location WH
  (owner's choice, keep it and keep the documentation as is), so
  `stock.location.warehouse_id` is empty for Bg/Stock and its children. Never rely on
  `warehouse_id` to find a stock's warehouse, address or country.
- One container `odoo_web` and one addons folder serve both databases: acceptable only
  while there is no real production (08/10/2026). Separate test and production
  environments (services, code, databases, filestores, backups, controlled promotion)
  are a mandatory prerequisite before any production use: docs/deployment/investor_home.md,
  section 0.
- Single company. DB container: odoo_db (`docker exec -i odoo_db psql -U odoo -d artdubati_test`).
- Languages: en_US, fr_FR, fa_IR (RTL). All UI strings translatable; .po files come from
  `odoo --i18n-export`, never written by hand.
- Owner's rule (09/10/2026): every price or cost label says it is untaxed: « (excl. tax) »
  in the source strings, « (HT) » in French, « (بدون مالیات) » in Persian. Exception only
  where a price is really entered tax included (none found so far): then « (incl. tax) /
  (TTC) ». Applies to new fields, views, reports and the stock monitor.
- Business definitions are in docs/DEFINITIONS.md. Read it first and follow it exactly.
  It is a revisable design document: report every finalised decision there.

## Goal
1. `maintenance_shareholder_equipment` (existing, slimmed down, technical name kept):
   equipment data model (ownership, lot, asset, replacement value, warranty, insurance),
   stock location attributes, fixed-asset category check, contract line link, receiving
   and exit wizards, bill / contract / asset integration.
2. `lartdubati_investor_home` (depends on 1): access profiles and record rules, stock
   monitor, investor home page.
   - Home page: one button per main function (Administrative, Financial, Commerce &
     Services, Production); only Financial is implemented, the others are "coming soon".
     OCA web_quick_start_screen screen versioned as module data since phase 4
     (docs/investor_home/README.md, docs/phase4/).
   - Financial -> Stock monitor: model `lartdubati.stock.monitor` (one SQL view), OWL
     dashboard `lartdubati_investor_home.action_stock_monitor` and standard views
     (phase 3, docs/phase3/; replaces the two OCA bi_sql_editor reports).

## Stock monitor
- Choose a stock (combo box) or filter by country / state / city / other attribute.
  A stock is a location with a place type; its stored address_id gives the geography.
- Family: assets, consumables or both. Ownership: owned / borrowed / rented / lent out
  (consumables: owned only in v1).
- Per stock: quantity, inventory value, accounting value, rental cost (see definitions).
- Assets = maintenance.equipment (stock-managed with a serial number, or non-stock with a
  monitor location), consumables = stock.quant, joined in one read-only SQL view
  (per-stock currency, grouped by currency). Fixed-asset categories count 0 in stock
  value; their value comes from account.asset. Contract data is joined through a
  subquery aggregated per equipment (one row per equipment).
- Receiving wizard: starts from the ownership status (purchase / borrowed / rented) and
  an exit wizard for lent out; mandatory stock, family, status; equipment created once at
  receipt; enforced by model constraints.
- Rent is not stored on the equipment: it comes from the equipment's rental contract
  line (OCA contract) and the posted bills linked to it.
- Access: access profiles (allowed countries / stocks / ownership statuses / families),
  enforced by record rules on the SQL view and every model the monitor opens.

## Rules
- Odoo standards: extend by inheritance, no raw SQL writes, no core patches.
- HTTP routes (audit of 6063db1): every installation or update of a module comes with the
  inventory of its HTTP routes (docs/phase4/routes.py, compared with the previous output).
  A new route, authenticated or public, stays refused to investor sessions until listed
  in INVESTOR_ROUTES or INVESTOR_PUBLIC_ROUTES with a reason and a test as an investor
  account; a new public route is read anyway (docs/phase4/ROUTES.md). Every future investor screen needs, explicitly, its
  action, models, methods, routes, menu, fields and tests.
- Main rule: use standard Odoo and OCA data and features first; change the repo only
  when necessary.
- Develop and test on artdubati_test only; production only on explicit request.
- Never guess an external ID: look it up and show it first.
- Manual: for the phases of this project, the manual is rewritten once, at the end of
  the last phase (owner's decision, 08/10/2026: nobody uses it before and it would
  change again; since the audit of 6063db1, after the functional phases of
  docs/ROADMAP.md). Outside this project, every Odoo change requires the manual update
  (FR, then EN/FA) and a changelog line.
  The manual's cards are edited directly in lartdubati_manual/manual/<lang>/*.html,
  then `lartdubati_manual/tools/refresh.py` and `check.py` are run. Procedure and
  definitions (card codes, writing rules, terminology, impact matrix):
  docs/manual/maintenance-manuel-odoo.md and docs/manual/definitions-manuel.md; tools:
  lartdubati_manual/tools/README.md. Read them before touching the manual. Investor
  profile tab in the three manuals.
- Update module on the server: `docker exec -i odoo_web odoo -d artdubati_test -u <module>
  --stop-after-init` then `docker restart odoo_web`.
  Run tests: `docker exec -i odoo_web odoo -d artdubati_test -u <module> --test-enable
  --test-tags /<module> --workers 0 --http-port 8079 --stop-after-init 2>&1 | tail -40`
  (tests start an HTTP server: without another port it collides with the running 8069).
- UI checks: Playwright from the session can log in to https://erp.lartdubati.com
  (db=artdubati_test) with a non-admin test user given by the owner; never store its password.
- Small commits, clear messages. Propose a plan before coding each phase.
- Working method: Claude Code develops and proposes; ChatGPT audits and criticises; the
  owner decides disagreements and runs everything on the server. Each proposal states
  what was verified, what could not be (server-side checks) and the open hypotheses.
  Each audit point is answered: fixed if right, argued with code or sources if
  disputable, sent to the owner if it needs a decision. Nothing is run on the server
  before the audit, and nothing is called done without saying so explicitly.
- Accounting questions: whenever an accountant's opinion is needed, 1) make a choice
  and state it is a test choice, 2) make it configurable (setting, category, profile)
  as soon as possible, 3) add the question, the choice and where to change it to
  docs/QUESTIONS_COMPTABLE.md.

## Decisions
Revision 2 of docs/DEFINITIONS.md (07/10/2026) replaces the decisions of 04/10/2026
wherever they differ. Superseded:
- ownership computed only in the monitor from acquisition_mode / owner_type → stored
  `ownership_status` + `owner_partner_id`; acquisition_mode and owner_type removed;
- rent through maintenance_equipment_contract → `contract.line.equipment_id` + nature;
- no asset link field → explicit `asset_id`, filled from the bill line when empty;
- stock address = warehouse partner → `stock_location_address`, address mandatory on
  every monitor stock;
- no receiving form → receiving and exit wizards (four branches);
- consumables borrowed / rented inferred from a running purchase contract → consumables
  are owned only in v1.

Still valid from 04/10/2026:
- Business choices with no single right answer are Settings options (stored on
  res.company, since bi_sql_editor cannot read system parameters), one at a time, each
  with a default.
- Investors read only the stock monitor (no Inventory/Maintenance rights). Access record
  rules are global (group rules are ORed with other rules): on the monitor model and on
  internal stock locations.
- Phase 0 done on artdubati_test: consumable product categories 11-17 at average cost;
  Consignment setting (owner on stock) enabled. Asset profiles wait for the accountant.

Decided by the owner on 09/10/2026 (phase 3): the bi_sql_editor reports are replaced by a
module model on a SQL view with `groups=` per field; the main interface is an OWL
dashboard (client action) on that model, through the ORM without sudo, the standard
views (list, pivot, graph, export) being the secondary interface. Plan and mock-up:
docs/phase3/. Still to decide in phase 4: the home page (web_quick_start_screen
configuration versus a client action).

## Existing code to rework (built on the 04/10 decisions)
- Done in phase 1: account_move_line.py no longer sets `current_location_id`;
  maintenance_equipment.py (internal location required) removed; `place_type` moved to
  maintenance_shareholder_equipment.
- Done in phase 3 (deployed on artdubati_test on 10/10/2026): `stock_monitor_replacement_price`,
  `owner_type` and `acquisition_mode` removed; the bi_sql_editor queries replaced by the
  monitor view; `_location_domain` by the country of the monitor stock's own address;
  investor tests without Inventory group. `stock_monitor_currency_mode` (historical /
  latest) stays pending the accountant (C12).

## Hypotheses of phase 1 (results of the integration tests, 08/10/2026)
Local Odoo 18 + OCA heads, see docs/phase1/CHARACTERISATION.md; confirmed by the same
tests on artdubati_test (47 passing, 08/10/2026).
- Our `action_post()` runs after maintenance_account and account_asset_management:
  confirmed (asset_id filled from the bill line after posting).
- `asset_product_item` keeps the purchase / bill matching: FALSE in the standard
  combination (split lines lose `purchase_line_id`); fixed by our override of
  `_expand_asset_line()` (copy with `include_business_fields`), tested.
- No duplicate equipment from maintenance_account: confirmed with our full
  reconciliation of each bill line (partial flows included).
- A free loan line never produces an invoice: confirmed with our overrides of
  `_can_be_invoiced()`, `_compute_recurring_next_date()` and the invoicing button.
- Supplier refunds on a fixed-asset bill create negative assets and keep the original
  (reversal included): confirmed; refused by default (question C8).
- Changing a column type (Float -> Monetary, or adding digits) makes Odoo drop every
  SQL view reading it: found by the migration rehearsal; such changes are forbidden on
  columns read by the monitor reports.

## Open decisions (external, blocking only the related parts)
- Accountant: every question, with the test choice made and where to change it, is in
  docs/QUESTIONS_COMPTABLE.md.

## Phases
0. Configuration on artdubati_test (docs/phase0/: server commands and setup_phase0.py,
   run by the owner): install the OCA modules to add; Lots & Serial Numbers; accounting
   choices for the test (asset profile with `asset_product_item` on 215400, category
   All / Fixed Assets with manual valuation), changeable by the accountant; Chez tiers
   under the warehouse root (Bougival 1, code Bg), outside Bg/Stock, checked or created.
   Order: backup, modules, dry run, --apply, control dry run.
   Script applied on 08/10/2026, control dry run clean: Lots & Serial Numbers on; asset
   profile id 4 « Matériel et outillage (test) » set on account 215400; category
   All / Fixed Assets id 19; internal location WH/Chez tiers created under the root.
   OCA modules installed (contract_line_successor, maintenance_equipment_usage,
   maintenance_request_purchase, stock_location_address with address_id /
   real_address_id checked in the database). Phase 0 done, audited.
1. Data model in maintenance_shareholder_equipment: delete the six test equipment
   records, remove obsolete fields (equipment and maintenance request), add the kept
   fields (see DEFINITIONS.md), stock.location currency / return location,
   product.category flag and its check, contract.line equipment_id and nature with
   overlap and product constraints, consumables owned only, ownership consistency checks,
   central status method and "Equipment ownership managers" group, `action_post()`
   integration (equipment to bill line, asset_id fill), contract line on supplier bill
   lines with posting lock. Integration tests for the hypotheses above.
   Audited, merged into main and deployed on artdubati_test on 08/10/2026
   (docs/phase1/README.md): preparation script applied (6 test equipment deleted,
   Bg/TEST Lent out archived after moving its 5 cement bags to Bg/Stock, table saw
   product set to serial tracking), update and 47 tests passing on the server
   (deploy_phase1.sh), category All / Fixed Assets flagged, monitor views unchanged,
   interface checks done. Phase 1 done. Manual: rewritten at the end of phase 5.
2. Equipment operations (docs/phase2/PLAN.md, revision 4 authorised on 08/10/2026):
   persistent `equipment.operation` with approval separated from execution, receipt in
   five branches (purchase, acquisition without purchase, borrowed, rented,
   consumables), exit, return, restitution; groups « Equipment Operator » and
   « Equipment Operations Approver »; protected link to pickings and moves; stock rules
   (supplier receipts and acquisitions only through an operation, no direct exit of
   equipment).
   Audited, merged into main and deployed on artdubati_test on 09/10/2026 (5ab6c36, then
   fixes up to 2345e7e: groups in their own categories, menu under Transfers, guided
   form, transfer type per warehouse, line sheets, messages naming the line and the
   path): 98 tests passing on the server, settings script applied, monitor views
   unchanged; first purchase receipt executed by the owner (order created, receipt done
   on Bg/Stock, equipment integrated, draft bill), standard « Validate » refused with the
   path to the operations. Phase 2 done.
2f. Corrections to phase 2 from the general audit of 09/10/2026 (responsible required,
   accounting treatment shown in the receipt, read-only approver, data to prepare):
   docs/phase2f/PLAN.md, revision 3 (equipment cost with `cost_known`, date, provisional
   flag and source; treatment from the real bill account, frozen in the approval;
   approver's read scope limited to referenced documents; deployment order fetch →
   setup → precheck → stop → update). P9, P10, P13, D6, D7 and D8 accepted; development
   authorised on 09/10/2026 (audit of 24d9027). Audited (corrections up to 4908235,
   precheck --keep-receipt 5b968de), merged into main (8c71b35) and deployed on
   artdubati_test on 09/10/2026 (docs/phase2f/README.md): backups (database, filestore
   at /var/lib/odoo/.local/share/Odoo/filestore), D1 and D3 clean, D4 none open
   (Bg/IN/00004 received through EQOP/2026/0437), D5 investor group removed from
   f.i.1@febitmail.com, PRECHECK OK, update OK, 141 tests 0 failed (the 3 tour tests
   skipped: no websocket-client / Chrome in odoo_web; covered by the interface checks),
   migration: 1 cost from its order (equipment 484, 15 € HT provisional, P00165),
   0 unknown; functional checks validated by the audit. Phase 2f done.
   Then (09/10/2026): the saw's bill BILL/2026/10/0006 (P00165) posted on 607000, no
   fixed asset (test choice, C19 open), equipment 484 cost 15 € HT final from the bill;
   addresses set on Bg/Stock (Bougival, FR), TIST/Stock (Istanbul, TR) and TBER/Stock
   (DE; its contact's city « PARIS CEDEX 20 », corrected to Berlin by the owner on
   09/10/2026).
3. Stock monitor on revision 2 (SQL view, OWL dashboard, access rules) and rework of the
   existing code: docs/phase3/PLAN.md revision 5, green light on 09/10/2026 after 2f.
   Developed on the branch (steps 4 to 10, implementation notes in PLAN.md §11):
   monitor stocks (`is_monitor_stock`, `monitor_currency_id`, address required), stored
   contract currency, view `lartdubati.stock.monitor` (values, set-based conversions as
   `_convert`, rent, alerts, `groups=` per field), access rules, standard views, OWL
   dashboard (3 RPCs, Hoot tests, tours), obsolete fields removed, precheck and
   post-check, translations fr/fa, screenshots. Audit of 643f95e: 5 points corrected
   (multi-company rule, no sum across currencies in the standard views, deployment
   stops odoo_web before moving the code, stock place type, TBER address), PLAN.md §11.1.
   191 tests passing locally; monitor_perf
   on 10,000 rows: 0.65-0.74 s server, 1.1 s browser; migration rehearsed on a database
   made with the 2f code. Audited, merged into main (70648a2, fast-forward) and deployed
   on artdubati_test on 10/10/2026 (docs/phase3/README.md): no equipment-contract rows,
   maintenance_equipment_contract uninstalled, the two bi_sql_editor reports deleted,
   backups, PRECHECK OK (addresses Bougival FR, Berlin DE, Istanbul TR), stop then code
   then update (deploy_modules.sh), 191 tests 0 failed (tours and Hoot skipped: no
   websocket-client / Chrome in odoo_web), migration flagged Bg/Stock, TBER/Stock,
   TIST/Stock, currency mode « latest », post-check clean, Financial button repointed,
   interface checks validated by the audit (investor, store, accountant, fa_IR RTL,
   pivot and graph with two currencies, saw 484: 15 € HT, 0, 0, « No Fixed Asset »).
   Phase 3 done. Data found by the monitor: Integrity alert on the cement of TBER/Stock
   (phase 4, P4-1), Bg/TEST Paris outside any monitor stock (emptied, 10/10/2026).
4. Home page and investor user setup (review the existing configuration). Decided
   items before the plan in docs/phase4/PLAN.md: P4-1 regularisation of third-party
   consumables (owner's option 2, 10/10/2026: removal by inventory adjustment or passage
   to the company, for TBER/Stock quant 10). Bg/TEST Paris emptied into Bg/Stock
   (internal transfer, 10/10/2026). Plan revision 5 (security design validated,
   development authorised on 10/10/2026). P4-1 step 1 done (CHARACTERISATION.md;
   step 2 = separate plan, C23). Developed on the branch, audit pending: investor
   accounts read only the monitor (default deny in `_get_allowed_models`, rules on the
   few listed models, mail and filter models readable with no record, export checked,
   action load whitelist, `run()` refused, exact action per home button, forbidden
   groups refused), home page as module data (adoption of the script's records in any
   language, rehearsal finding), back link on the dashboard, precheck / post-check,
   fr/fa; audit of dff33cb corrected (public methods and external API guarded, home
   adoption by screen then its buttons, S2 a real return); audit of 6063db1 corrected
   (whitelist of authenticated routes for investor accounts: get_definitions, /json,
   /report refused, docs/phase4/ROUTES.md; own password change tested); audit of
   2071e6e corrected (whitelist of public routes for investor sessions, no group channel
   on the investor's websocket, own presence); audit of 3326829 corrected (/mail/data
   options whitelisted for investors: `failures` dropped; websocket channels tested
   without websocket-client); 230 tests
   passing locally; rehearsals on the phase 3 code clean. Before deployment: Q7
   (Purchase rights off `test_investor`), one atomic update.
5. Translations, deployment checklist (docs/deployment/investor_home.md).
6. Functional phases proposed by the audit of 6063db1, order to set by the owner
   (docs/ROADMAP.md): recurring expenses and contracts, bill payment and bank
   reconciliation, insurance register (ten-year liability included), Fleet linked to
   equipment and assets, worksites and stock consumption, workwear / PPE (« VT »
   = vêtements de travail, confirmed), operational maintenance, supplier bill intake, one-off and
   employee expenses.
Last. Manual rewrite for all phases (cards citing removed or changed fields, new
   receiving procedures, Investor tab), after every functional phase.

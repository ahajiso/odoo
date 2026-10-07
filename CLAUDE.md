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
- Single company. DB container: odoo_db (`docker exec -i odoo_db psql -U odoo -d artdubati_test`).
- Languages: en_US, fr_FR, fa_IR (RTL). All UI strings translatable; .po files come from
  `odoo --i18n-export`, never written by hand.
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
     Currently configured with OCA web_quick_start_screen (docs/investor_home/).
   - Financial -> Stock monitor. Currently two OCA bi_sql_editor reports
     (docs/stock_monitor/).

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
- Main rule: use standard Odoo and OCA data and features first; change the repo only
  when necessary.
- Develop and test on artdubati_test only; production only on explicit request.
- Never guess an external ID: look it up and show it first.
- Every Odoo change requires the manual update (FR, then EN/FA) and a changelog line.
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

To decide when phase 3 is planned: keep bi_sql_editor for the monitor (reports defined
in docs/stock_monitor/, two reports because a column cannot be hidden per group) or
replace it by a module model on a SQL view with `groups=` per field. Same question for
the home page (web_quick_start_screen configuration versus a client action).

## Existing code to rework (built on the 04/10 decisions)
- lartdubati_investor_home/models/account_move_line.py: sets `current_location_id` on
  equipment created from a bill → replaced by creation at receipt and linking at
  posting.
- lartdubati_investor_home/models/maintenance_equipment.py: requires an internal
  `current_location_id` on every active equipment → only for non-stock assets.
- lartdubati_investor_home/models/res_company.py: `stock_monitor_replacement_price`
  (replacement price of borrowed / rented consumables) → moot while consumables are
  owned only; `stock_monitor_currency_mode` stays pending the accountant.
- docs/stock_monitor/*.sql: ownership computed from acquisition_mode / owner_type, rent
  from maintenance_equipment_contract → rewrite on revision 2.
- Tests in lartdubati_investor_home/tests/ to update accordingly; access profile tests
  stay valid.

## Hypotheses to confirm by Odoo integration tests (not acquired before)
- Our `action_post()` override runs after maintenance_account and
  account_asset_management: the asset and the equipment both exist on return of super().
- `asset_product_item` splits a received purchase bill line into quantity-1 lines, one
  asset each, without breaking the purchase / bill matching.
- Linking the bill line to equipment created at receipt prevents maintenance_account
  from creating a duplicate.
- A free loan contract line without invoicing recurrence never produces an invoice, not
  even at zero.

## Open decisions (external, blocking only the related parts)
- Conversion of values to each stock's currency: rate and date (accountant).
- Meaning of handover_value (transfer, contribution or provision) and counterpart
  account (accountant).
- Fixed-asset category setup and rental expense account (6135?) (accountant).

## Phases
0. Configuration on artdubati_test: install the OCA modules to add; asset profiles with
   `asset_product_item`; fixed-asset product category (manual valuation, class 21 account
   with asset profile) to be validated by the accountant; location tree Off-site / At
   third parties.
1. Data model in maintenance_shareholder_equipment: delete the six test equipment
   records, remove obsolete fields (equipment and maintenance request), add the kept
   fields (see DEFINITIONS.md), stock.location currency / return location,
   product.category flag and its check, contract.line equipment_id and nature with
   overlap and product constraints, consumables owned only, ownership consistency checks,
   central status method and "Equipment ownership managers" group, `action_post()`
   integration (equipment to bill line, asset_id fill), contract line on supplier bill
   lines with posting lock. Integration tests for the hypotheses above.
2. Receiving and exit wizards: four branches, return from a third party, restitution
   to the owner, tests (including free loan producing no invoice).
3. Stock monitor on revision 2 (SQL view, access rules) and rework of the existing code.
4. Home page and investor user setup (review the existing configuration).
5. Translations, manual update, deployment checklist (docs/deployment/investor_home.md).

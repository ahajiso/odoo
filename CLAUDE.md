# Project: Investor Home and Stock Monitor (L'Art du Bâti, Odoo 18 CE)

## Context
- Odoo 18.0 Community, Docker (container odoo_web), VPS. Prod DB: artdubati. Test DB: artdubati_test.
- This repo is the custom addons folder: each module sits at the repo root and is cloned
  on the server at /opt/odoo/addons/custom. Existing modules: maintenance_shareholder_equipment,
  lartdubati_facturation, lartdubati_env_ribbon, lartdubati_manual, plus OCA
  account_asset_management (with report_xlsx, report_xlsx_helper).
- Installed on artdubati_test (checked by the owner): account_asset_management,
  maintenance_product, maintenance_account. The latter two are not in this repo.
- OCA modules to add (18.0): contract, contract_line_successor (OCA/contract),
  maintenance_equipment_usage, maintenance_request_purchase (OCA/maintenance),
  stock_location_address (OCA/stock-logistics-transport). Not used:
  maintenance_equipment_contract (unqualified many2many), maintenance_purchase.
- Languages: en_US, fr_FR, fa_IR (RTL). All UI strings translatable; .po files come from
  `odoo --i18n-export`, never written by hand.
- Business definitions are in docs/DEFINITIONS.md. Read it first and follow it exactly.
  It is a revisable design document: report every finalised decision there.

## Goal
Two modules:
1. `maintenance_shareholder_equipment` (existing, slimmed down, technical name kept):
   equipment data model (ownership, lot, asset, replacement value, warranty, insurance),
   stock location attributes, fixed-asset category check, contract line link, receiving
   and exit wizards, bill / contract / asset integration.
2. `lartdubati_investor_home` (new, depends on 1):
   - Home page (client action, home action of the investor user): one button per main
     function: Administrative, Financial, Commerce & Services, Production.
     Only Financial is implemented; the others are "coming soon" placeholders.
   - Financial -> Stock monitor, its SQL view, access profiles and record rules.

## Stock monitor
- Choose a stock (combo box) or filter by country / state / city / other attribute.
  A stock is a location with a place type; its stored address_id gives the geography.
- Family: assets, consumables or both. Ownership: owned / borrowed / rented / lent out.
- Per stock: quantity, inventory value, accounting value, rental cost (see definitions).
- Assets = maintenance.equipment (stock-managed with a serial number, or non-stock with a
  monitor location), consumables = stock.quant, joined in a unified SQL-view reporting
  model (`_auto = False`, read-only, per-stock currency, grouped by currency). Fixed-asset
  categories count 0 in stock value; their value comes from account.asset. Contract data
  is joined through a subquery aggregated per equipment (one row per equipment).
- Receiving wizard: starts from the ownership status (purchase / borrowed / rented) and
  an exit wizard for lent out; mandatory stock, family, status; equipment created once at
  receipt; enforced by model constraints.
- Rent is not stored on the equipment: it comes from the equipment's rental contract
  line (OCA contract) and the posted bills linked to it.
- Access: access profiles (allowed countries / stocks / ownership statuses / families),
  enforced by record rules on the SQL view and every model the monitor opens.

## Rules
- Odoo standards: extend by inheritance, no raw SQL writes, no core patches.
- Develop and test on artdubati_test only; production only on explicit request.
- Never guess an external ID: look it up and show it first.
- Every Odoo change requires the manual update (FR, then EN/FA), a changelog line,
  and regeneration of /manuel. The procedure is in the document
  claude/maintenance-manuel-odoo.md of the Claude project "Odoo" (read it with the
  Projects tool before touching the manual). New "Investor" profile tab in the three manuals.
- Update module on the server: `docker exec -i odoo_web odoo -d artdubati_test -u <module>
  --stop-after-init` then `docker restart odoo_web`.
- Small commits, clear messages. Propose a plan before coding each phase.

## Open decisions (external, blocking only the related parts)
- Conversion of values to each stock's currency: rate and date (accountant).
- Meaning of handover_value (transfer, contribution or provision) and counterpart
  account (accountant).
- Fixed-asset category setup and rental expense account (6135?) (accountant).

## Phases
0. Configuration on artdubati_test: install the OCA modules listed above; asset profiles
   with `asset_product_item`; fixed-asset product category (manual valuation, class 21
   account with asset profile) to be validated by the accountant; consumables at average
   cost; consignment option (owner on stock); location tree Off-site / At third parties.
1. Data model in maintenance_shareholder_equipment: delete the six test equipment
   records, remove obsolete fields (equipment and maintenance request), add the kept
   fields (see DEFINITIONS.md), stock.location place type / currency / return location,
   product.category flag and its check, contract.line equipment_id and nature with
   overlap and product constraints, ownership consistency checks, central status method
   and "Equipment ownership managers" group, `action_post()` integration (equipment to
   bill line, asset_id fill), contract line on supplier bill lines with posting lock.
2. Receiving and exit wizards: four branches, return from a third party, restitution
   to the owner, tests (including free loan producing no invoice).
3. lartdubati_investor_home: access profiles and record rules, unified SQL view and
   stock monitor views.
4. Home page client action and investor user setup.
5. Translations, manual update, deployment checklist.

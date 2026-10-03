# Project: Investor Home and Stock Monitor (L'Art du Bâti, Odoo 18 CE)

## Context
- Odoo 18.0 Community, Docker (container odoo_web), VPS. Prod DB: artdubati. Test DB: artdubati_test.
- This repo is the custom addons folder: each module sits at the repo root and is cloned
  on the server at /opt/odoo/addons/custom. Existing modules: maintenance_shareholder_equipment,
  lartdubati_facturation, lartdubati_env_ribbon, lartdubati_manual, plus OCA
  account_asset_management (with report_xlsx, report_xlsx_helper), installed on artdubati_test.
- Also installed on artdubati_test (OCA, not in this repo): maintenance_product,
  maintenance_partner, maintenance_request_repair, maintenance_equipment_category_hierarchy.
- Single company. DB container: odoo_db (`docker exec -i odoo_db psql -U odoo -d artdubati_test`).
- Languages: en_US, fr_FR, fa_IR (RTL). All UI strings translatable; .po files come from
  `odoo --i18n-export`, never written by hand.
- Business definitions are in docs/DEFINITIONS.md. Read it first and follow it exactly.

## Goal
New module `lartdubati_investor_home`:
1. Home page (client action, home action of the investor user): one button per main
   function: Administrative, Financial, Commerce & Services, Production.
   Only Financial is implemented; the others are "coming soon" placeholders.
2. Financial -> Stock monitor.

## Stock monitor
- Choose a stock (combo box) or filter by country / state / city / other attribute.
- Family: assets, consumables or both. Ownership: owned / borrowed / rented / lent out.
- Per stock: quantity, inventory value, accounting value, rental cost (see definitions).
- Assets = maintenance.equipment, consumables = stock.quant, joined in a unified
  SQL-view reporting model (read-only, per-stock currency, grouped by currency).
- Receiving form: mandatory stock, family, ownership status; creates an equipment record
  or a stock move; enforced by model constraints.
- Access: per-user allowed countries / stocks / ownership statuses / families, enforced
  by record rules on all models read, including the SQL view.

## Rules
- Odoo standards: extend by inheritance, no raw SQL writes, no core patches.
- Develop and test on artdubati_test only; production only on explicit request.
- Never guess an external ID: look it up and show it first.
- Every Odoo change requires the manual update (FR, then EN/FA), a changelog line,
  and regeneration of /manuel. The procedure and all definitions (card codes, doc/tab ids,
  writing rules, terminology, impact matrix) are in docs/manual/maintenance-manuel-odoo.md
  and docs/manual/definitions-manuel.md in this repo — read those first; they no longer
  require access to the Claude project "Odoo". The manual's actual content (the fiches)
  still lives only in the three Claude Docs documents listed there, reachable only from a
  session with Claude Docs / claude.ai access, not from this repo alone. The generator
  that turns those documents into /manuel's HTML pages is in lartdubati_manual/tools/
  (see its README). New "Investor" profile tab in the three manuals.
- Update module on the server: `docker exec -i odoo_web odoo -d artdubati_test -u <module>
  --stop-after-init` then `docker restart odoo_web`.
- Small commits, clear messages. Propose a plan before coding each phase.

## Decisions (validated by the owner)
- Main rule: use standard Odoo data and features first; change the repo only when necessary.
- Consumable ownership uses standard stock.quant owner_id (already excluded from valuation
  by Odoo): no owner or company = owned; quant in a lent-out stock = lent_out; third-party
  owner = borrowed, or rented when rental terms exist. No custom field in the quant key.
- Equipment ownership is derived from existing values: acquisition_mode rental = rented,
  borrowed = borrowed, loaned_out = lent_out; purchase = owned if owner_type is company,
  otherwise borrowed. Who owns it is secondary.
- The new ownership field must not be labelled "Ownership Status" (already used by
  ownership_state).
- Access record rules are global (not group rules, which Odoo ORs with
  maintenance rules) and only filter internal stock locations.
- Phase 0: consumable product categories 11-17 set to average cost on artdubati_test.
  Asset profiles wait for the accountant's answers.

## Phases
0. Install and configure OCA account_asset_management on artdubati_test (asset categories,
   depreciation rules to be validated by the accountant). Set consumables to average cost.
1. Data model: location address, place type, currency; unified ownership status
   (+ rent amount/period/start date on equipment); access fields and record rules.
2. Unified reporting model and stock monitor views.
3. Receiving form with constraints.
4. Home page client action and investor user setup.
5. Translations, manual update, deployment checklist.

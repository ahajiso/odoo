# Project: Investor Home and Stock Monitor (L'Art du Bâti, Odoo 18 CE)

## Context
- Odoo 18.0 Community, Docker (container odoo_web), VPS. Prod DB: artdubati. Test DB: artdubati_test.
- This repo is the custom addons folder: each module sits at the repo root and is cloned
  on the server at /opt/odoo/addons/custom. Existing modules: maintenance_shareholder_equipment,
  lartdubati_facturation, lartdubati_env_ribbon, lartdubati_manual, plus OCA
  account_asset_management (with report_xlsx, report_xlsx_helper), present but NOT confirmed installed.
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
  and regeneration of /manuel. The procedure is in the document
  claude/maintenance-manuel-odoo.md of the Claude project "Odoo" (read it with the
  Projects tool before touching the manual). New "Investor" profile tab in the three manuals.
- Update module on the server: `docker exec -i odoo_web odoo -d artdubati_test -u <module>
  --stop-after-init` then `docker restart odoo_web`.
- Small commits, clear messages. Propose a plan before coding each phase.

## Phases
0. Install and configure OCA account_asset_management on artdubati_test (asset categories,
   depreciation rules to be validated by the accountant). Set consumables to average cost.
1. Data model: location address, place type, currency; unified ownership status
   (+ rent amount/period/start date on equipment); access fields and record rules.
2. Unified reporting model and stock monitor views.
3. Receiving form with constraints.
4. Home page client action and investor user setup.
5. Translations, manual update, deployment checklist.

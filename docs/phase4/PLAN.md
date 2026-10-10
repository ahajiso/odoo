# Phase 4 – home page and investor user setup: plan (revision 1, 10/10/2026)

Scope (CLAUDE.md): investor home page (decision left open in phase 3: OCA
web_quick_start_screen configuration versus a client action), investor user setup,
review of the existing configuration; plus P4-1 decided by the owner. **No code before
the audit of this plan and the owner's go.**

Sources read for this plan: `docs/investor_home/` (README, setup_investor_home.py), the
OCA sources of `web_quick_start_screen` (OCA/web 18.0, c3120b0) and
`base_menu_visibility_restriction` (OCA/server-ux 18.0, 737262e), our
`lartdubati_investor_home` (groups, rules, user tab), and a local probe of what an
investor can read (`probe_investor.py`, §2).

## 1. Current state

- Home page = configuration made by `setup_investor_home.py` through JSON-RPC: a quick
  start screen « Investor Home » with 4 buttons (Financial → server action
  `lartdubati_investor_home.action_server_stock_monitor` → dashboard; the 3 others → a
  « coming soon » server action), translations EN/FR/FA written by the script, 4 menus
  hidden from the investor group with `excluded_group_ids` (Discuss, Dashboards ×3).
  Validated by the owner after phase 3 (step 8b).
- Investor user = internal user + group « Stock Monitor Investor » + a stock access
  profile (user form, « Stock Access » tab) + home screen and home action set by hand
  or by the script (`setup_investor_home.py <login>`).
- What the investor may read is decided by the standard rights of an **internal user**,
  narrowed by our rules on the monitor, the internal locations and the move lines only.

## 2. Findings (verified locally, to confirm on the server with the probe)

F1. **Every internal user may modify the home page.** `web_quick_start_screen` gives
`base.group_user` read **and write** on `quick.start.screen` and
`quick.start.screen.action` (security/ir.model.access.csv). An investor can rename a
button or point it to another action, for every user.

F2. **The profile does not bound what an investor can read outside the monitor.** Probe
on a local database (investor without profile, so the monitor shows 0 rows):

| model | ACL | records read |
|---|---|---|
| stock.quant | read | **all** (8/8: product, quantity, location id, value) |
| product.template / product.product | read | all, **cost included** (`standard_price` is `groups="base.group_user"`) |
| stock.warehouse | read | all |
| account.account | read | all (660) |
| maintenance.request | **read, write, create, delete** | standard maintenance for every internal user |
| maintenance.equipment | read | only followed ones (standard rule) |
| stock.location | read | profile rule (phase 3) |
| stock.move.line | none in practice | rule of 2f (0) |

This contradicts DEFINITIONS.md « Investors read only the stock monitor »: an investor
limited to Germany can still read the quants and costs of every stock through the
JSON-RPC API or a URL, even though no menu shows them.

F3. **Menus are hidden by a blacklist.** Shown to the local investor: Discuss,
Dashboards (hidden on the server by the script), Stock Monitor, **Maintenance**
(standard, open to every internal user), **Apps**. Every module installed later that
opens a menu to internal users shows up for investors too.

F4. On the local test database `base.group_user` implies « Technical Features »
(developer tools for every internal user). To check on artdubati_test (probe, groups
line); if so, investors see the debug tools.

## 3. Proposal

### P4-0. Home page: keep OCA web_quick_start_screen, hardened and versioned (recommended)

Options weighed:
- **A. Keep the quick start screen** (recommended). It is standard OCA, it works and the
  owner validated it; it accepts client actions too (`action_ref_id` selection, no model
  so always visible). Changes:
  - F1: two group rules on `quick.start.screen` and `quick.start.screen.action` for
    write / create / delete: FALSE for Internal User, TRUE for Settings (group rules are
    ORed: an administrator keeps the rights, an investor loses them). Read unchanged.
  - The screen, its 4 buttons, the « coming soon » server action and their EN/FR/FA
    texts become **data of `lartdubati_investor_home`** (XML with external IDs,
    translations in the module's .po from `--i18n-export`) instead of the RPC script:
    versioned, tested, installed in production by the module update. The records the
    script created are adopted (their external IDs are bound in a pre-migration, found
    by their English name), so no duplicate. New dependency: `web_quick_start_screen`
    (already installed on artdubati_test).
  - The Financial button points directly to the client action
    `lartdubati_investor_home.action_stock_monitor` (no server action needed; the
    server action stays for compatibility, removed in phase 5).
- B. Own OWL client action « Investor Home ». Full control of the design, no write risk,
  but code to write and maintain for what the OCA module already does. Not
  recommended (main rule: OCA first).

### P4-2. Investor data perimeter (F2): « read only the monitor », enforced

A **pure investor** = member of « Stock Monitor Investor » without Inventory / User
(the definition already used by the move-line rule of 2f). For pure investors only,
global rules computed per user (same pattern as `stock_access_rule_domain`): no access
(FALSE domain, all modes) to the models the monitor makes unnecessary. List to confirm
with the server probe; proposed:
- stock: `stock.quant`, `stock.lot`, `stock.warehouse`, `stock.move`, `stock.picking`;
- products: `product.template`, `product.product`;
- equipment: `maintenance.equipment`, `maintenance.request`;
- accounting: `account.account` (and every accounting model the probe shows readable).
Kept: `res.users`, `res.partner`, `res.company`, `res.currency` (the web client needs
them), `lartdubati.stock.monitor` (profile rule), `stock.location` (profile rule).
Staff (Inventory / User, Accounting / Read-only, equipment groups) is unchanged: these
rules return TRUE for any non-pure-investor, so Inventory is not affected (the reason
global quant rules were refused on 04/10/2026).
Tests: a pure investor reads none of these models (search, read, read_group, export),
the dashboard and the analysis views still work for him, staff rights unchanged.

### P4-3. Investor menus: whitelist instead of blacklist (F3)

For pure investors, `ir.ui.menu._visible_menu_ids` keeps only the menu tree of the stock
monitor (and the quick start « Start » menu if shown): Discuss, Dashboards, Maintenance,
Apps and any future app disappear without listing them. Staff unchanged. Like
`base_menu_visibility_restriction`, it only hides menus (access stays governed by
P4-2). Then the `excluded_group_ids` lines of the script are dropped and
`base_menu_visibility_restriction` can be uninstalled (owner's choice, Q3).
Tests: the investor's root menus are exactly « Stock Monitor » (and « Start »); a
staff user still sees Inventory and Maintenance.

### P4-4. Investor user setup without a script

- When a user becomes a pure investor (create or write of the groups), the home screen
  « Investor Home » and the home action « Quick Start Screen » are set if empty; the
  same for the existing investors in the migration.
- Warning banner on the user form: investor without stock access profile (sees no
  stock), or investor holding Inventory / Accounting / equipment groups (then staff
  rights apply, P4-2 rules do not).
- `setup_investor_home.py` reduced to nothing to do (or deleted) once P4-0 is in the
  module; README updated: create the user, tick the investor group, choose the profile.

### P4-1. Regularisation of third-party consumables (owner's decision, 10/10/2026)

Found by the stock monitor after the phase 3 deployment: quant 10 at TBER/Stock, 15
« TEST Cement bag » owned by « TEST Supplier (owner) » (consignment test of phase 0),
Integrity alert. Consumables are owned only in v1 (DEFINITIONS.md), and
`stock.move.line._check_third_party_owner` (phase 2) refuses every move line carrying an
owner other than the company unless it is the serial number of a borrowed or rented
equipment of that owner. Standard Odoo changes a quant owner only through a move (the
owner column of an existing quant is read-only, `readonly="id"` in the inventory list),
so such a leftover can neither leave the stock nor become the company's.

To build (option 2 chosen by the owner):
- allow, for an untracked consumable (no serial, `maintenance_ok` false) whose existing
  quant belongs to a third party, only the two regularisations:
  1. its removal by an inventory adjustment (internal location → inventory loss
     location, line owner = the quant's owner);
  2. its passage to the company by an internal transfer on the same location with
     « Assign Owner » = the company (source line owner = the third party, destination
     quant without owner);
- everything else stays refused: a third-party consumable entering the stock, moving
  between locations, leaving to a customer or supplier;
- tests: both regularisations accepted, every other case still refused, the monitor's
  Integrity alert gone afterwards, the valuation of the passage to the company (average
  cost; entry if the category is in automated valuation) checked;
- to check before coding: how Odoo 18 builds the move lines of an owner change (one
  internal line with `owner_id` = third party and the destination quant's owner from
  the picking's `owner_id`), and whether the passage to the company produces a
  valuation layer.
Then, on artdubati_test, the owner's choice for quant 10 (remove or pass to the company).

## 4. Order of work (one commit per step)

0. Server probe (`probe_investor.py`, read-only, run by the owner as `test_investor`)
   → the P4-2 model list and F4 confirmed; plan revised if needed.
1. P4-1 (independent, in `maintenance_shareholder_equipment`).
2. P4-2 rules and tests.
3. P4-3 menu whitelist and tests.
4. P4-0 home page as module data, rules of F1, pre-migration adopting the script's
   records, tests (Python; a tour investor → home → Financial → dashboard, local only).
5. P4-4 user setup, migration of existing investors, form warnings.
6. Translations (`--i18n-export`), README and server procedure (`docs/phase4/README.md`:
   backup, fetch, precheck, `deploy_modules.sh`, post-check, probe again as
   `test_investor` expecting the new perimeter), DEFINITIONS.md (Access, home page),
   CLAUDE.md.

## 5. Questions for the owner

- Q1. Home page: A (OCA quick start screen, hardened and moved into the module,
  recommended) or B (own client action)?
- Q2. Pure investors: no access at all to quants, products, warehouses, equipment,
  maintenance requests and accounting models (P4-2)? Any of them to keep?
- Q3. Menus by whitelist (P4-3); Discuss hidden too (no chat with the company from the
  investor account)? Then uninstall `base_menu_visibility_restriction`?
- Q4. An investor who also holds Inventory / Accounting / equipment groups: allowed
  (staff rights apply, warning on the form) or refused by a constraint?

## 6. Verified / not verified / hypotheses

- Verified locally: F1 in the OCA source; F2 and F3 by the probe on a local database
  (our modules, no Accounting app data beyond the chart, no calendar or HR); the OCA
  quick start screen accepts `ir.actions.client` and shows it without a model check.
- Not verified (server): the probe as `test_investor` (installed apps differ:
  `lartdubati_facturation`, accounting data, possibly HR / calendar); F4; how many
  investor users exist.
- Hypotheses: the investor's web client needs only `res.users`, `res.partner`,
  `res.company`, `res.currency` and our models (to confirm by the tour in step 4 under
  the P4-2 rules); adopting the script's records by English name finds exactly one
  record each (checked by the pre-migration, which stops otherwise); the buttons
  (`run_action`, an object button of the kanban) still run for a user without write
  access on `quick.start.screen.action` once F1 is fixed (to test first in step 4).

## Data cleaned after the phase 3 deployment (10/10/2026)
Bg/TEST Paris (id 21): its 40 « TEST Cement bag » moved to Bg/Stock by a standard
internal transfer (Bg/Stock now 46); « Outside Any Monitor Stock » alert gone; the
location archived.

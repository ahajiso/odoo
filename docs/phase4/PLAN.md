# Phase 4 – home page and investor user setup: plan (revision 5, 10/10/2026)

Scope (CLAUDE.md): investor home page, investor user setup, review of the existing
configuration, P4-1. **No code before the audit of this plan and the owner's go.**

History:
- revision 2 answered the audit of revision 1: default-deny data whitelist, every leak
  covered, cumulated rights refused, real security tests, P4-1 characterised first, C23;
- revision 3 answers the audit of revision 2:
  1. the server probe as `test_investor` is the reference (§1);
  2. the probe no longer reads `res.groups`;
  3. no model-wide access to `ir.actions.*`, menus restricted by rule;
  4. allowed groups = full transitive closure of Internal User;
  5. security first in the order of work (§6);
- revision 4 answers the audit of revision 3 (actions bypass the ACL): revision 3 was
  wrong on two points, checked in the Odoo 18 source: `/web/action/load` reads the
  action in sudo and does **not** check its groups; `ir.actions.server.run()` loops on
  `self.sudo()`, so refusing the model's ACL does not stop a run (a server action
  granted to Internal User, or without groups on a model the user may write, runs).
  New P4-2d: whitelist of loadable actions, central refusal of `run()`, exact check of
  the action behind a home button, direct tests;
- revision 5 (security design validated, development authorised on 10/10/2026): one
  atomic update for steps 2 a-e (§6), each button checked against its own action; Q7
  not yet done on the server (probe of the audit), the precheck blocks until it is.

Owner's answers: Q1 A; Q2 nothing outside the monitor but the demonstrated technical
minimum; Q3 whitelist, Discuss hidden, `base_menu_visibility_restriction` uninstalled
only once nothing else uses it; Q4 cumulated rights refused; Q5 keep Technical Features
(standard implication of Internal User); Q6 export allowed, from the monitor only, on
the fields the investor may read; Q7 Purchase / Administrator and Purchase / User
removed from `test_investor` by the owner.

Sources: `docs/investor_home/`, OCA `web_quick_start_screen` (OCA/web 18.0, c3120b0) and
`base_menu_visibility_restriction` (OCA/server-ux 18.0, 737262e), Odoo 18 source
(`ir.model.access._get_allowed_models` / `check`, `ir.ui.menu._visible_menu_ids`,
`web/controllers/action.py` load / run, `base_groups.xml`), our module, the probe.

## 1. Findings

**Server probe as `test_investor` (10/10/2026, read-only), the reference:**
- groups: Stock Monitor Investor, Internal User, **Purchase / Administrator, Purchase /
  User**, Technical Features, Multi Currencies, Different Stock Owners, Lots / Serial
  Numbers, Multiple Stock Locations, Multiple Warehouses, delivery reminder;
- root menus: Calendar, Contacts, Dashboards, Stock Monitor, Purchase, Maintenance,
  Apps, Manuel;
- data (ACL, records read): monitor r (2 rows); quick start screens and buttons **rw**;
  `res.partner` rwc (16); `res.users` r (5); quants r (8); warehouses r (3); locations r
  (15); stock moves, pickings rwcd (12, 6); products and categories rwcd (13, 12);
  maintenance requests rwcd; **journal entries and lines rwcd (8, 24)**; **purchase
  orders rwcd (2)**; chart of accounts r (660); **messages rwcd (134), attachments
  rwcd (90), channels rwc (2)**; calendar rwcd; equipment operations, assets, contracts,
  access profiles: none.
(An earlier run with an administrator account is not used.)

What it shows:
- F1. The home page is writable by investors (OCA ACL: `base.group_user` read and
  write on `quick.start.screen` and `quick.start.screen.action`).
- F2. An internal user's standard rights reach quants, warehouses, products and costs,
  the chart of accounts, messages, attachments, channels, calendar, contacts; the
  Purchase groups add purchase orders, journal entries, moves and pickings.
- F3. Menus hidden by a blacklist: every app open to internal users is shown.
- F4. Technical Features is implied by Internal User in standard Odoo 18
  (`base_groups.xml`); not changed (Q5).
- F5. `test_investor` holds Purchase / Administrator and Purchase / User: forbidden for
  an investor (§2, P4-5); to be removed by the owner before the update.

## 2. Security model for investors

### Investor account
A user of « Stock Monitor Investor ». It may hold only: that group, Internal User,
**every group in the transitive closure of Internal User** (`trans_implied_ids` of
`base.group_user`, which includes Technical Features, Multi Currencies, stock technical
groups when the settings imply them), and « Access to export feature » (Q6). Anything
else is refused (P4-5). Staff accounts are not affected by anything in this section.

### P4-2a. Central default deny of data
Every non-sudo access to a model goes through `ir.model.access.check()`, which reads the
set of allowed models from `_get_allowed_models(mode)` (ormcache per uid and mode,
cleared when groups change). Override (inheritance): for an investor account the set
becomes `super() ∩ INVESTOR_MODELS[mode]`. Any model not listed, including models of
modules installed later, is refused in every mode through the ORM, JSON-RPC and URLs,
whatever ACL another module grants.

`INVESTOR_MODELS` starts empty; each entry is justified here and tested (§4). Proposed:
- read: `lartdubati.stock.monitor`; `quick.start.screen`, `quick.start.screen.action`
  (home page); `res.users`, `res.partner`, `res.company`, `res.currency`, `res.lang`
  (web client session, amounts, language switch); `res.users.settings` (web client);
  `ir.ui.menu` (menu loading runs as the user, `_visible_menu_ids`);
- write: `res.users` (own preferences through the standard self-writeable fields),
  `res.users.settings`;
- create / delete: none.
Deliberately **not** listed:
- `ir.actions.*`: the investor needs no read access to the action models
  (`/web/action/load` reads in sudo). Refusing them is **not** what protects actions:
  `load` does not check groups and `run()` works in sudo; actions are protected by
  P4-2d;
- `ir.ui.view`, `ir.model`, `ir.model.fields`: views are loaded in sudo by
  `get_views`; added only if a test proves otherwise, with a record rule;
- `res.groups` (the probe no longer needs it), stock, products, equipment,
  maintenance, accounting, purchase, sales, contracts, `mail.*`, `ir.attachment`,
  `discuss.channel`, `calendar.event`, `lartdubati.stock.access`, everything else.
Any addition found necessary by the tests is written in this plan with its reason and
its record rule before being coded.

### P4-2d. Actions: whitelist and central refusal of server actions
For an investor account (`not env.su`):
1. **Loadable actions** (override of the `Action` controller's `load`, `@http.route()`
   kept; `load_breadcrumbs` and `/odoo/action-…` URLs go through it): the action is
   resolved (id, external ID or path) and returned only if it is one of
   `INVESTOR_ACTIONS`, explicit external IDs:
   - the home window action of P4-0 (`lartdubati_investor_home.action_investor_home`);
   - the dashboard client action `lartdubati_investor_home.action_stock_monitor`;
   - the detailed analysis `lartdubati_investor_home.action_stock_monitor_analysis`;
   - the « coming soon » client action of P4-0;
   any other action, by any id, raises « action not found » (no metadata returned).
   Any addition proved necessary by the tests (e.g. an action of the user menu) is
   added here with its reason before being coded.
2. **Server actions**: override of `ir.actions.server.run()`: for an investor account,
   outside sudo, refused before anything (AccessError), whatever its groups and model;
   no server action is in the investor's whitelist. Base automations are not affected:
   `base_automation` runs its actions from `self.sudo()` (checked in the source), and
   so are framework internals.
3. **Home buttons** (override of OCA `quick.start.screen.action.run_action`): for an
   investor account, the action dictionary is built in sudo only if
   - the button belongs to the « Investor Home » screen (external ID), and
   - its `action_ref_id` is one of `INVESTOR_ACTIONS` with the expected type and tag
     (`ir.actions.client` `lartdubati_stock_monitor`, `ir.actions.client`
     `lartdubati_coming_soon`),
   otherwise AccessError. A button an administrator pointed by mistake to another
   action is refused to investors.
The data of whatever an allowed action opens stays governed by P4-2a / P4-2b.

### P4-2b. Record rules on the listed models
Global rules computed per user (pattern `stock_access_rule_domain`), TRUE for staff:
- `ir.ui.menu`: only the Stock Monitor menu tree (this is also P4-3: the same rule hides
  the other menus and refuses reading them by RPC);
- `quick.start.screen`: the « Investor Home » screen; `quick.start.screen.action`: its
  buttons;
- `res.users`: own record; `res.partner`: own partner and the company's partner;
  `res.company`: own companies; `res.users.settings`: own record;
- `lartdubati.stock.monitor`: unchanged (profile and multi-company rules).
The `stock.location` and `stock.move.line` rules of phases 2f and 3 stay.

### P4-2c. Fields
`groups=` keep protecting sensitive fields of the listed models (monitor staff and
accountant fields, `res.users` technical fields). Export (Q6): only the monitor is
readable, so only the monitor can be exported, and only the fields readable by the
investor; tested on every staff and accountant field and on personal fields.

### P4-5. Cumulated rights refused
- Constraint on `res.users` (create and write of groups): an investor account holding a
  group outside the allowed set raises an error naming the groups to remove. The
  allowed set is computed (investor group, Internal User and its transitive closure,
  export), never hard-coded.
- Deployment precheck, **blocking**: lists every investor account with a forbidden
  group (and, as information, investors without access profile). The owner removes the
  groups in Settings → Users; nothing is removed automatically; the update runs only on
  an empty list. Expected today: `test_investor` (Purchase / Administrator, Purchase /
  User).

## 3. Interface

### P4-3. Menus by whitelist
By the `ir.ui.menu` rule of P4-2b: the investor's menu tree is the Stock Monitor tree
(the home page is the home action, it needs no menu). Discuss, Calendar, Contacts,
Dashboards, Purchase, Maintenance, Apps, « Manuel » and any future app disappear, and
their menu records cannot be read by RPC. Staff unchanged.
`base_menu_visibility_restriction`: the precheck lists every menu with
`excluded_group_ids`; uninstalled by the owner only if nothing but the four investor
exclusions of the script uses it.

### P4-0. Home page (Q1: A), adapted to P4-2
- The home page needs no server action:
  - the user's home action becomes a **window action** of our module (kanban
    `web_quick_start_screen.quick_start_screen_action_kanban` on the « Investor Home »
    buttons), loaded by `/web/action/load` in sudo; instead of the OCA server action
    `web_quick_start_screen.start_screen_action`, which `/web/action/run` would run as
    the user;
  - Financial → the client action `lartdubati_investor_home.action_stock_monitor`;
  - the three « coming soon » buttons → a client action of our module (tag
    `lartdubati_coming_soon`) showing a translated notification (`_t`, .po); the
    « Investor Home: coming soon » server action is retired;
  - the buttons' `run_action` reads the referenced action as the user, which P4-2a
    refuses: override of P4-2d point 3 (exact screen, exact action, type and tag).
- F1: write / create / delete on screens and buttons only for Settings (two group
  rules; investors are already read-only through P4-2a).
- The screen, buttons and translations become data of `lartdubati_investor_home`
  (external IDs, `--i18n-export`); the script's records are adopted by a pre-migration
  (found by English name, stops on zero or several). New dependency
  `web_quick_start_screen`.

### P4-4. Investor user setup
- Making a user an investor account sets its home action (window action above) if
  empty; the migration does it for existing investors.
- Warning on the user form: investor without access profile.
- `setup_investor_home.py` retired once P4-0 is in the module; README updated. Manual
  (« Investor » tab): phase 5.

## 4. Tests

Under the real investor account (`with_user` for the ORM; an HttpCase session for
JSON-RPC and URLs):
- refused models, a sample from every installed area (stock, product, equipment,
  maintenance, account, purchase, contract, `mail.message`, `ir.attachment`,
  `discuss.channel`, calendar, `res.groups`, `ir.actions.server`, `ir.actions.client`,
  access profiles): `search`, `read`, `search_read`, `read_group`, `web_search_read`,
  `export_data`, `create`, `write`, `unlink` all refused; the same through
  `/web/dataset/call_kw`, `/web/content/<attachment>`,
  `/web/image/product.product/<id>/image_128`, `/odoo/action-<other action>`;
- a model no rule of ours mentions is refused (default deny, not a list);
- actions (P4-2d), through the real HTTP routes:
  - `/web/action/load` by id, by external ID and by path of an action outside the
    whitelist (a staff window action, a hidden menu's action, a report): refused, no
    metadata returned; `/web/action/load_breadcrumbs` and `/odoo/action-<id>` the same;
    each whitelisted action loads;
  - `/web/action/run` and `ir.actions.server.run()` by RPC on a server action granted
    to `base.group_user`, on one without groups on `res.users` (a model the investor may
    write), and on the OCA start screen action: refused; a base automation triggered by
    an investor's allowed write still runs;
  - a home button of the investor screen re-pointed (as admin, in the test) to a
    foreign action, to a server action, or to the right action with another tag:
    refused to the investor; the 4 correct buttons run;
- `ir.ui.menu`: `load_menus` and a direct `search_read` return only the Stock Monitor
  tree;
- listed models: only the allowed records (own user, own and company partner, the
  investor screen and its 4 buttons), no write except own preferences;
- export: allowed on the monitor only; staff, accountant and personal fields refused;
- pages after restriction: home page (4 buttons; Financial opens the dashboard; coming
  soon notification in EN/FR/FA), dashboard (3 RPCs, figures), detailed analysis
  (list, pivot, graph), language switch, logout: tours and Python checks;
- staff unchanged: Inventory user and accountant keep their accesses and menus;
- P4-5: each forbidden group refused, Technical Features and the other implied groups
  accepted; the precheck lists offenders.
On the server after the update: the probe as `test_investor`, expected: monitor readable,
quick start screen and buttons read-only, every other model refused, root menu Stock
Monitor only.

## 5. P4-1. Third-party consumables (separate plan)

Independent of the security work. Step 1, characterisation on local Odoo 18 (no change
to our rules outside the test): standard handling of (a) the removal of a consigned
quant (inventory adjustment, return to the owner), (b) consigned goods becoming the
company's (purchase from the consignor: order, receipt, bill), with move lines, quants,
valuation layers and entries; report in `docs/phase4/CHARACTERISATION.md`. Step 2: a
separate plan for a controlled business action (reason, approval separated from
execution, history), our rule relaxed only inside it; accountant question C23. Quant
10 of TBER/Stock waits for it.

## 6. Order of work (one commit per step, after the go)

0. Done: server probe as `test_investor` (§1).
1. P4-1 step 1, characterisation (independent, report only).
2. Security and home page, developed in this order but **deployed as one atomic update**
   (audit of revision 4: the action checks use the external IDs of the screen and
   buttons, so their adoption cannot come later):
   a. P4-2a central default deny, with the minimal list;
   b. P4-5 constraint and blocking precheck;
   c. P4-2b record rules (menus included: P4-3) and P4-2d actions, each button checked
      against **its own** expected action (button external ID → action external ID,
      type, tag), not only against the whitelist;
   d. P4-0: screen, buttons, home window action and client actions as module data, the
      pre-migration adopting the script's records (external IDs bound before the
      checks need them), F1 rules, translations;
   e. P4-4 user setup and form warning;
   with the tests of §4.
3. README and server procedure (backup, precheck with forbidden groups, records to
   adopt and menu exclusions, `deploy_modules.sh`, post-check, probe again),
   DEFINITIONS.md (Access, home page), CLAUDE.md.
No partial deployment. Prerequisite: Q7 done (Purchase groups removed from
`test_investor`), checked by the precheck.

Implementation criteria (audit of revision 4): filter `/web/action/load` before the
standard controller runs; refuse `ir.actions.server.run()` before any `sudo()`; check
each button's exact action; test numeric ids, external IDs, paths and breadcrumbs.

## 7. Questions for the owner
All answered (Q1 to Q7, see the top). Q7 is done by the owner in Settings → Users before
the update; the precheck checks it.

## 8. Verified / not verified / hypotheses
- Verified: F1 (OCA ACL); F2, F3, F5 by the server probe as `test_investor`; F4 in
  `base_groups.xml`; `_get_allowed_models` is the single source of `check()`;
  `/web/action/load` reads in sudo without checking groups, `ir.actions.server.run()`
  loops on `self.sudo()` (revision 3 was wrong on both); `load_breadcrumbs` goes
  through `load` and `run`; `base_automation` runs actions from sudo;
  `_visible_menu_ids` searches menus as the user (a rule on `ir.ui.menu` applies).
- Not verified: the minimal list of models the web client needs with `mail` and the
  installed apps (built by the step 2 tests); whether other profiles use
  `base_menu_visibility_restriction`; whether `get_views` needs any `ir.ui.view` read for
  the quick start kanban.
- Hypotheses: the web client works with `mail.*` and `discuss.channel` refused (the
  mail init runs partly in sudo); to prove by the tours, otherwise the plan is revised
  before adding anything.

## 9. Implementation notes (10/10/2026), for the code audit

Developed as planned (§6 step 2, one commit for the security core, then precheck,
rehearsal, translations, docs). Additions and findings, each with its reason:
- **Web client minimum, found by the tours** (§8 hypothesis disproved: the mail init
  does not run in sudo). With the bare list, the investor's web client raised access
  errors from `/mail/data` (`discuss.channel`, `discuss.channel.member`,
  `mail.message`), the activity systray (`mail.activity`) and the views' favourite
  filters (`ir.filters`). These five models are readable (read only) with a rule
  returning **no record** for investor accounts: the searches come back empty, no
  data is visible, and the websocket subscription (`ir.websocket`, which searches the
  user's channels as the user) subscribes to no channel, so nothing posted in
  #general reaches an investor account. `ir.module.module` is also refused once per
  page load; Odoo catches it (no dialog, no RPC error): left refused.
- **Export of `id`**: `export_data(["id"])` reads nothing in standard Odoo (external IDs
  are built in sudo), so it escaped the default deny. For investor accounts
  `export_data` checks read access first (override on `base`). Found by the tests.
- **`res.users` not in the write list**: own preferences are written through the
  standard self-writeable fields (in sudo); `res.users.settings` is the only write.
- **Home button rule**: the investor buttons are those named in `INVESTOR_BUTTONS`
  (external IDs), not whatever the screen lists, so the rule does not depend on data an
  administrator may change.
- **Back to the home page**: the dashboard (client action, no control panel) shows a
  back link to the previous screen (« ← Investor Home »), with Odoo's `oi-arrow-left`,
  mirrored by Odoo in right-to-left languages.
- **Adoption of the script's records** (rehearsal finding): the old
  `setup_investor_home.py` wrote the translations so that the last one (Persian) could
  end up in the source value `en_US` (screen « خانه سرمایه‌گذار », buttons « مالی »…).
  Adopting by English name created duplicates; the pre-migration now finds each record
  by its name in any of the three languages, the precheck counts duplicates the same
  way, and the post-check lists every screen or button not bound to the module.
- **Exact action check proven**: a look-alike client action (same type and tag as the
  dashboard, another record) is refused only by the exact check; mutation tests:
  without the default deny, the `run()` refusal, the load filter, the export check or
  the exact button check, the tests fail.

Verified locally (Odoo 18, OCA heads, `web_quick_start_screen` c3120b0):
- tests of both modules (see README for the count), including the investor tours
  (dashboard and home page) without any access error;
- rehearsal on a database built with the deployed phase 3 code (70648a2), configured by
  the real `setup_investor_home.py`, with `test_investor` holding Purchase rights:
  precheck refusing `test_investor: Purchase / User, Purchase / Administrator`, then
  passing once removed; update; adoption of the 5 records (English names restored,
  French and Persian kept); post-check clean; probe as `test_investor`: only the
  monitor, home page, own user / partner / company, currencies, empty messages and
  channels; root menu Stock Monitor only; browser check: home page, Financial, back
  link, « coming soon », no RPC error.

Not verified (server): the state of the script's records on artdubati_test (the
precheck shows them); whether other users rely on `base_menu_visibility_restriction`
(listed by the precheck).

## Data cleaned after the phase 3 deployment (10/10/2026)
Bg/TEST Paris (id 21): its 40 « TEST Cement bag » moved to Bg/Stock by a standard
internal transfer (Bg/Stock now 46); « Outside Any Monitor Stock » alert gone; the
location archived.

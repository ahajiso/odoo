# Phase 4 – home page and investor user setup: plan (revision 2, 10/10/2026)

Scope (CLAUDE.md): investor home page, investor user setup, review of the existing
configuration, P4-1. **No code before the audit of this plan and the owner's go.**

Revision 2 answers the audit of revision 1 (10/10/2026): data perimeter as a whitelist
with a central default deny (point 1), every leak covered (point 2), cumulated rights
refused with a blocking precheck (point 3), security tested through the real investor
account and JSON-RPC / URLs (point 4), P4-1 reduced to a characterisation first and a
controlled business action, accountant question C23 (point 5). Owner's answers: Q1 A,
Q2 nothing outside the monitor but the demonstrated technical minimum, Q3 whitelist with
Discuss hidden, uninstall `base_menu_visibility_restriction` only once nothing else uses
it, Q4 cumulated rights refused.

Sources: `docs/investor_home/` (README, setup_investor_home.py), OCA sources of
`web_quick_start_screen` (OCA/web 18.0, c3120b0) and `base_menu_visibility_restriction`
(OCA/server-ux 18.0, 737262e), Odoo 18 `ir.model.access` (`_get_allowed_models`,
`check`), our `lartdubati_investor_home`, the probe `probe_investor.py`.

## 1. Findings

F1. **Every internal user may modify the home page**: `web_quick_start_screen` grants
`base.group_user` read and write on `quick.start.screen` and `quick.start.screen.action`.

F2. **An internal user's standard rights are far wider than the monitor.** Local probe,
investor without other groups: all quants, products with their cost (`standard_price`
is `groups="base.group_user"`), warehouses, the chart of accounts, maintenance requests
(read, write, create, delete), messages, attachments, channels.

F3. **Menus hidden by a blacklist**: Maintenance, Apps and any app installed later are
shown to investors.

F4. **Technical Features** (developer tools) is implied by Internal User on the local
database; to check on artdubati_test.

**Server probe of 10/10/2026: run with the wrong account.** Its « Groups » line has no
« Investor / Stock Monitor Investor » but has « Administration / Settings »,
« Administration / Access Rights », Inventory / Purchase / Sales / Invoicing
administrator, and it reads `lartdubati.stock.access` (reserved to Access Rights): it is
an administrator account (most likely `test@test.com`, used for the setup script just
before), not `test_investor`. The figures it shows (Purchase menus, 8 moves, 2 purchase
orders…) are an administrator's and do not describe `test_investor`. The probe now stops
when the account is not an investor; it must be run again with `test_investor`'s login
(step 0). The conclusions of the audit stand anyway: F2 is true for any internal user,
so the plan below does not depend on that run.

## 2. Security model for investors (P4-2, P4-5)

### Definitions
- **Investor account**: a user of the group « Stock Monitor Investor ». From phase 4 an
  investor account holds **only** that group, Internal User and the groups Odoo implies
  automatically for every internal user (`base.group_user.implied_ids`, e.g. Multi
  Currencies, Multiple Stock Locations); optionally « Access to export feature ».
  Anything else (Inventory, Accounting / Invoicing, Purchase, Sales, Maintenance,
  equipment groups, Settings, Access Rights, Technical Features given directly, SQL
  Request…) is **refused** (P4-5). There is no « investor with staff rights » any more,
  so no ambiguous rule.
- Staff keep their standard rights; nothing in this section applies to them.

### P4-2a. Central default deny (data whitelist)
Odoo checks every non-sudo access to a model through `ir.model.access.check()`, which
reads the set of models allowed to the user from `_get_allowed_models(mode)`
(ormcache per user and mode). Override (inheritance, no core patch): for an investor
account, the allowed set becomes `super() ∩ INVESTOR_MODELS[mode]`. Every model not
listed, including those of modules installed later, is refused to investors in every
mode, through the ORM, JSON-RPC, URLs (`/web/content`, `/web/image`, exports, reports),
whatever ACL another module adds. Sudo code (framework internals) is unaffected.

`INVESTOR_MODELS` starts empty and receives only what the investor's web client and
pages need, **each model justified and tested** (§4). Expected, to be confirmed by the
tests and the tours (a model refused that the client needs shows up as an access error
in the tour):
- read: `lartdubati.stock.monitor` (profile rule), `quick.start.screen`,
  `quick.start.screen.action` (home page), `res.users` (own record), `res.partner` (own
  partner and the company's), `res.company` (own company), `res.currency` (amounts),
  `res.lang` (language switch), `ir.ui.menu`, `ir.ui.view`, `ir.actions.*` (client
  loading; read only), `res.users.settings`, `ir.model`/`ir.model.fields` only if the
  views require them;
- write: `res.users` (own preferences: language, password, through the standard
  self-writeable fields only), `res.users.settings`;
- create / delete: none, unless a test shows the client needs one (e.g. the web
  client's own settings record), justified in the plan before being added.
Not listed, so refused: stock, products, equipment, maintenance, accounting, purchase,
sales, contracts, `mail.message`, `mail.activity`, `ir.attachment`, `discuss.channel`,
`calendar.event`, `lartdubati.stock.access`, everything else.

### P4-2b. Record rules on the whitelisted models
Global rules computed per user (pattern `stock_access_rule_domain`), TRUE for staff:
- `res.users`: the investor's own record only;
- `res.partner`: the investor's own partner and the company's partner only;
- `res.company`: the investor's companies (standard);
- `quick.start.screen` / `quick.start.screen.action`: read only, the « Investor Home »
  screen and its buttons;
- `lartdubati.stock.monitor`: unchanged (profile, multi-company).
The `stock.location` and `stock.move.line` rules of phases 2f and 3 stay for safety, but
are no longer what protects investors.

### P4-2c. Fields
Sensitive fields of whitelisted models stay protected by their `groups=` (monitor:
staff and accountant fields; `res.users`: groups, login history…). Tested by reading
them as the investor (§4).

### P4-5. Cumulated rights refused
- Constraint on `res.users` (create / write of groups): an investor account holding a
  group outside the allowed list raises an error naming the groups to remove. The
  allowed list is computed (investor group, Internal User, its implied groups, export),
  not hard-coded, so a setting that implies a group for every internal user does not
  break it.
- Precheck of the deployment, **blocking**: lists every investor account holding a
  forbidden group (and every investor without access profile, as information). The
  owner corrects each one in Settings → Users (nothing is removed automatically); the
  update runs only on an empty list. `test_investor` is expected in it if it holds
  Purchase or Technical Features directly.
- Technical Features: if, as locally, it is implied by Internal User for everyone
  (developer mode setting), it cannot be removed from investors alone; the menu
  whitelist (P4-3) and the data deny (P4-2a) make it harmless, and the owner decides
  whether to turn the global setting off (Q5).

## 3. Interface (P4-0, P4-3, P4-4)

### P4-0. Home page: OCA quick start screen, hardened and versioned (owner's Q1: A)
- F1: write / create / delete on `quick.start.screen` and `quick.start.screen.action`
  only for Settings (two group rules: FALSE for Internal User, TRUE for Settings; group
  rules are ORed). Investors are already limited to read by P4-2a.
- The screen, its 4 buttons, the « coming soon » server action and their EN/FR/FA texts
  become data of `lartdubati_investor_home` (external IDs, translations in the .po from
  `--i18n-export`), installed in production by the module update. The records the
  script created are adopted by a pre-migration (found by English name; it stops if a
  name matches zero or several records). New dependency: `web_quick_start_screen`.
- Financial points to the client action `lartdubati_investor_home.action_stock_monitor`
  directly (the quick start screen accepts `ir.actions.client` without a model check);
  the server action stays until phase 5.
- To test first: the buttons (`run_action`, an object button) run for a user without
  write access.

### P4-3. Menus by whitelist (owner's Q3)
For investor accounts, `ir.ui.menu._visible_menu_ids` keeps only the Stock Monitor menu
tree (and the quick start « Start » menu if used). Discuss, Calendar, Contacts,
Dashboards, Maintenance, Apps, « Manuel » and any future app disappear. Staff
unchanged. Menus only hide; access is P4-2. `base_menu_visibility_restriction`: the
precheck lists every menu with `excluded_group_ids` and the groups used; it is
uninstalled (owner) only if nothing but the four investor exclusions of the script uses
it.

### P4-4. Investor user setup without a script
- On create / write making a user an investor account: home screen « Investor Home »
  and home action « Quick Start Screen » set if empty; the migration does it for
  existing investors.
- Warning on the user form: investor without access profile (sees no stock).
- `setup_investor_home.py` retired once P4-0 is in the module; README: create the user,
  Internal User + investor group only, choose the profile.
- Manual (« Investor » tab): phase 5.

## 4. Tests (point 4 of the audit)

Under the real investor account (`with_user` for the ORM, an HttpCase session for
JSON-RPC and URLs):
- for a sample of refused models from every installed area (stock, product, equipment,
  maintenance, account, purchase, contract, mail, attachment, channel, calendar if
  installed, access profiles): `search`, `read`, `search_read`, `read_group`,
  `web_search_read`, `export_data`, `create`, `write`, `unlink` all refused; same
  through `/web/dataset/call_kw` (JSON-RPC), `/web/content/<attachment>`,
  `/web/image/product.product/<id>/image_128`, `/odoo/action-stock.action_picking_tree_all`;
- a model installed by no rule of ours (a test model or a standard one not listed) is
  refused: the deny is by default, not by list;
- whitelisted models: only the allowed records (own user, own and company partner),
  sensitive fields refused (`res.users.groups_id` of others, monitor staff fields,
  product cost not reachable at all);
- messages and attachments: none readable, none creatable (chatter, upload);
- writes: no create / write / unlink anywhere except the investor's own preferences;
- the pages still work: home page (4 buttons, Financial opens the dashboard), dashboard
  (3 RPCs, figures), detailed analysis (list, pivot, graph), language switch, logout:
  tours, plus Python checks of each RPC they make;
- staff unchanged: an Inventory user and an accountant keep their accesses;
- P4-5: the constraint refuses each forbidden group; the precheck lists them;
- P4-3: investor root menus = Stock Monitor (and Start); staff still see Inventory.
The probe (`probe_investor.py`) run again on artdubati_test after the update, as
`test_investor`, is the server-side evidence.

## 5. P4-1. Third-party consumables: characterise first, then a controlled action

Revision 1 proposed to relax `_check_third_party_owner` for an inventory adjustment and
for an internal transfer « assigning » the company as owner. The audit is right: in
Odoo the owner of a move line is the owner of the goods both at the source and at the
destination, so a transfer on the same location does not change the quant's owner and
produces no valuation; and a third party's goods becoming the company's is an
accounting event (purchase from the consignor or other), not a stock correction.

Step 1, characterisation (local Odoo 18, no change to our rules except in the test):
how the standard handles (a) the removal of a consigned quant (inventory adjustment,
return to the owner by a delivery), (b) the consigned goods becoming the company's (the
standard consignment flow: purchase order to the consignor and receipt / bill; what
happens to the consigned quant and its valuation), with the move lines, quants,
valuation layers and entries of each; written in `docs/phase4/CHARACTERISATION.md`.

Step 2, proposal from the results (plan revision, owner, then accountant C23): a
business action in `equipment.operation` style (reason required, approval separated
from execution, chatter history), allowing only the case characterised, our rule
relaxed only inside that action (`running` context as for receipts). Quant 10 of
TBER/Stock is handled with it after deployment.

## 6. Order of work (one commit per step, after the go)

0. Probe again as `test_investor` (read-only, owner) → F4 and the real current
   perimeter; investors holding forbidden groups listed.
1. P4-1 step 1 (characterisation), report, then P4-1 step 2 is planned separately.
2. P4-2a default deny + P4-2b rules + P4-5 constraint, with the tests of §4 (the
   whitelist built from the failing tours, each addition justified in this plan).
3. P4-3 menu whitelist.
4. P4-0 home page as module data, F1 rules, pre-migration.
5. P4-4 user setup.
6. Translations, precheck (forbidden groups, profiles, menu exclusions, quick start
   records to adopt), README and server procedure, DEFINITIONS.md (Access, home page),
   CLAUDE.md.

## 7. Questions for the owner

- Q5. Technical Features: is it implied for every internal user on artdubati_test
  (Settings → developer mode / « Technical Features » group)? If so, keep it or turn it
  off globally?
- Q6. « Access to export feature » for investors: allowed (exports stay limited to the
  monitor fields they may read) or refused?

## 8. Verified / not verified / hypotheses

- Verified: F1 in the OCA source; F2, F3 by the local probe; F4 locally; Odoo 18
  `_get_allowed_models` is the single source of the model set for `check()` (cached per
  uid and mode, cleared when groups change).
- Not verified: the server probe as `test_investor` (the one run was an administrator);
  the exact minimum list of models the investor's web client needs with `mail` and the
  installed apps (built by the tests of step 2); whether other profiles use
  `base_menu_visibility_restriction`.
- Hypotheses: the web client works for a user refused `mail.*` and `discuss.channel`
  through ACL (the mail init runs partly in sudo; to prove by the tours); the quick
  start buttons run for a read-only user.

## Data cleaned after the phase 3 deployment (10/10/2026)
Bg/TEST Paris (id 21): its 40 « TEST Cement bag » moved to Bg/Stock by a standard
internal transfer (Bg/Stock now 46); « Outside Any Monitor Stock » alert gone; the
location archived.

# Phase 4 – HTTP routes and investor accounts (P4-2f)

Audit of 6063db1: some authenticated routes resolve models, actions or reports on their
own, sometimes in sudo, without going through `/web/dataset/call_kw` or
`/web/action/load`. Examples: `/web/model/get_definitions` (fields of any model),
`/json` and `/json/1` (resolve an action, then `get_view`, `web_read`, `search_read`),
and `/report/*` (the report is looked up in sudo). Since the model and method whitelist
does not cover them, investor accounts get **a whitelist of routes**.

## Rule (`ir.http._pre_dispatch`, `models/investor_security.py`)

For an investor account, every route with `auth="user"` or `auth="bearer"` is refused
**before its controller runs**, unless it is in `INVESTOR_ROUTES`. The refusal raises
an AccessError: 403 for an HTTP route, an error for a JSON route. The server log gets a
line « Investor route refused: <route>, uid <id> ».

This also covers every route a module installed later will add: until it is listed,
it is refused.

Allowed routes (16), each one needed by the investor's pages (tours and interface
checks) and protected by its own check:

| Route | Why | Check behind it |
|---|---|---|
| `/web/webclient/load_menus/<string:unique>` | menus | rule on `ir.ui.menu` (monitor tree) |
| `/web/session/get_session_info`, `/web/session/check` | web client session | own session only |
| `/web/action/load`, `/web/action/load_breadcrumbs` | home page, dashboard, analysis | action whitelist (P4-2d) |
| `/web/dataset/call_kw[/<path>]`, `/web/dataset/call_button[/<path>]` | every RPC of the pages | `INVESTOR_METHODS` (P4-2e) and default deny |
| `/web/domain/validate` | custom filter of the analysis views | `search_count` as the user (default deny) |
| `/web/export/formats`, `get_fields`, `namelist`, `csv`, `xlsx` | export of the monitor (Q6) | model check (P4-2e), read check |
| `/web/pivot/export_xlsx` | download of the analysis pivot | nothing read: the client sends the table it shows |

The routes the audit named are refused, and tested (`TestInvestorRoutes`):
`/web/model/get_definitions`, `/bus/get_model_definitions` (same exposure), `/json`,
`/json/1` (session or API key), `/report/<converter>/<report>[/<ids>]`,
`/report/download`, `/stock/<format>/<report>`, plus `/my`, `/my/invoices`,
`/account/download_invoice_documents`, `/web/become`, `/web/session/account`,
`/web/session/modules`, `/web/view/edit_custom`, `/web/action/run`,
`/mail/inbox/messages` and `/mail/thread/messages`.

What is not available to an investor, since it needs a refused route: the « My Odoo.com
account » entry of the user menu (`/web/session/account`), and Discuss (hidden since Q3).

## Public routes for an investor session (P4-2g, audit of 2071e6e)

A public route (`auth="public"`) runs as the logged-in user when there is a session, so
it can behave differently than for an anonymous visitor: branches for internal users,
`sudo()`. For an **investor session**, every public route is therefore refused before
its controller unless it is in `INVESTOR_PUBLIC_ROUTES`: 11 routes, the ones the tours
use, plus `/web/bundle`, which lists a lazy bundle's asset files. Anonymous requests are
**not** filtered: the login page, the assets before login and token links work as
before.

| Route | Why | What it gives an investor session |
|---|---|---|
| `/web/assets/...`, `/web/bundle/...`, `/web/webclient/translations/...` | the web client's code, styles and translations | the same files as for anyone |
| `/web/manifest.webmanifest`, `/web/service-worker.js`, `/odoo/offline` | installable web app (the page loads them) | static content |
| `/web/image`, `/web/image/<model>/<id>/<field>` | avatars (own, company) | read access checked as the user: default deny and the rules; other records give the placeholder (tested) |
| `/bus/websocket_worker_bundle`, `/websocket` | real-time bus | only its own partner, its own presence and `broadcast`: Odoo's subscription to the **group channels** is removed for investor accounts (`ir.websocket`), otherwise an investor would receive what is sent to every internal user (channels auto-subscribing Internal User, shared canned responses); a discussion channel asked for by the client is not subscribed (rule: none) |
| `/mail/data` | mail client init (every page) | own counters only: no channel, message, partner or activity (tested with every option; canned responses refused by the default deny) |

Found while doing it:
- the websocket of an investor account could not subscribe at all: the subscription
  searches `mail.guest`, then the presence update writes `bus.presence`, both as the
  user, and both were refused by the default deny. That left an error in the log on
  every page. `mail.guest` is now readable with no record (rule: none), and
  `bus.presence` readable and writable for the account's own record only (rule: own);
- refused and tested for an investor session: `/mail/action`, `/mail/thread/data`,
  `/mail/message/post`, `update_content` (edit, delete), `reaction`,
  `/mail/attachment/upload`, `zip`, `delete`, `/mail/link_preview`,
  `/mail/message/<id>`, `/discuss/channel/<id>`, `messages`, `info`, `join`,
  `members`, `/websocket/peek_notifications`, `/web/content/...` (even for a public
  attachment, readable anonymously) and the sized `/web/image/.../<w>x<h>`. Nothing is
  created, changed or deleted;
- mutation check: without the public whitelist or without the websocket filter,
  13 checks fail.

## Inventory (rehearsal database with the modules of artdubati_test, 10/10/2026)

`docs/phase4/routes.py` (read-only, Odoo shell) lists every route of the installed
modules with its status for an investor session:

| auth | allowed | refused | total |
|---|---|---|---|
| user / bearer | 16 | 102 | 118 |
| public | 11 | 109 | 120 |
| none (no user environment: `/web`, `/odoo`, login, `/xmlrpc`, `/jsonrpc`, database manager) | – | – | 44 |

The external API (`/xmlrpc`, `/jsonrpc`) is refused to investor accounts (P4-2e).

## Project rule (CLAUDE.md)

Every installation or update of a module comes with the inventory of its HTTP routes
(`routes.py`, compared with the previous output):
- a new route, authenticated or public, stays refused to investor sessions; listing it
  in `INVESTOR_ROUTES` or `INVESTOR_PUBLIC_ROUTES` requires a reason and a test as an
  investor account;
- a new public route is read anyway: whatever it does for anonymous visitors is open to
  everyone.

Every future investor screen explicitly requires its action (`INVESTOR_ACTIONS`), its
models (`INVESTOR_MODELS`), its methods (`INVESTOR_METHODS`), its routes
(`INVESTOR_ROUTES`), its menu, its fields and dedicated tests.

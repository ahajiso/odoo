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

## Inventory (rehearsal database with the modules of artdubati_test, 10/10/2026)

`docs/phase4/routes.py` (read-only, Odoo shell) lists every route of the installed
modules with its status:
- authenticated routes: 118, of which **16 allowed** and **102 refused**. The refused
  ones, by module: html_editor 19, web 18, mail 16, web_editor 7, portal 7, account 6,
  purchase 4, product 4, web_unsplash 3, report_xlsx(_helper) 3, payment 2,
  contract 2, then 1 each for stock, spreadsheet(_dashboard), digest, bus, board,
  base_setup, base_import, auth_signup, google_gmail, ours;
- public routes (`auth="public"`): 164, **not filtered**. Anyone can reach them without
  logging in. For a logged-in investor they run as that account, so the default deny and
  the rules apply to every ORM access. Tested: `/web/content/<attachment>` and
  `/web/image/<model>/<id>/<field>` give nothing. The leftover risk is a public route that
  works in sudo **because** the user is logged in. That is why the rule below asks for
  every new public route to be read.
- `auth="none"` routes (`/web`, `/odoo`, `/xmlrpc`, `/jsonrpc`, login) have no user
  environment; the external API is refused to investors (P4-2e).

Why public routes are not filtered as well: the login page, the assets, the websocket
and `/mail/data` are public routes. Filtering them would put the whole web client at
the mercy of an incomplete list, for little gain, because anyone can already reach these
routes anonymously. The owner can decide otherwise; the cost is the list of the public
routes the pages use, found the same way as the 16 above (the tours, then the interface
checks).

## Project rule (CLAUDE.md)

Every installation or update of a module comes with the inventory of its HTTP routes
(`routes.py`, compared with the previous output):
- a new authenticated route stays refused to investor accounts; listing it in
  `INVESTOR_ROUTES` requires a reason and a test as an investor account;
- a new public route is read. If it reads a model, an action or a report, or runs a
  method in sudo, it is tested as an investor account.

Every future investor screen explicitly requires its action (`INVESTOR_ACTIONS`), its
models (`INVESTOR_MODELS`), its methods (`INVESTOR_METHODS`), its routes
(`INVESTOR_ROUTES`), its menu, its fields and dedicated tests.

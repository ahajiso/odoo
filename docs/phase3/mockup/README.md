# Stock monitor mock-up (phase 3)

Throwaway Odoo 18 module `lartdubati_stock_monitor_mockup`: static demo data in
JavaScript, no model, no server call. It shows the ergonomics, navigation and
information density of the dashboard described in `docs/phase3/PLAN.md` (section 4).
It is never installed on a server and is deleted once the real dashboard is merged.
It sits under `docs/`, so the server's addons path (the repo root) does not see it.

What is **not** representative:
- rows are filtered, sorted and summed in JavaScript because there is no server; the
  real dashboard pages the list with `web_search_read` and sums with `read_group`
  (plan, section 4.3);
- the « Maquette » switches (view as Investisseur / Magasin / Comptable, simulate
  loading / empty / RPC error) do not exist in the module: what a user sees comes from
  their groups, record rules and the real state of the calls;
- texts are French only; amounts use `Intl` (the module uses Odoo's formatting).

## Screenshots (`screenshots/`, local Odoo 18, 09/10/2026)
| File | Shows |
|---|---|
| 01 | Accountant, all stocks: stock cards, the three values, rents, alerts, staff controls |
| 02 | Stock selection: searchable list grouped by country · city |
| 03 | Bg/Stock selected, rented item: detail panel |
| 04 | Missing USD rate: amount kept in USD, excluded from totals, alert filter active |
| 05, 06 | Investor: inventory value only, no owner, no rent, no outside-stock card |
| 07 | Store user, filter « Loué »: weekly rent without monthly equivalent |
| 08 | Tablet 1024 px: panel over the list |
| 09 | Tablet 768 px portrait: wrapped filters, stock column hidden |
| 10 | Search and sort (descending inventory value) |
| 11 | Draft asset: provisional net book value |
| 12 | Serial number in two locations: one row, integrity alert |
| 13a, 13b | Keyboard: Tab to a row, Enter opens (focus on « Fermer »), Escape closes and the focus returns to the row |
| 14, 15, 16 | Loading, no result (profile without stock), RPC error with « Réessayer » |
| 17, 18 | fa_IR (RTL): mirrored layout, amounts isolated (`<bdi>`) |

## Run it locally
Add `docs/phase3/mockup` to the addons path of a local Odoo 18, install
`lartdubati_stock_monitor_mockup`, open the « Stock Monitor » menu. RTL needs the
`rtlcss` command (`npm install -g rtlcss`); without it Odoo serves the RTL bundle
unmirrored and logs a warning.

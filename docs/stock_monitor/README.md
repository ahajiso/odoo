# Stock monitor (OCA bi_sql_editor reports)

The stock monitor is not code: it is two reports of the OCA module `bi_sql_editor`
(OCA/reporting-engine 18.0), configured in **Dashboards > Configuration > SQL Views**.
This folder keeps their configuration so they can be recreated (e.g. on production).
Definitions: `docs/DEFINITIONS.md`. Decisions: `CLAUDE.md`.

## Prerequisites (installed modules)
`bi_sql_editor`, `contract`, `maintenance_equipment_contract`, `maintenance_account`,
`account_asset_management`, `lartdubati_investor_home` (access profiles, place type,
`user.stock_access_rule_domain('monitor')`).

## The two reports
| Name | Technical name | Query | Groups |
|---|---|---|---|
| Stock Monitor | `stock_monitor` | `stock_monitor_investor.sql` | `lartdubati_investor_home.group_stock_investor`, `stock.group_stock_user`, `account.group_account_readonly` |
| Stock Monitor - Values & Rent | `stock_monitor_full` | `stock_monitor.sql` | `account.group_account_readonly`, `stock.group_stock_manager` |

`stock_monitor_investor.sql` is `stock_monitor.sql` without the columns
`x_accounting_value`, `x_rent_month`, `x_rent_paid` (bi_sql_editor cannot hide a
column per group, hence two reports). Change both files together.

Settings for both:
- **Is Materialized View: unchecked** (the default is checked; a materialized view only
  refreshes on a schedule, the monitor must be live).
- Domain: `user.stock_access_rule_domain('monitor')` (global rule: investors only see
  what their Stock Access Profile allows; other users are not restricted).
- Parent menu: `spreadsheet_dashboard.spreadsheet_dashboard_menu_root` (Dashboards).
- View order: `pivot,list,graph`. Action context: `{'group_by': ['x_currency_id']}`.

Field mapping (after "Validate SQL Expression"):
- Selection fields:
  - `x_family`: `[('asset', 'Asset'), ('consumable', 'Consumable')]`
  - `x_ownership`: `[('owned', 'Owned'), ('borrowed', 'Borrowed'), ('rented', 'Rented'), ('lent_out', 'Lent Out')]`
  - `x_place_type`: `[('physical', 'Physical'), ('lent_out', 'Lent Out'), ('virtual', 'Virtual')]`
- Labels: `x_location_id` Stock, `x_item` Item, `x_rent_month` Rent per Month,
  `x_rent_paid` Rent Paid to Date (others: proposed label).
- Group by: family, ownership, location, warehouse, place type, country, state, city,
  currency, product.
- Pivot: row `x_location_id`, column `x_family`; measures (sum) quantity, inventory value,
  accounting value, rent per month, rent paid.
- List: warehouse, place type, state, city, product "Optional (hidden)"; others shown.

Then "Create SQL View and Model", then "Create UI".

## Business choices written in the query (edit the query to change them)
- Replacement price of borrowed/rented consumables: product cost (`third_value` in the
  `consumable` part). bi_sql_editor forbids reading system parameters, so this choice
  is a line of the query.
- Currency: latest rate into the currency of the stock's country (warehouse address),
  company currency when that currency has no rate. To be confirmed by the accountant.
- Rent: supplier contracts (OCA contract, type Supplier), lines with a manual price
  (specific price); converted to a monthly amount; paid = posted vendor bills of the
  contract lines. A contract linked to several equipment is split equally between them;
  consumable rent is split between stocks by quantity.
- Accounting value of an asset: the fixed asset of the vendor bill line the equipment was
  created from (OCA maintenance_account); empty (0) when there is none.

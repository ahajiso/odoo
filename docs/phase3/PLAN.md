# Phase 3 plan – stock monitor on revision 2

Status: revision 1, proposal for the audit (09/10/2026). No code written.
Scope: `maintenance_shareholder_equipment` 18.0.4.0.0 (stock attributes, removal of the
obsolete fields) and `lartdubati_investor_home` 18.0.2.0.0 (monitor, access). Builds on
phases 1 and 2. Home page: phase 4 (only its Financial button is repointed here).
Manual: phase 5.

Owner's input (09/10/2026): « Je n'ai pas grand chose à garder du monitor actuel. Il
n'est pas assez intuitif. » The current bi_sql_editor reports are therefore replaced,
not ported (section 2), and the screens are validated by the owner on screenshots
before the rest is coded (section 9, step 1).

## 0. Facts checked in the code

- The current monitor (docs/stock_monitor/) is two bi_sql_editor reports, built on the
  04/10 decisions:
  - it reads `acquisition_mode` and `owner_type`, and the rent through
    `contract_contract_maintenance_equipment_rel`, split equally;
  - it places assets through `current_location_id`, which is wrong for serial-tracked
    equipment;
  - it reads the country from `warehouse_id.partner_id`, which is empty for Bg/Stock;
  - it uses the currency of the country, not the stock's.
  Nothing in its SQL survives revision 2.
- `stock.location.place_type` is required with default `physical`
  (maintenance_shareholder_equipment/models/stock.py:11), so every location has one.
  « A stock is a location whose place type is set » (DEFINITIONS) is therefore true of
  every location. The phase 1 plan (§10) left « the change of meaning of
  `place_type` (only on monitor stocks) » to phase 3.
- No stock currency field exists yet (phase 1 §10 postponed it).
- OCA `stock_location_address`:
  - `address_id` is stored;
  - `real_address_id` (inherited from the parents) is computed and not stored, so it
    cannot be used in SQL. DEFINITIONS already says that the monitor uses the stored
    address of the stock itself.
- `lartdubati.stock.access._location_domain` filters the country through
  `warehouse_id.partner_id.country_id` (stock_access.py), which is empty for Bg/Stock.
- OCA account.asset stores `purchase_value`, `value_depreciated` and `value_residual`
  (account_asset.py:54-83). The depreciated value counts the posted depreciation lines.
- OCA contract:
  - contract lines carry `date_start`, `date_end`, `recurring_rule_type`,
    `recurring_interval`, `price_unit`, `quantity` and `active`;
  - the contract has `contract_type` (sale / purchase) and `currency_id`.
- In Odoo 18, `stock.quant.value` is not stored. The AVCO unit cost is the
  company-dependent `product_product.standard_price` (jsonb keyed by company).
- Removing a field makes Odoo drop its column with CASCADE, so every SQL view reading
  it is dropped too (phase 1 characterisation). The two bi_sql_editor views read
  `owner_type` and `acquisition_mode`, so they must be removed before those fields.
- The investor home page's Financial button opens the bi_sql_editor action, whose id
  changes whenever the report is rebuilt (docs/investor_home/README.md).

## 1. Decisions proposed (owner)

| # | Question | Proposal |
|---|---|---|
| P1 | Monitor technology: bi_sql_editor reports or a module model on a SQL view? | **Module model** (`_auto = False`): field-level `groups=` (one report instead of two), real field names in the access rules, stable action XML id for the home page, versioned and tested code, and its own screens (section 4). bi_sql_editor gives none of these. |
| P2 | What makes a location a stock? | A new boolean **`is_monitor_stock`** (« Stock (monitor) ») on stock.location, rather than an optional `place_type`. Emptying `place_type` would touch the phase 2 rules that read it (lent_out, virtual) and every existing location. A monitor stock requires an address and a currency. |
| P3 | Items in an internal location with no monitor stock above it? | Shown to non-investors with stock « (outside any monitor stock) », as a control; never shown to investors (the access rule requires a stock). |
| P4 | May investors see the legal owner of borrowed / rented items (`owner_partner_id`)? | **No** by default: shown to stock users and accountants only. Investors see the status. |
| P5 | Keep bi_sql_editor installed? | Remove the two reports. Uninstalling the module is the owner's choice (it may be used elsewhere); the plan does not need it. |
| P6 | Screens (section 4): standard views or a custom dashboard? | **Standard views first** (A), validated on screenshots; the custom dashboard (B) only if A is still not intuitive. |

## 2. Data model changes

### 2.1 maintenance_shareholder_equipment (18.0.4.0.0)
- stock.location:
  - `is_monitor_stock` (boolean, tracked). Not on non-internal locations.
  - `monitor_currency_id`: many2one res.currency, default the company currency.
  - Constraint: an active monitor stock has an `address_id` and a currency.
  - Constraint: a `lent_out` location is a monitor stock. The receipts and exits of
    phase 2 create off-site stocks with an address; they set the flag too.
- maintenance.equipment: remove `owner_type` and `acquisition_mode` (and their
  translations). This is safe only after the reports are removed (section 8 order;
  checked by the rehearsal).
- No change to any column read by the monitor view (phase 1 rule: a type change drops
  views).

### 2.2 lartdubati_investor_home (18.0.2.0.0)
- New model `lartdubati.stock.monitor` (SQL view, read only), section 3.
- `_location_domain`: the country comes from `address_id.country_id`. The stock itself
  carries the address (P2), and allowed sub-locations stay allowed through `child_of`.
- `_monitor_domain`: real field names (`family`, `ownership_status`, `stock_id
  child_of`, `country_id`).
- res.company:
  - `stock_monitor_replacement_price` is removed: it is moot, since consumables are
    owned only;
  - `stock_monitor_currency_mode` is kept (C12).
- Global rule on `lartdubati.stock.monitor`:
  `user.stock_access_rule_domain('monitor')`.
- The existing location rule is kept.
- Depends on `contract` (already installed through module 1).
- `maintenance_equipment_contract` is no longer used: it is uninstalled on the server
  (section 8), and nothing in the repo depends on it (to be checked by grep before
  the commit).

## 3. The view `lartdubati.stock.monitor`

### 3.1 Grain and stable ids
- One row per integrated asset: `integration_state = done`, active.
  Id = `equipment.id * 2`.
- One row per consumable quant: internal location, quantity ≠ 0, product without
  equipment (`maintenance_ok` false). Id = `quant.id * 2 + 1`.

Rows have stable ids, so a row form can be opened and reloaded.

### 3.2 Location
- Stock-managed asset: the location of the positive internal quant of its
  `stock_lot_id`.
- Non-stock asset: its `current_location_id`.
- `stock_id` is the nearest location at or above that location with
  `is_monitor_stock`, matched on the `parent_path` prefix (longest wins). It is never
  found through `warehouse_id`.
- `location_id` is the exact location.
- Geography comes from `stock_id.address_id`: country, state, city.

### 3.3 Columns (field label, groups)

| Field | Content | Visible to |
|---|---|---|
| company, stock, location, place type, country, state, city, currency (stock currency) | as above | all |
| family | asset / consumable | all |
| ownership_status | equipment status; consumables `owned` | all |
| owner_partner_id | legal owner | stock users, accountants (P4) |
| product, category, equipment name, serial number | | all |
| warranty / insurance status | equipment | all |
| asset_count | 1 per asset row | all |
| quantity, uom | 1 for an asset; quant quantity for a consumable, not summed across products (`aggregator=None`, units differ) | all |
| inventory_value | owned / lent_out: asset `purchase_value`, otherwise the stock unit cost of the product (C19); borrowed / rented: replacement value. Consumables: quantity × AVCO. | all |
| replacement_value, its date | equipment | all |
| original_value, depreciated_value, accounting_value (NBV) | owned / lent_out only. Assets: asset `purchase_value`, `value_depreciated`, `value_residual`; without an asset, stock value as for the inventory value. Fixed-asset categories count 0 in stock value. Consumables: quantity × AVCO. Borrowed / rented: 0. | accountants (`account.group_account_readonly`) |
| rent_amount, rent_period, rent_start | active rental line (`equipment_nature = rental`, supplier contract, not cancelled, active, today within [start, end]) | stock users, accountants |
| rent_paid | posted supplier bill lines minus refunds, on all rental lines of the equipment (by `contract_line_id`), company currency converted | accountants |

### 3.4 Aggregation rule

Contract data is joined through a subquery aggregated per equipment, so there is one
row per equipment even when it has several lines or renewals. The current rent comes
from the single active line, which is unique because of the overlap constraint of
phase 1.

### 3.5 Currency
- Every amount is converted from its source currency into the stock's currency, as set
  by `stock_monitor_currency_mode`:
  - source currencies: company currency for assets, AVCO and bills; contract currency
    for the rent; replacement currency for the replacement value;
  - `latest`: last rate;
  - `entry_date`: rate on the acquisition date (asset start date, or the quant's
    in_date);
  - `none`: no conversion, and then the row's currency is the company currency.
- A missing rate keeps the company currency on that row, without a silent mix.
- Totals are only meaningful within one currency. The default grouping starts with the
  currency whenever more than one currency is present (section 4).

## 4. Screens (to validate by the owner on screenshots, step 1)

Option A, standard Odoo views, no JavaScript. Top menu « Stock Monitor » (own app
icon), one action:

1. Default view: a list grouped by stock. The collapsed group rows show the totals per
   stock: assets, inventory value, and, by group, accounting value, rent. Opening a
   stock lists its items.
2. Left search panel (`searchpanel`), with counts:
   - Country, then City;
   - Stock (hierarchy);
   - Family (Assets / Consumables);
   - Ownership (Owned / Borrowed / Rented / Lent out).
   One click filters. Choosing a stock is a click in the panel or typing its name in
   the search bar, which replaces the combo box of the brief.
3. Pivot (stock × family, stock × ownership) and graph as secondary views.
4. Row form: one sheet per item with sections Identity, Location, Ownership, Values,
   Rent. The fields are read-only. Links are not clickable for investors
   (`no_open`), so they never open models they have no right on.

Option B, only if A is refused: a custom OWL dashboard. It has a top bar (stock combo
box, country / city, family toggle, ownership chips) and one card per stock with its
totals, and opens the same list.
- The data still come through the ORM, with the same rules and no sudo.
- Cost: JavaScript, its tests and its translations to maintain at each Odoo version.

Question to the owner, to guide the prototype: what is not intuitive today (finding a
stock, filters, too many columns, pivot)?

## 5. Access
- `ir.model.access` read on the monitor for the groups investor, `stock.group_stock_user`
  and `account.group_account_readonly`. No write right for anyone (`_auto = False`).
- Global rule on the monitor, and the location rule corrected (section 2.2).
- Navigation from the monitor never uses sudo. Many2one labels are read by Odoo's
  standard display. Investors open only the monitor's own form.
- The column groups of section 3.3 are enforced by `groups=` on the fields: hidden in
  the views, and refused when read through RPC.

## 6. Settings and data script (`docs/phase3/setup_phase3.py`, JSON-RPC)
Dry run by default, `--apply` on artdubati_test only. It:
- lists the internal locations with their place type, address and stock quantity;
- proposes the monitor stocks:
  - the warehouses' stock locations (Bg/Stock, which takes the warehouse partner as
    address if it has none);
  - the `lent_out` locations;
  - nothing else;
- refuses `--apply` if a proposed stock has no address it can set;
- sets the currency to the company currency;
- lists the internal quants outside any monitor stock (P3);
- lists the active equipment still `draft` (not in the monitor);
- lists the orphan serial numbers (maintainable products in stock without equipment);
- repoints the home page's Financial button to the new action, found by its XML id
  and shown before writing.

## 7. Tests (TransactionCase, both modules)
- One row per case, with the expected values:
  - owned asset with an asset (inventory value = purchase value, NBV = residual);
  - fixed-asset category (stock value 0, NBV from the asset);
  - asset without account.asset;
  - borrowed (replacement value, accounting value 0);
  - rented (rent of the active line, period, start; rent paid = bills minus refund);
  - lent_out in an off-site stock;
  - non-stock asset (`current_location_id`);
  - consumable at AVCO;
  - draft equipment and archived equipment absent.
- One row per equipment with two rental lines (renewal through
  `contract_line_successor`) and an insurance line.
- Stock resolution:
  - nearest monitor stock for a sub-location;
  - a stock outside its warehouse root, like Bg/Stock, gets its country from its own
    address;
  - an item outside any stock shows as P3.
- Currency: stock in another currency at the latest rate, mode `none`, and a missing
  rate.
- Access:
  - each profile dimension on the monitor (country, stock, status, family);
  - a user without a profile sees nothing;
  - non-investors are not restricted;
  - the location rule by address country (the existing 5 tests updated);
  - an investor reading `accounting_value` or `owner_partner_id` through RPC gets an
    AccessError.
- Constraints: a monitor stock without an address is refused; so is a lent_out location
  that is not a monitor stock.
- Regression: the 98 tests of phases 1-2 still pass.

## 8. Server procedure (docs/phase3/README.md, run by the owner)

0. Backup (as in phase 2). Read-only checks:
   - rows of `contract_contract_maintenance_equipment_rel`;
   - views depending on `maintenance_equipment.owner_type` / `acquisition_mode`
     (`pg_depend`).
1. Remove the two bi_sql_editor reports (Dashboards → Configuration → SQL Views →
   « Set to Draft », then delete). Note the home button's action first.
2. Uninstall `maintenance_equipment_contract` (Apps), once step 0 shows no data to
   keep, or after exporting it.
3. `git pull`, then `bash docs/deploy_modules.sh <dump> <count> phase3`.
4. `setup_phase3.py` dry run, then `--apply`.
5. Interface checks with the test investor user (Playwright, password never stored):
   - totals per stock;
   - filters;
   - hidden columns;
   - no access outside the profile.

Rehearsed first on the local `mig` database, a copy with the old monitor views.

## 9. Order of work (small commits)
1. Prototype of the screens (section 4, A) on the local database with sample data,
   with screenshots sent to the owner. Nothing else is coded before their answer.
2. stock.location fields and constraints, with tests.
3. SQL view and model, with the tests of section 7.
4. Access: rules, groups and the location domain, with tests.
5. Removal of the obsolete fields and setting, migration rehearsal.
6. Setup script, README, translations (fr, fa, exported), CLAUDE.md and DEFINITIONS.md
   (« Stock », « Measures », « Access »), QUESTIONS_COMPTABLE.md.

## 10. Verified / not verified / hypotheses
- Verified in the code: the facts of section 0.
- Not verified (server):
  - the content of `contract_contract_maintenance_equipment_rel`;
  - other SQL views depending on the obsolete columns;
  - the addresses of the existing internal locations;
  - whether bi_sql_editor is used for anything else.
- Hypotheses to check in step 1 or 3:
  - Odoo 18 list group rows sum monetary fields per group, and the screen stays
    readable with one currency per stock;
  - `searchpanel` on an `_auto = False` model with many2one hierarchy (stock);
  - `contract.contract.currency_id` is stored (it is computed);
  - the performance of the `parent_path` match is enough (a few hundred rows today).

## 11. Accountant (docs/QUESTIONS_COMPTABLE.md)
- C12 updated: conversion into the stock's own currency (field on the stock), no longer
  the country's.
- C19 (new): inventory and accounting value of a stock-managed equipment outside the
  fixed-asset categories (no account.asset). Test choice: product unit cost (AVCO) at
  the time of the monitor. Where to change: product category (costing method), or move
  the category to the fixed assets.

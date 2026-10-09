# Phase 3 plan – stock monitor on revision 2

Status: revision 5 (09/10/2026), developed on the branch (section 11), audit pending.
- The audit of revision 4 accepted P9, P10, P13 and D6, validated the visual
  direction (no new mock-up needed) and asked for five corrections, answered in
  section 1c and in docs/phase2f/PLAN.md revision 3.
- The audit of revision 3 validated the mock-up's visual direction and the answers to
  the eight blockers. It asked for four corrections and five complements, answered in
  section 1b.
- Once they are integrated: green light for phase 2f, then a new audit of its code
  before deployment. Phase 3 starts afterwards, in the planned order.
- Revision 1 was audited by ChatGPT: eight blocking corrections.
- Revision 2 recorded the owner's choice of an OWL dashboard and a first mock-up. Its
  audit was validated in principle, with the eight corrections still due, plus
  requests 9-15.
- This revision answers every point (section 1), plans the corrective phase 2f
  (`docs/phase2f/PLAN.md`) and iterates the mock-up (`docs/phase3/mockup/`,
  19 screenshots).

Scope:
- `maintenance_shareholder_equipment` 18.0.4.0.0: stock attributes, contract currency,
  removal of the obsolete fields (the equipment cost, its date and its provisional
  flag come from phase 2f);
- `lartdubati_investor_home` 18.0.2.0.0: monitor, dashboard, access.

It builds on phases 1, 2 and 2f. Home page: phase 4 (only its Financial button is
repointed here). Manual: phase 5.

Owner's input (09/10/2026):
- « Je n'ai pas grand chose à garder du monitor actuel. Il n'est pas assez intuitif. »
  The bi_sql_editor reports are replaced, not ported.
- « Je choisis finalement un tableau de bord OWL moderne comme interface principale du
  moniteur [...] esthétique, intuitive et responsive, tout en restant fonctionnellement
  irréprochable. Les vues Odoo standard doivent rester disponibles comme interface
  secondaire [...]. Le tableau de bord doit utiliser le même modèle SQL, passer
  exclusivement par l'ORM, sans sudo, et respecter strictement les règles d'accès et les
  restrictions de champs. »

## 0. Facts checked in the code

Current monitor and stocks:
- The current monitor (docs/stock_monitor/) reads `acquisition_mode` / `owner_type`,
  the rent through `contract_contract_maintenance_equipment_rel`,
  `current_location_id` for every asset, the country of `warehouse_id.partner_id` and
  the currency of the country. None of it survives revision 2. Its totals are not to be
  used (audit: the saw counted as a consumable with 329 € of accounting value).
- `stock.location.place_type` is required with default `physical`, so every location
  has one (maintenance_shareholder_equipment/models/stock.py:11). No stock currency
  field exists yet.
- OCA `stock_location_address`: `address_id` is stored; `real_address_id` is computed
  and not stored.

OCA contract (contract/models):
- `contract.contract.currency_id` is computed, **not stored** (contract.py:81). It is
  `manual_currency_id`, otherwise:
  - the price list currency (or the partner's property price list) only if a line has
    `automatic_price`;
  - otherwise the journal currency;
  - otherwise the company currency (`_get_computed_currency`, contract.py:461).
- `contract.line.price_unit` and `price_subtotal` are computed, **not stored**
  (contract_template_line.py:72-83). The stored price is `specific_price`, used when
  `automatic_price` is false.
- `recurring_rule_type`: daily, weekly, monthly, monthlylastday, quarterly, semesterly,
  yearly; `recurring_interval` is an integer (contract_recurring_mixin.py:33).

OCA account_asset_management (account_asset.py):
- `state`: draft, open, close, removed (line 111).
- `value_residual` = `depreciation_base` − `value_depreciated`, and `depreciation_base`
  excludes the salvage value (lines 281-305). So the net book value is
  `purchase_value − value_depreciated`, not `value_residual`.

Odoo and the existing code:
- `stock.quant.value` is not stored. The AVCO unit cost is the company-dependent
  `product_product.standard_price`.
- The equipment `cost` is set only when the equipment is created from a bill
  (lartdubati_investor_home/models/account_move_line.py). Equipment received through
  the phase 2 operations has no cost.
- `Many2one.convert_to_read` reads the display name as superuser, but `web_read`
  reads the co-records themselves under the user's rights. An investor without
  Inventory rights cannot rely on many2one labels (audit point 6).
- Removing a field drops its column with CASCADE, so every SQL view reading it is
  dropped too. Python constraints are not re-checked on existing data at update.
- The investor test user of `lartdubati_investor_home/tests` has `stock.group_stock_user`
  (test_stock_access.py), which real investors must not have.
- Odoo serves the RTL bundle unmirrored when the `rtlcss` command is missing (found
  with the mock-up).
- Currency rates (odoo/addons/base/models/res_currency.py):
  - `_get_rates` (line 121) takes for each currency the rate dated on or before the date
    with `company_id` in (NULL, the root company), ordered by `company_id` then
    `name DESC`. A company rate is therefore always preferred to a global one,
    whatever their dates.
  - When there is no rate before the date, it takes the **earliest later** rate; when
    there is no rate at all, **1.0**.
  - `_get_conversion_rate` (line 266) = rate(target) / rate(source) at the same date and
    for the same company; `_convert` multiplies by it (line 290).
- The equipment received before its bill is linked to the bill line at posting by
  `_reconcile_equipment()` (maintenance_shareholder_equipment/models/account_move.py:146),
  before `_fill_equipment_assets()`.

## 1. Answers to the audit, point by point

| # | Correction retained | Test planned | Owner decision |
|---|---|---|---|
| 1 | Contract currency: a stored field `equipment_currency_id` on contract.contract, computed by OCA's own logic (`currency_id`), with depends on `manual_currency_id`, `journal_id.currency_id`, `company_id.currency_id`, `pricelist_id.currency_id`, `contract_line_ids.automatic_price`. Constraint: a contract holding an equipment line has no `automatic_price` line. Without this constraint the currency would depend on the partner's property price list, which no dependency can follow, and the stored price would not be `specific_price`. The view reads `equipment_currency_id` and `specific_price`. | One test per origin: manual currency, journal currency, company currency. Price list path refused by the constraint. Recompute when the journal changes. | — |
| 2 | One conversion per measure, each with its own source amount, source currency, rate, rate date and « rate missing » flag. A missing rate gives NULL, never 0, and the amount is excluded from the totals and raises an alert. Modes: `historical` (each amount at its own date, §3.5) and `latest`; **`none` is removed**. | Asset in EUR plus rent in USD plus replacement value in IRR on one row: three conversions, one missing. Each date rule. `latest` mode. Totals ignore NULL. Migration of a company still set to `none`. | P9: default mode `historical` (test choice, C12). |
| 3 | Three explicit measures, `inventory_value`, `stock_value` and `accounting_value`, defined per case in §3.4. C19 split into inventory value and accounting value. | One test per row of the §3.4 table. | — (C19 for the accountant) |
| 4 | Asset state in the view (`asset_state`), with `accounting_provisional` set for a draft asset. Formula per state in §3.4. The NBV is `purchase_value − value_depreciated`. Provisional amounts are flagged everywhere and counted apart in the cards (« dont X provisoire »). New question C20. | One test each: draft, open, close and removed asset; salvage value not lost. | C20 (accountant) |
| 5 | Serial position through a subquery `DISTINCT ON (lot_id)` over the positive internal quants: largest quantity, then lowest id; with `count(*)` as `lot_quant_count`. One row per equipment whatever the count, values counted once, `alert_integrity` when the count is above 1. With no position: no location and `alert_no_position`. | Two positive quants for one serial: one row, unique id, quantity 1, values once, alert raised. Serial with no positive quant. | — |
| 6 | Real investors have no Inventory group. Investors read **text labels denormalised in the view**: `product_name`, `category_name`, `equipment_name`, `serial`, `stock_name`, `location_name`, `country_name`, `state_name`, `city`, `uom_name` (translatable jsonb where the source is). The many2one fields carry `groups=` for staff only. Rules filter on ids at SQL level, which needs no right on the co-model. The location filter by country follows the descendants of a stock whose root alone carries the address. | Investor with `base.group_user` + investor only: dashboard, read_group, analysis views and form work, and no co-model is read. The current tests are fixed (no stock group). A sub-location without `address_id` under a Bg/Stock-like stock is visible by country. | — |
| 7 | Migration order: (a) a precheck before the update (`docs/phase3/precheck.sh`, psql read-only), whose non-zero exit stops the deployment; (b) a post-migration script of 18.0.4.0.0 fills `is_monitor_stock` and the currency before anyone can edit, and refuses to continue if a candidate has no address; (c) after the update, a check that the monitor view exists and that no view depends on a removed column. | Migration rehearsal on the local copy with the old views: precheck failing while the reports exist, then passing; post-migration on Bg/Stock-like and lent_out data; a candidate without address stops the update. | — |
| 8 | Rent paid and monthly equivalent, defined in §3.6: posted bills only, product lines only, signed `balance` (HT, company currency), refunds deducted (full and partial), each bill converted at its accounting date. P8 formula as proposed by the audit; daily and weekly give NULL and `alert_rent_period_unsupported`, never an approximation. | Bill, partial refund, full refund, draft bill ignored, tax line ignored, bill in a foreign currency, unsupported periodicity, interval 2. | C21 (accountant: HT, non-recoverable VAT) |
| 9-11 | Corrective phase 2f, planned separately: `docs/phase2f/PLAN.md` (responsible user, accounting treatment shown in the receipt, read-only approver with minimal read rights, equipment cost with date and provisional flag). Must be deployed before phase 3. | In the 2f plan. | In the 2f plan. |
| 12 | No full load in the browser: the list uses `web_search_read` (domain, limit, offset, order); cards, stock cards, alerts and counts use `read_group` / `search_count`. Target: initial load under 2 s of server time and under 15 RPCs on 10,000 monitor rows. | Performance test tagged `monitor_perf` (not in the default run) on 10,000 generated rows: time and query counts. Hoot test checking that no RPC asks for more than one page. | P13: target accepted? |
| 13 | Allowed fields from `fields_get`, which omits fields the user's groups do not allow. The dashboard never asks for an absent field. The analysis views, pivot, export and form use the same model, so the same `groups=` apply. | AccessError for an investor on `read`, `read_group` and `export_data` of a staff field. Hoot test: no column or card for a field absent from `fields_get`. Tour: the analysis view and export with an investor. | — |
| 14 | Equipment to complete (`integration_state != done`) stays **out of the monitor**: no row, no value. It is counted in a separate « controls outside the monitor » block for staff only, by `search_count` under the user's own rights; serial numbers in stock without equipment are counted the same way. The mock-up shows it this way (screenshot 01). | Draft equipment: no row, counted in the control. Investor: no control. | — |
| 15 | Accessibility and ergonomics, worked into the mock-up and required of the module (§4.5): keyboard, contrast (AA), information not carried by colour alone, large amounts, 1024 px and tablet, full RTL, closable panel with focus restored, states for loading, no result and RPC error. | Hoot tests: Enter opens, Escape closes, focus restored, aria attributes. Screenshots in fr_FR, en_US and fa_IR at 1440, 1024 and 768 px. | — |
| Data | Data to prepare before phase 3 (address of Bougival, equipment « Test », receipt Bg/IN/00004, user with both Investor and Inventory, old monitor totals): read-only queries and owner decisions in `docs/phase2f/PLAN.md` §5. | — | D1-D4 in the 2f plan. |
| Deployment | Pinned OCA commits, dbfilter / `list_db = False`, rewritten production procedure, database and filestore backup: added to `docs/deployment/investor_home.md` §0 (prerequisites before production). The production procedure is rewritten in phase 5. | — | — |

## 1b. Answers to the audit of revision 3

| # | Correction retained | Test planned | Owner decision |
|---|---|---|---|
| A1 | Equipment cost with a stored date, provisional flag and source. Moved into **phase 2f** (`docs/phase2f/PLAN.md` §2), because it is set by the receipt and by bill posting; phase 3 only reads it. Receipt before bill: order price, receipt date, provisional. Bill before receipt: `abs(balance) / quantity`, accounting date, final. Bill posted after receipt: the estimate is replaced, through `_reconcile_equipment()`. Acquisition without purchase: unit value, execution date. No cost found: NULL and `alert_cost_missing`, never 0. The view no longer uses `quant.in_date`. | In 2f: order price ≠ bill price, bill before and after receipt, foreign currency, partial bill, acquisition, bill reset to draft. | — |
| A2 | Accounting treatment in the 2f receipt computed from the account the future bill line will actually use (in-memory bill line: fiscal position, `stock_account` input account); message « planned treatment under the current configuration ». Confirmation for company property only (purchase, and acquisition without purchase with its own message), never for borrowed or rented. | In 2f §3. | — |
| A3 | Independent approver: minimal **read** ACLs on what an operation references (orders, order lines, lots, transfers, moves, contracts, contract lines), no Inventory group, no write. A real interface test (tour) with an approver-only user opening and approving a complete operation. | In 2f §4. | — |
| A4 | Rates exactly as `_get_rates` / `_get_conversion_rate` (§3.5): same company / global priority, same fallback, factor = rate(target) / rate(source) at the same date and company. `m_rate` holds this effective factor. Odoo's silent fallbacks are flagged instead of hidden: 1.0 → NULL and `m_rate_missing`; later rate → same factor as Odoo plus `m_rate_fallback`. | SQL compared with `res.currency._convert()`: company → stock, foreign → company, foreign A → foreign B, company rate versus global rate, missing on the source side, missing on the target side, later-rate fallback. | — |
| C1 | `alert_negative_quantity` for negative quants: the row stays visible and is valued as the stock valuation does (negative quantity × AVCO), flagged as an anomaly. | Negative quant: row, signed value, alert. | — |
| C2 | D2 covers every candidate monitor stock: `Bg/Stock`, `TBER/Stock`, `TIST/Stock` and every `lent_out` location (2f §6). | — | D2 |
| C3 | 2f: the correction of existing equipment is **mandatory before deployment**. The 2f precheck refuses to deploy while an integrated equipment has no valid responsible, because `@api.constrains` only runs when its trigger fields change. | Precheck blocking on a database with such an equipment. | D1 |
| C4 | Alert counts and every aggregate of the first display come from **one** ORM method, `get_dashboard_data(filters)`, on the monitor model (§4.3), under the user's environment, without sudo. **Revised by 1c-4**: structured filters instead of a domain; 3 RPCs at first display. | Query count, groups (an investor gets no staff key), record rules. | — |
| C5 | Performance measured in the browser too: time from opening the menu to cards and list rendered (Playwright), plus server time. | `monitor_perf` test on 10,000 rows, both measures recorded. | — |

## 1c. Answers to the audit of revision 4

| # | Correction retained | Test planned | Owner decision |
|---|---|---|---|
| 1 | Cost known only through `cost_known` (phase 2f), never through a NULL Float. The view gives NULL when `cost_known` is false and 0 only for a real zero. Quantities and prices converted into the product's unit. Cancellation and release record the equipment before the unlink. Manual correction through a wizard reserved to Accounting / Administrator. | 2f §2 (reset to draft, cancellation, units, real zero). View: unknown cost gives NULL and the alert; real zero gives 0 without alert. | D7 (2f) |
| 2 | Treatment signature (account, profile, valuation, category, fiscal position, Anglo-Saxon flag) in the approval snapshot, recomputed at execution; any difference cancels the approval. The profile name is shown only to users who can read it. | 2f §3, against the account of the real bill line Odoo generates. | — |
| 3 | Deployment of 2f: backup, `git fetch` and extraction of the scripts without touching the working tree, setup, precheck, stop, merge, update and tests, restart only on success. | 2f §5. | — |
| 4 | `get_dashboard_data(filters)` takes **no Odoo domain**: a structured filter (§4.3) checked against a per-profile whitelist, from which the server builds the domain. The standard RPCs (`web_search_read`, `read_group`, export) are already protected by Odoo 18: a domain, order or group-by on a field the user may not read raises AccessError (`_field_to_sql`, models.py:3003; `_flush_search`, models.py:5792). This is tested, not assumed. The first display is **3 RPCs**: `fields_get`, aggregates and list page. | Investor: filter on a financial field refused by the method; `web_search_read`, `read_group` and `search_count` with a domain on `accounting_value` refused (AccessError). Store user: domain on `rent_paid` refused. RPC count measured at 3. | — |
| 5 | **No PostgreSQL function**: the rate lookup is written inside the view with `LEFT JOIN LATERAL` subqueries (§3.5). The only SQL object remains the view. | The comparisons with `_convert()` of A4 run on the view. | — |
| Approver | Read scope limited to the documents referenced by operations (record rules of the approver group), 2f §4. | 2f §4: unreferenced documents unreadable. | D8 (2f) |

## 2. Decisions for the owner

| # | Question | Proposal |
|---|---|---|
| P1 | Monitor technology | Module model on a SQL view (validated with the OWL choice). |
| P2 | What makes a location a stock? | A boolean `is_monitor_stock` on stock.location, rather than an optional `place_type`, which phase 2 rules read. A monitor stock requires an address and a currency. |
| P3 | Items in an internal location with no monitor stock above | Rows with « outside any monitor stock » and an alert, for staff only. |
| P4 | Owner of borrowed / rented items visible to investors? | No: staff only; investors see the status. |
| P5 | bi_sql_editor | The two reports are removed. Uninstalling the module is the owner's choice. |
| P6 | Screens | Decided: OWL dashboard plus standard views on the same model. |
| P7 | Threshold of « replacement value too old » | 12 months, company setting. |
| P8 | Monthly equivalent of a rent | Audit's formula (§3.6); daily and weekly are unsupported and raise an anomaly. |
| P9 | Conversion mode | **Accepted**: `historical` by default, `latest` as an option, `none` removed (C12). |
| P10 | Equipment to complete | **Accepted**: outside the monitor, counted in the staff controls. |
| P13 | Performance target | **Accepted**: under 2 s in the browser (and on the server) and under 15 RPCs for the first display on 10,000 rows; the design needs 3 RPCs. |

## 3. The view `lartdubati.stock.monitor`

### 3.1 Grain and unique ids
- One row per integrated equipment (`integration_state = done`, active).
  Id = `equipment.id * 2`.
- One row per consumable quant: internal location, quantity ≠ 0, product with
  `maintenance_ok` false. Id = `quant.id * 2 + 1`.
- The view is built so that each source row appears once. Every join that could
  duplicate is either aggregated or `DISTINCT ON`: lot position (point 5), contract data
  per equipment, bills per equipment.
- A unit test checks that the ids are unique on a dataset with every duplicating case.
- Quants of maintainable products without equipment are not rows; they are counted in
  the staff controls (point 14).

### 3.2 Location and stock
- Stock-managed equipment is placed by its lot position (point 5). Non-stock equipment
  is placed by `current_location_id`.
- `stock_id` is the nearest location at or above that location with
  `is_monitor_stock`. It is matched on the `parent_path` prefix, the longest one wins,
  never through `warehouse_id`.
- Geography comes from `stock_id.address_id`: country, state, city, as ids for the rules
  and as text labels for display (point 6).

### 3.3 Columns and groups
Staff = `stock.group_stock_user` or `account.group_account_readonly`.
Accountants = `account.group_account_readonly`.

| Field | Content | Visible to |
|---|---|---|
| `company_id`, `currency_id` (stock currency) | | all (res.currency is readable by every internal user) |
| `family`, `ownership_status`, `place_type`, `asset_state`, `accounting_provisional` | selections and boolean | all; `asset_state` and `accounting_provisional` for accountants |
| `product_name`, `category_name`, `equipment_name`, `serial`, `stock_name`, `location_name`, `country_name`, `state_name`, `city`, `uom_name` | text labels (point 6) | all |
| `stock_id`, `location_id`, `product_id`, `equipment_id`, `country_id`, `state_id`, `lot_id` | ids for rules, staff navigation and grouping | staff |
| `owner_partner_id`, `owner_name`, `responsible_name` | legal owner, responsible | staff (P4) |
| `warranty_status`, `insurance_status` | | all |
| `asset_count`, `quantity` | 1 per equipment; quant quantity for a consumable, not summed across products | all |
| `inventory_value` (+ source, rate, date, missing) | §3.4 | all |
| `replacement_value` (+ source, rate, date, missing), `replacement_value_date` | equipment | all |
| `stock_value` (+ conversion columns) | §3.4 | staff |
| `original_value`, `depreciated_value`, `accounting_value` (+ conversion columns) | §3.4 | accountants |
| `rent_amount`, `rent_currency_id`, `rent_rule_type`, `rent_interval`, `rent_start`, `rent_end`, `rent_monthly` (+ conversion columns) | active rental line, §3.6 | staff |
| `rent_paid` (+ conversion columns) | §3.6 | accountants |
| `alert_*` booleans and `alert_count` | §3.7 | per alert, the group of the figure it concerns |

Each converted measure `m` has five columns: `m` (converted, NULL if a rate is
missing), `m_source_amount`, `m_source_currency_id`, `m_rate`, `m_rate_date`, and the
flag `m_rate_missing`, all with the groups of `m`. `rent_paid` is converted bill by
bill, so its `m_rate` and `m_rate_date` are empty; the detail lists the bills.

### 3.4 The three values (point 3) and the asset states (point 4)

| Case | `inventory_value` (physical, all owners) | `stock_value` (carried by stock valuation) | `accounting_value` (net book value, company property) |
|---|---|---|---|
| Consumable (AVCO, automated) | qty × AVCO | qty × AVCO | qty × AVCO |
| Owned / lent_out equipment with `asset_id`, fixed-asset category | asset `purchase_value` | 0 (no double count) | by `asset_state`: draft → `purchase_value − value_depreciated`, flagged provisional; open / close → `purchase_value − value_depreciated`; removed → 0 and `alert_asset_removed` if still in stock |
| Owned / lent_out equipment without asset, category with automated valuation | equipment `cost` | qty × AVCO | `stock_value` |
| Owned / lent_out equipment without asset, category with manual valuation (expensed, like the saw in « All ») | equipment `cost` | 0 | 0, and `alert_no_asset` (staff) |
| Fixed-asset category without `asset_id` (bill not posted yet) | equipment `cost` | 0 | 0, and `alert_asset_missing` (accountants) |
| Borrowed / rented | replacement value (NULL and `alert_replacement_missing` if none) | 0 | 0 |
| Non-stock equipment (vehicle) | as owned, with its asset or cost | 0 | as owned |

- **Equipment cost** (phase 2f): `cost_known`, `cost` (company currency), `cost_date`,
  `cost_provisional`, `cost_source` and `cost_reference`. The view reads `cost` only
  when `cost_known` is true, otherwise NULL. A provisional
  cost makes the inventory value provisional (`inventory_provisional`, shown with the
  « provisional » tag). With no cost, the inventory value is NULL and
  `alert_cost_missing` is raised, never a silent 0.
- **AVCO** is the company's `standard_price` of the product.
- **C19** is split. Test choice: the inventory value of equipment without an asset is
  its purchase cost; its accounting value is what the books carry (stock valuation if
  automated, 0 if expensed).

### 3.5 Conversion dates (point 2)
In `historical` mode each measure uses its own date. In `latest` mode every measure
uses the last rate.

| Measure | Source currency | Date (`historical`) |
|---|---|---|
| asset values (original, depreciated, accounting, inventory) | company | asset `date_start` |
| equipment `cost` (inventory value without asset) | company | `cost_date` (phase 2f) |
| AVCO values (consumables, stock value) | company | date of the monitor (current values) |
| replacement value | `replacement_currency_id` | `replacement_value_date` |
| current rent | `equipment_currency_id` of the contract | `date_start` of the active line |
| rent paid | company (`balance`) | accounting `date` of each bill line |

- The rate of each currency is computed exactly as `_get_rates` does (correction A4):
  - candidate rows have `company_id` NULL or the root company, ordered by
    `company_id` (the company row first) then `name DESC`, and dated on or before the
    date;
  - without such a row, the earliest later row;
  - without any row, 1.0.
- `m_rate` = rate(stock currency) / rate(source currency), both at the same date for
  the same company: the effective factor, as in `_get_conversion_rate`. `m` =
  `m_source_amount × m_rate`, unrounded in the view; the dashboard rounds with the
  currency.
- Deviations from Odoo's silent behaviour, flagged rather than hidden:
  - a non-company currency without any rate row gets NULL (not 1.0), with
    `m_rate_missing` and `alert_rate_missing`;
  - when the earliest later rate is used, the factor is Odoo's, with `m_rate_fallback`.
  - The company currency without a rate row is 1.0, as in Odoo.
- Implemented **inside the view**, without any PostgreSQL function. For each measure,
  two `LEFT JOIN LATERAL` subqueries (source and target currency) select the rate row
  as `_get_rates` does:
  - `WHERE currency_id = … AND (company_id IS NULL OR company_id = root company)`;
  - first `name <= date ORDER BY company_id, name DESC LIMIT 1`;
  - then, as fallback, `ORDER BY company_id, name ASC LIMIT 1`.
  The factor and the flags are computed from these two rows. The only SQL object
  created by the module is the view (§6.3 checks it).

### 3.6 Rent (point 8)
- **Active rental line**:
  - `equipment_nature = rental` on a supplier contract (`contract_type = purchase`),
    line active and not cancelled, today within [`date_start`, `date_end`];
  - unique by the phase 1 overlap constraint;
  - amount = `specific_price × quantity × (1 − discount / 100)`, untaxed, in
    `equipment_currency_id` (point 1).
- **Monthly equivalent**:
  - monthly and monthlylastday: amount ÷ interval;
  - quarterly: amount ÷ (3 × interval);
  - semesterly: amount ÷ (6 × interval);
  - yearly: amount ÷ (12 × interval);
  - daily, weekly or any other value: NULL and `alert_rent_period_unsupported`. The
    contract amount and period are still shown.
- **Rent paid**:
  - sum of `account.move.line.balance` (company currency, signed: refunds negative);
  - lines must have `parent_state = posted`, `move_type` in (`in_invoice`, `in_refund`)
    and `display_type = product` (tax, payment term, section and note lines excluded);
  - linked by `contract_line_id` to a rental line of the equipment on a supplier
    contract, every line of the history included;
  - untaxed (non-recoverable taxes: C21);
  - each line converted at its accounting date;
  - full and partial refunds are deducted by their sign.
- Rent invoiced to customers (lent out against rent) is not a monitor measure in v1.

### 3.7 Alerts (all computed in the view, filterable and countable)

| Alert | Level | Visible to |
|---|---|---|
| `alert_rate_missing` (per measure, through `m_rate_missing`) | blocking | whoever sees the measure |
| `alert_integrity` (several positive quants for one serial; consumable quant with a third-party owner) | blocking | staff |
| `alert_no_position` (integrated serial with no positive internal quant) | blocking | staff |
| `alert_negative_quantity` (negative quant; the row stays, valued as the stock valuation does) | blocking | staff |
| `alert_cost_missing` (owned equipment without asset and without cost) | blocking | staff |
| `m_rate_fallback` (a later rate used, as Odoo does) | to check | whoever sees the measure |
| `alert_outside_stock` | blocking | staff |
| `alert_rental_ended` (latest rental line ended, item still in an internal stock) | blocking | staff |
| `alert_asset_removed`, `alert_asset_missing` | blocking | accountants |
| `alert_replacement_missing`, `alert_replacement_old` (P7) | to check | staff |
| `alert_lent_uninsured` | to check | staff |
| `alert_rent_period_unsupported` | to check | staff |
| `alert_no_asset` | to check | staff |
| `alert_no_responsible` (phase 2f) | to check | staff |
| `accounting_provisional` (draft asset) | to check | accountants |
| `inventory_provisional` (provisional cost, phase 2f) | to check | staff |

Investors see only the rate alerts of the measures they see (`inventory_value_rate_missing`,
`replacement_value_rate_missing`).
Alert columns are integers 0/1 with the `sum` aggregator, so that a single `read_group`
counts them all (C4).

## 4. Interface

### 4.1 Main interface: OWL dashboard (client action)
- Action `lartdubati_investor_home.action_stock_monitor` (stable XML id, target of the
  home page's Financial button). Layout as in the mock-up (`docs/phase3/mockup/README.md`).
- Header: title, date of the figures, « Detailed analysis » (secondary interface, with
  the current filters).
- Selection: Country, City, Stock (`SelectMenu`, searchable, stocks grouped by
  country · city), chained, with « Clear all ».
- Visual filters: a Family segment and multi-choice Ownership chips, each with its count
  and an icon. The pressed state is given by `aria-pressed` and by an icon, not only by
  colour.
- Stock cards: one per stock in the selection, following the family / ownership
  filters. The « outside any monitor stock » card is for staff only.
- Summary cards, according to the allowed fields:
  - items;
  - inventory value;
  - stock value (staff);
  - net book value, with « dont X provisoire » (accountants);
  - current rents as monthly equivalent (staff);
  - rents paid (accountants).
  Each card shows one line per currency, never added across currencies. Unconverted
  amounts are shown outside the totals, in red, with an icon and a text.
- Alerts: a button per kind with its count, which filters the list. Below them, the
  staff controls outside the monitor (point 14).
- List: search, sorting by column, 25 rows per page, all on the server (point 12).
- Detail panel:
  - alerts first, then ownership, location, values (with the provisional tag), rental
    contract with the bills (accountants), conversions with source, rate and date, and
    identity;
  - « Open the equipment form » for users with read access on maintenance.equipment
    only.

### 4.2 Secondary interface: standard views
Action `lartdubati_investor_home.action_stock_monitor_analysis` on the same model:
- list grouped by currency then stock;
- pivot, graph and read-only form;
- search view with filters and group-bys on the text labels and selections, so it
  works for investors too.
Exports go through the standard export, limited to the fields from `fields_get`.

### 4.3 Data access (points 12 and 13, complement C4)
- **One aggregated method** `get_dashboard_data(filters)` on `lartdubati.stock.monitor`
  (public, no sudo). It takes **no Odoo domain**. `filters` is a dictionary with only
  these keys:
  - `country_ids`, `cities`, `stock_ids`;
  - `families`, `ownerships`;
  - `alert` (one alert column name);
  - `search` (text).
  Values are type-checked. The server builds the domain from them:
  - `search` applies only to the text labels;
  - `alert` must be an alert the user may see.
  Any other key, any other value type, or an alert outside the user's whitelist raises
  a UserError. The whitelist comes from the fields the user may read (investor, store,
  accountant), so no filter can bear on a hidden figure.
- Under the user's environment, and therefore under the record rules, it runs:
  - one `read_group` grouped by `currency_id`, summing the converted measures (SQL
    `SUM` ignores NULL);
  - one `read_group` grouped by `stock_name`, `currency_id` (stock cards);
  - one `read_group` per visible measure on `m_rate_missing = 1`, grouped by
    `m_source_currency_id` (unconverted amounts, at most six);
  - one `read_group` with no grouping, summing every visible alert column (counts);
  - one `read_group` grouped by `country_name`, `city`, `stock_name` (selection lists);
  - for staff only, `search_count` on maintenance.equipment and stock.quant (controls
    outside the monitor), only if `check_access_rights` allows it.
- The list page uses the standard `web_search_read` with the domain the client builds
  from the same filters. Odoo 18 refuses any domain, order or group-by on a field the
  user may not read (`_field_to_sql` and `_flush_search`); a test proves it for each
  profile.
- Fields not readable by the user (`_has_field_access` / `fields_get` of the user) are
  left out of every aggregate, so the method never returns or computes a figure the
  user could not read directly.
- First display: **3 RPCs**:
  1. `fields_get` (metadata);
  2. `get_dashboard_data` (aggregates);
  3. `web_search_read` (list page: limit 25, offset, order).
  Each filter change makes calls 2 and 3 again. Detail: `web_read` of the row.
- Everything goes through the ORM with the user's environment. No controller, no
  `sudo()`, no raw SQL in Python: the only SQL is the view definition.
- RPC errors are caught: a banner with « Retry » is shown and the previous figures are
  never kept as if current.
- Performance (P13, C5), measured on 10,000 generated rows:
  - server time of `get_dashboard_data` plus the list page;
  - time in the browser from opening the menu to the cards and the list being rendered
    (Playwright), with the local and the server figures recorded in the test report.

### 4.4 Mock-up (iteration 2, for the owner's validation)
`docs/phase3/mockup/`:
- throwaway module with static demo data, never installed on a server;
- 19 screenshots, listed in its README;
- this iteration adds the three values, the provisional net book value, the integrity
  alert, the unsupported weekly rent, per-date conversions, the staff controls,
  keyboard navigation and focus, the loading / empty / error states, AA contrast and
  fa_IR (RTL).

### 4.5 Accessibility and ergonomics requirements (point 15)
- Keyboard:
  - every control is reachable with Tab;
  - a list row is focusable; Enter or Space opens it;
  - Escape closes the panel and gives the focus back to the row;
  - the panel puts the focus on « Close » when it opens.
- Contrast: AA (4.5:1) for all text. Checked in the mock-up: grey text 5.43, « Rented »
  5.55, « Owned » 6.73, alerts 5.74 and 6.59.
- Not colour alone: ownership badges have an icon and a text; alerts have an icon, a
  text and a hidden prefix (« Blocking: » / « To check: »); unconverted and provisional
  amounts have a text tag.
- Large amounts: tabular figures, wrapping inside the cards, amounts isolated with
  `<bdi>` in RTL.
- Responsive: at 1200 px and above the panel sits beside the list; under 1200 px it
  opens over the list; under 992 px the minor columns are hidden; tablet screenshots at
  1024 and 768 px.
- RTL: logical CSS properties, checked in fa_IR. The server needs `rtlcss` (official
  Odoo image; to check on the server).
- States: skeleton while loading; « no result » with « Clear filters », plus the
  no-profile case; RPC error banner with « Retry ».

## 5. Access
- `ir.model.access` read on the monitor for investor, `stock.group_stock_user` and
  `account.group_account_readonly`; no write right.
- Global rule `user.stock_access_rule_domain('monitor')`.
  - `_monitor_domain` uses `family`, `ownership_status`, `country_id` and `stock_id`.
  - For the stock dimension, the allowed stocks are expanded with their descendants
    (searched as superuser inside the rule method) into `stock_id in [...]`.
- Location rule:
  - `_location_domain` on country = `child_of` the monitor stocks whose own
    `address_id.country_id` is allowed;
  - this covers sub-locations without an address (point 6).
- Real investors: `base.group_user` + investor, without any Inventory, Maintenance or
  Accounting group (tests and setup accordingly).
- The `groups=` of §3.3 apply to the dashboard, list, pivot, graph, form and export
  alike (point 13).

## 6. Migration and deployment (point 7)

### 6.1 `docs/phase3/precheck.sh` (before the update, read-only psql)
It stops the deployment (exit 1) when:
- a view depends on `maintenance_equipment.owner_type` / `acquisition_mode` or on a
  `res_company` column removed or changed (`pg_depend` / `pg_rewrite`);
- `contract_contract_maintenance_equipment_rel` still exists with rows nobody decided
  about;
- a candidate monitor stock (warehouse stock locations, `lent_out` locations) has no
  `address_id`, or its address has no country or city.
It prints the lists in every case.

### 6.2 Post-migration `maintenance_shareholder_equipment/migrations/18.0.4.0.0/post-migrate.py`
- Flags the candidates `is_monitor_stock`.
- Sets their currency to the company currency.
- Moves `stock_monitor_currency_mode = none` to `latest`.
- Writes through the ORM, so the constraints run. A candidate without an address
  raises, the update fails and the deployment script stops (backup restore documented,
  as in phase 2).

### 6.3 After the update
A psql check: the view `lartdubati_stock_monitor` exists, no view depends on a removed
column, and the counts of rows per family match the source tables.

### 6.4 Server procedure (`docs/phase3/README.md`, run by the owner)
1. Backup (database and filestore).
2. Phase 2f deployed and checked.
3. Remove the two bi_sql_editor reports; uninstall `maintenance_equipment_contract`
   once its data are decided.
4. `precheck.sh`, which must pass.
5. `git pull`.
6. `deploy_modules.sh`.
7. Post-update check (6.3).
8. `setup_phase3.py` (dry run, then `--apply`): repoints the home button, lists the
   staff controls.
9. Interface checks with the four profiles of 2f and an investor without Inventory
   rights.
Everything is rehearsed first on a local copy holding the old monitor views.

## 7. Tests
The tests of section 1, plus:
- unique ids and no duplicated values on a dataset with every duplicating case;
- stock resolution:
  - nearest stock;
  - Bg/Stock-like stock outside its warehouse root;
  - sub-location without address;
  - outside any stock;
- consumable at AVCO; non-stock equipment;
- archived equipment and draft equipment are absent;
- constraints:
  - a monitor stock without address is refused;
  - a lent_out location that is not a monitor stock is refused;
  - an equipment line on a contract with `automatic_price` is refused;
- conversions compared with `res.currency._convert()`, on the cases of A4;
- `get_dashboard_data`:
  - query count;
  - an investor gets no staff or accountant key;
  - totals restricted by the access profile;
- negative quant (C1);
- the 98 tests of phases 1-2 and those of 2f still pass.

## 8. Order of work (small commits)
1. Mock-up iterations, the current step: screenshots to the owner.
2. Audit of this plan (revision 3) and of the 2f plan. No business code before their
   green light.
3. Phase 2f (its own plan), deployed before phase 3.
4. stock.location, contract currency, constraints, migration, with
   tests.
5. SQL view and model (§3), with tests.
6. Access (§5), with tests.
7. Secondary interface (§4.2).
8. OWL dashboard (§4.1, 4.3, 4.5), Hoot tests, tour, performance test, screenshots in
   three languages.
9. Removal of the obsolete fields and setting; migration rehearsal with `precheck.sh`.
10. Setup script, README, translations (exported), CLAUDE.md, DEFINITIONS.md
    (« Stock », « Measures », « Currency », « Access »), QUESTIONS_COMPTABLE.md; then
    the mock-up is deleted.

## 9. Verified / not verified / hypotheses
- Verified in the code: section 0.
- Verified with the mock-up (local Odoo 18):
  - `SelectMenu` with groups and search; `Pager`;
  - side panel and overlay;
  - keyboard: Tab reaches the row, Enter opens with focus on « Close », Escape returns
    the focus to the row (checked by script);
  - AA contrast (computed);
  - fa_IR mirrored once `rtlcss` was installed.
  Pitfalls found:
  - English words in templates get Odoo's translations;
  - `.o_action` imposes a column layout;
  - Sass `min()` with mixed units breaks the bundle;
  - Chrome draws no outline on a `<tr>`;
  - the RTL bundle stays cached when it was built without `rtlcss`.
- Not verified (server):
  - content of `contract_contract_maintenance_equipment_rel`;
  - other views depending on the obsolete columns;
  - addresses of the existing locations (the audit reports Bougival without city or
    country);
  - other uses of bi_sql_editor;
  - presence of `rtlcss` in the `odoo_web` image.
- Hypotheses to check in steps 4-8:
  - performance of the `parent_path` match and of the per-bill conversion on 10,000
    rows (indexes added where EXPLAIN demands);
  - `read_group` on text labels translated in jsonb;
  - `fields_get` omitting the fields of foreign groups in Odoo 18 (expected, to be
    tested);
  - Hoot tests of a client action in Odoo 18.

## 10. Accountant (docs/QUESTIONS_COMPTABLE.md)
- C12 updated: per-measure dates, `historical` by default, `none` removed.
- C19 updated: inventory value versus accounting value of equipment without an asset.
- C20 (new): draft assets shown as provisional.
- C21 (new): rent paid untaxed; non-recoverable VAT.

## 11. Implementation notes (09/10/2026), for the code audit

Developed in the order of section 8, one commit per step (4 da4b5ef, 5 bcf936b,
6 3336526, 7 f8e22a4, 8a a1c271a, 8b d02bb4d, 8c 7c6e6c0, 9 e34653e, then docs and
translations). Departures from the plan, each with its reason:
- **Monitor stock fields** (P2): `is_monitor_stock` and `monitor_currency_id` (the
  name avoids any clash with a `currency_id` other modules could add to locations). A
  monitor stock is internal and needs a currency and an address with a city and a
  country; a lent-out location must be one. The off-site stock created by an exit is
  flagged in company currency, and the exit checks the site address first.
- **Contract currency**: `equipment_currency_id` reuses OCA's own
  `_get_computed_currency()`; the depends also list `partner_id` (the price-list path is
  excluded by the constraint anyway).
- **NULL amounts**: the ORM reads a NULL Float as 0.0, so « unknown » could not be told
  from 0 on a row. Each measure has a `<measure>_known` column (0/1); the list, form and
  dashboard hide or flag unknown amounts. Totals were already right (SQL sums ignore
  NULL); a currency whose amounts are all unknown gets no total line.
- **Consumables with manual valuation** (not in the §3.4 table): inventory value =
  quantity × average cost, stock value and net book value 0, like expensed equipment.
  New question C22.
- **Dates**: an amount without a date (replacement value without its date) is converted
  at today's rate, as `_convert()` does without a date.
- **Dashboard filters**: country, city and stock are sent as their **text labels**
  (`countries`, `cities`, `stocks`), not ids: the ids are staff-only fields and Odoo
  refuses a domain on them to an investor. The server builds the domain and returns
  it; the client uses it for the list page, so the domain is built in one place.
- **Export**: Odoo refuses any export to a user without « Allow export »
  (`base.group_allow_export`), investors included; with it, the field groups still
  apply (tested). Stricter than the plan, nothing to configure.
- **Home page button**: a server action `action_server_stock_monitor` opens the client
  action, because whether the quick start screen accepts a client action could not be
  checked (OCA web_quick_start_screen not available locally); server actions are already
  used there. `docs/investor_home/setup_investor_home.py` points to it.
- **Performance** (P13): the first version took 8.6 s on the server for 10,000 rows.
  Measured with EXPLAIN on a local copy (10,000 rows, half the stocks in another
  currency): the base computation took 21 ms. The time went to per-row work:
  - rate lookups as LATERAL joins (computed even when unused);
  - the nearest stock found per row;
  - the `ir.default` fallback of the company-dependent fields per row;
  - six full passes in `get_dashboard_data`;
  - web_search_read's second count.
  The fixes:
  - the conversions are set-based: the (currency, date) points needed are listed once,
    each rate looked up once exactly as `_get_rates` does, then hash-joined;
  - the nearest stock is resolved once per location, the fallbacks once per company;
  - `get_dashboard_data` makes one fine-grained `read_group` (country, city, stock,
    place, currency, family, ownership), from which totals, cards, alerts, counts and
    choices are derived; further queries only with an alert or text filter or for
    unconverted / provisional amounts;
  - the list page skips the second count (`count_limit` 1; the total comes from the
    aggregates).
  Result (`monitor_perf`, local machine): server 0.65 s (accountant) and 0.74 s
  (investor with its rules), browser render 1.1 s. The 3 RPCs of the first display are
  checked by a Hoot test.
- **Precheck**: the « views reading a removed column » check cannot be unit-tested once
  the columns are gone; it is covered by the rehearsal below. The other checks have a
  test.

Verified locally (Odoo 18, local OCA heads):
- 186 tests in both modules (5 Hoot tests run headless by one of them, 3 tour
  tests), plus the `monitor_perf` test on request;
- migration rehearsal on a database made with the deployed 2f code (d63608c): precheck
  failing on an old report reading `owner_type` / `acquisition_mode`, rows in the
  equipment-contract table and a stock without address, then passing once fixed; update
  to 18.0.4.0.0 / 18.0.2.0.0 without error; « No Conversion » moved to « Latest Rate »;
  post-check clean; the saw and the cement valued as expected.

Not verified (server):
- the content of `contract_contract_maintenance_equipment_rel` (README step 0a);
- Chrome, `websocket-client` and `rtlcss` in `odoo_web`;
- whether the quick start screen also accepts a client action (not needed with the
  server action);
- the times on the server's hardware (4 GB VPS) and with its rate history.

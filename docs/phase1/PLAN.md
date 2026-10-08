# Phase 1 plan – data model (revision 2 after audit)

Status: proposal, revised after the first audit (08/10/2026). No code written yet.
Scope: `maintenance_shareholder_equipment` 18.0.2.0.0 and the parts of
`lartdubati_investor_home` that conflict with it. Wizards are phase 2, the monitor phase 3.

## Decisions taken (audit + owner)

- D1: `owner_type` and `acquisition_mode` stay in the code, hidden and marked obsolete,
  until phase 3: the two bi_sql_editor reports read them, and Odoo drops a removed
  field's column with `DROP COLUMN … CASCADE` (`ir_model.py`, `_drop_column`), which
  would silently drop the report views.
- D2: `place_type` moves from `lartdubati_investor_home` to this module with the same
  technical name and values; both modules are updated together.
- D3 (revised): an equipment in stock is identified by its serial number, not by
  `maintenance_ok` alone (see 4).
- D4 (revised): warranty and insurance are not required columns, but are required by
  the central finalisation method (see 2), not only by a screen.

## 1. Two states of integration

`integration_state`: `draft` (to complete) | `done` (integrated). Stored, indexed,
tracked, never written directly (see 3).

- Any equipment created automatically (OCA `maintenance_account` at bill posting,
  import, API) is `draft`. A draft equipment is visible to maintenance users, excluded
  from the monitor (phase 3), and listed in a "To complete" filter.
- `done` requires, checked in the model by the finalisation method and by constraints
  on done records:
  - a serial number (`stock_lot_id`) for a stock-managed product, or a monitor location
    (`current_location_id`) for a non-stock asset, not both;
  - `ownership_status`, `owner_partner_id` consistent with it;
  - `warranty_status`, `insurance_status` set (no silent default; a value configured on
    the product category is applied explicitly when the record is created and shown);
  - replacement value, currency and date for borrowed / rented.
- Constraints that would block a draft (lot or location, warranty, insurance) only
  apply to `done` records. Uniqueness and consistency constraints apply to all.

This answers the audit's point 1: a bill posted before the receipt creates draft
equipment through `maintenance_account` (unchanged behaviour), and posting never fails
on the completion rules.

## 2. Receipt and bill, in either order

Matching key: the purchase order line (`purchase.order.line`), reachable from the
stock move (`purchase_line_id`) and from the bill line (`purchase_line_id`).

- Bill before receipt: `maintenance_account` creates one draft equipment per unit
  (lines already split to quantity 1 by `asset_product_item` for fixed-asset accounts;
  otherwise its own loop per unit). At receipt (phase 2 wizard / receipt validation),
  each serial number is given to a draft equipment of the same purchase line without
  lot, instead of creating a new one.
- Receipt before bill: the receipt creates the equipment. Before `super()` of
  `action_post()`, our override links each bill line to the received equipment of the
  same purchase line, filling **both** relations kept by `maintenance_account`:
  `account.move.line.equipment_ids` and `maintenance.equipment.move_line_id`; a line
  that already has equipment is skipped by `maintenance_account`, so no duplicate.
- After `super()`: `asset_id` is filled from `move_line_id.asset_id` when empty.
- Tests: both orders; both relations consistent (`equipment.move_line_id ∈ line` ⇔
  `equipment ∈ line.equipment_ids`); no duplicate; one asset per unit; purchase / bill
  matching quantities unchanged.

## 3. Write protection (model level, API included)

`ownership_status`, `owner_partner_id`, `integration_state`:
- `write()` refuses them unless the environment is superuser (`env.su`, only reachable
  from server code: the central methods) or the user is in the group « Equipment
  ownership managers » (manual correction, logged with a reason). A context key is not
  used, because a context can be sent by any API caller.
- `create()` by a non-manager accepts only `owned` with the company partner and
  `draft`; other values go through the central methods.
- Central methods: `_set_ownership(status, owner, reason)`,
  `action_finalize_integration()`; they check the caller's group or business right,
  write with `sudo()` limited to these fields, and post the real author and the reason
  in the chatter.

## 4. Third-party owner on stock (D3 revised)

On validation of a stock move line (`_action_done`), a line with an owner (`owner_id`)
is accepted only if:
- the product is tracked by serial number and the line has a lot;
- that lot is linked to exactly one equipment;
- that equipment is `borrowed` or `rented` and its `owner_partner_id` is the line's
  owner.
Otherwise the validation fails with a message naming the line. Consumables therefore
stay owned only (v1).

Product rule: a storable product (`is_storable`) that is `maintenance_ok` must be
tracked by serial number (constraint on `product.template`), whether or not its
category is a fixed-asset category.

## 5. Fields on maintenance.equipment

| Field | Type | Rule |
|---|---|---|
| `ownership_status` | selection owned / borrowed / rented / lent_out | required, indexed, tracked, protected (3) |
| `owner_partner_id` | many2one res.partner | required, indexed, protected; = `company_id.partner_id` for owned / lent_out, ≠ for borrowed / rented |
| `integration_state` | selection draft / done | required, default draft, protected (1) |
| `stock_lot_id` | many2one stock.lot | SQL unique; same product and company as the equipment |
| `asset_id` | many2one account.asset | indexed, not copied, SQL unique (one asset per unit) |
| `replacement_value`, `replacement_currency_id`, `replacement_value_date` | monetary, many2one res.currency, date | required at `done` for borrowed / rented |
| `warranty_status`, `insurance_status` | selection (3 values each) | required at `done` (1) |
| `handover_value`, `handover_value_date` | monetary, date | temporary, accountant pending |
| `current_location_id` | existing many2one | label « Emplacement (équipement hors stock) »; empty when a lot exists |
| `owner_type`, `acquisition_mode` | existing | hidden, obsolete, removed in phase 3 (D1) |

Removed: on the equipment `accounting_ownership`, `ownership_state`,
`rental_counterparty_id`, `rental_end_date`, `accounting_depreciation_active`,
`physical_wear_active`, `return_obligation`, `initial_condition`; on the maintenance
request `repairer`, `repair_invoice_ref`, `repair_cost` (replaced by purchase orders,
OCA `maintenance_request_purchase`). None is read by the bi_sql_editor reports
(checked in `docs/stock_monitor/*.sql`).

## 6. Consistency check job

Daily scheduled action: for each `done` equipment with a lot, compares the owner of the
lot's positive quants with its status. A difference creates one activity « Ownership to
check » on the equipment only if no open activity of that type exists for it
(idempotent); nothing is corrected automatically.

## 7. Product category

`is_fixed_asset_stock`. Check, for each company of the category (`with_company()`):
manual valuation; expense account of class 21 with an asset profile; that profile has
`asset_product_item`. Run when the flag or one of these properties changes.

## 8. Contract lines (OCA contract)

`equipment_id`, `equipment_nature` (rental / loan / insurance / maintenance).
- No overlapping periods `[date_start, date_end]` per equipment, nature and contract
  type (purchase / sale); empty end = open-ended; cancelled lines ignored.
- `insurance` only on supplier contracts; product = service, not `maintenance_ok`.
- Free loan: `_can_be_invoiced()` (the single filter used by
  `contract._get_lines_to_invoice()`) returns False for `loan` lines, so they keep a
  `recurring_next_date` (required by `_check_recurring_next_date_recurring_invoices`)
  but never produce an invoice, not even at zero. Test: a contract with only a loan
  line, then with a loan and a rental line: only the rental line is invoiced.

## 9. Supplier bills

- `contract_line_id` shown on supplier bill lines.
- Server-side check on posting (not only the screen domain): the contract line belongs
  to a supplier contract (`contract_type = purchase`) of the bill's partner and company,
  has nature `rental` and an equipment.
- Posting refused for a line on the rental expense account without a contract line.
  The account is a company setting `equipment_rent_account_id`; its default is looked
  up by code 613500 at installation and logged.

## 10. stock.location

`place_type` moved (D2). `return_location_id`, required when `place_type = lent_out`.
Existing data: `Bg/TEST Lent out` is `lent_out` without return location; the phase 1
script lists it and the owner chooses (decision O2 below). Currency and the change of
meaning of `place_type` (only on monitor stocks) stay in phase 3.

## 11. lartdubati_investor_home

- `maintenance_equipment.py`: its constraint (internal location on every active
  equipment) is removed; the rule of 1 replaces it.
- `account_move_line.py`: no longer sets `current_location_id`; equipment created from
  a bill is `draft`, `owned`, company partner.
- Tests updated; the rest waits for phase 3.

## 12. Phase 1 script (`docs/phase1/`, dry run by default, artdubati_test only)

Lists then, with `--apply`, deletes the six test equipment records through the API.
The dry run shows for each one its bill line (`move_line_id`, `equipment_ids`),
contracts (`maintenance_equipment_contract`), lot, asset and maintenance requests
(none found by the audit). Lists `lent_out` locations without return location.
Order on the server: backup, script dry run, `--apply`, module update of both modules,
tests, control dry run.

## 13. Tests, translations, manual

- Integration tests: the four hypotheses of CLAUDE.md, sections 1 to 9, write
  protection by API for a non-manager, idempotence of the job.
- `.po` from `--i18n-export`, FR / FA translations of the new labels.
- Manual: REF-05, REF-06, ADM-05, every card citing a removed field (searched in the
  three languages); a « To complete » card for draft equipment. Receiving procedures
  come with phase 2.

## Verified / not verified / hypotheses

- Verified in code: `DROP COLUMN … CASCADE`; columns read by the reports;
  `maintenance_account` equipment creation and its two relations;
  `asset_product_item` line split; `contract_line_id`; `_can_be_invoiced()` and the
  `recurring_next_date` constraint of OCA contract.
- Verified by the audit on the database: six equipment, no maintenance request, one
  linked to a bill, one to a contract; `Bg/TEST Lent out` is `lent_out`.
- Not verified: other views or reports reading removed fields (the script's dry run
  lists the database views depending on `maintenance_equipment` columns).
- Hypotheses: the four of CLAUDE.md, to be confirmed by the tests.

## Open decisions for the owner

- O1: the `draft` / `done` integration state (section 1) – this adds one status field,
  limited to completeness, not the global status refused earlier. Accept?
- O2: `Bg/TEST Lent out`: archive it (test data), give it a return location, or set it
  back to `physical`?

# Phase 1 plan – data model (revision 2 after audit)

Status: plan validated by the audit (08/10/2026); code written and tested locally, see README.md and CHARACTERISATION.md. Deviations from the plan: `replacement_value` and `handover_value` stay Float (a type change drops the monitor views); the fixed-asset category check runs for the companies selected when saving.
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
  the central finalisation method (see 1), not only by a screen.
- O1 (owner, audit): `integration_state` accepted.
- O2 (owner, audit): `Bg/TEST Lent out` is archived by the phase 1 script.

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

## 2. Receipt and bill: exact reconciliation, partial flows included

`maintenance_account` skips a bill line as soon as it has at least one equipment
(`not x.equipment_ids`). Linking some units and letting it create the rest is therefore
impossible: our code reconciles each line completely itself.

Matching key: the purchase order line P (`purchase_line_id` on the stock move and on
the bill line). No new field: the equipment of P are found through
- received equipment: their lot is on a done stock move line of P;
- draft equipment created from a bill: `move_line_id.purchase_line_id = P`.

**At bill posting**, before `super()` of `action_post()`, for each line L of a supplier
bill (`in_invoice` only) with a `maintenance_ok` product and a purchase line P:
1. the quantity must be a whole number of units (error otherwise);
2. `needed` = quantity of L;
3. `free` = equipment of P not linked to any bill line of a posted or draft bill,
   received ones (with a lot) first, in receipt order;
4. link `min(needed, free)` of them to L, filling **both** relations of
   `maintenance_account`: `L.equipment_ids` and `equipment.move_line_id`;
5. create the `needed - linked` missing ones as `draft` equipment, with the values of
   `maintenance_account` (`_prepare_equipment_vals`), linked the same way.
6. if L already has **more** equipment than units (bill reset to draft and quantity
   lowered), release the excess in a fixed order: draft equipment without lot created
   for L first (archived), then received equipment (link removed on both sides, the
   equipment stays), newest first; the chatter of the bill lists what was released.
L then has exactly its units and `maintenance_account` skips it. Bill lines without a
purchase line keep the standard behaviour of `maintenance_account` (equipment created
as `draft`).

**Supplier refunds create no equipment.** Odoo 18 counts `in_refund` as a purchase
document (`is_purchase_document()`), so `maintenance_account` creates equipment for a
refund line during `super()`. Masking `is_purchase_document()` is not an option: Odoo
calls it 8 times in `account_move.py` during posting. Neutralisation, without touching
the OCA module: before `super()`, our override records the equipment already linked to
each refund line; after `super()`, the equipment that `maintenance_account` has just
created for refund lines (linked now, not before) are unlinked from the line and
deleted, in the same transaction, with `sudo()`. Nothing remains after posting. Returns
of equipment are handled in phase 2.

**Refund created with « Extourner » (reversal).** Odoo builds it with `copy()`, and the
OCA field `equipment_ids` has no `copy=False`: the refund lines would start with the
original bill's equipment and break the constraints below. Our module redeclares the
inherited field with `copy=False`, so a reversal starts with no equipment.

**Supplier refunds and fixed assets: behaviour to measure, blocked by default.**
Static reading (to be confirmed by test, not acquired):
- Odoo 18 `account.move._reverse_moves()` builds the refund with `copy()` and never
  calls `_reverse_move_vals()`; the asset deletion that `account_asset_management`
  puts in `_reverse_move_vals()` is therefore not executed in this version;
- on the refund line, `asset_id` is `copy=False`, but `asset_profile_id` is recomputed
  from the account (`_compute_asset_profile`): a refund line on 215400 gets the profile
  and should create a **negative** asset at posting, whether the refund comes from
  « Extourner » or is entered by hand; the original asset should stay;
- reset of a supplier bill to draft (`button_draft` of the OCA module): its assets are
  deleted, and new ones are created at the next posting; `asset_id` is filled again then
  (section 2, after `super()`).

Test choice (question C8 of docs/QUESTIONS_COMPTABLE.md), made configurable in phase 1:
company setting « Allow supplier refunds on fixed-asset accounts », **off by default**.
When off, posting a supplier refund (manual or reversal) with a line on an account that
carries an asset profile is refused, with a message telling to ask the accountant.

First integration test (run with the setting on, to observe): bill with equipment and
asset, then the standard « Extourner » wizard, then a manual refund on 215400. Measured
before and after: number of `account.asset`, their purchase value and state, the
original asset, `equipment.asset_id`, the equipment linked to the refund. The behaviour
is documented only from this result; if the static reading is confirmed, an explicit
treatment (or keeping the block) is proposed for audit, according to the accountant's
answer to C8. Other refund tests (setting off): the refund on 215400 is refused; a
refund of a `maintenance_ok` line on another account, with and without purchase line,
is posted and leaves no equipment.

**One equipment, one bill line, both sides checked.** The two relations of
`maintenance_account` are independent: `account.move.line.equipment_ids` (many2many)
and `maintenance.equipment.move_line_id`. An API call can write either one directly.
Two symmetric constraints would make any sequential update fail (whichever side is
written first breaks the other one), and a context key to bypass them could be sent by
any API caller. The rules are therefore split so that one fixed order always passes,
without any bypass:
- on `maintenance.equipment` (`@api.constrains('move_line_id')`): when set, the
  equipment must not be in the `equipment_ids` of **another** line of a non-cancelled
  bill;
- on `account.move.line` (`@api.constrains('equipment_ids')`): every equipment of the
  line has `move_line_id` = this line, and none is in the `equipment_ids` of another
  line of a non-cancelled bill;
- on `account.move.line.write()`: removing an equipment whose `move_line_id` is still
  this line is refused, except in superuser mode (`env.su`, reachable only from server
  code).
Linking order, always: 1) `equipment.move_line_id`, 2) `line.equipment_ids`. It is the
order `maintenance_account` already follows (equipment created with `move_line_id`,
then added to the line), so its behaviour is unchanged. Unlinking order: 1) remove from
`line.equipment_ids`, 2) clear `move_line_id`, both in superuser mode.
Two private methods (leading underscore, so not callable by RPC) do this:
`_link_equipment(line, equipment)` and `_unlink_equipment(line, equipment)`. They run
with `sudo()`, write in the order above, then check the final invariant explicitly
(both sides agree, one line per equipment) and raise if it does not hold. An ordinary
API write that would break the invariant (adding an equipment of another line,
removing one side only, pointing `move_line_id` to a line that does not list it and is
then posted) fails; the remaining one-sided state (equipment pointing to a line that
does not list it) is refused at posting, where the count must also equal the units.
A cancelled bill releases its links (both relations); the draft equipment it created
without a lot are archived, not deleted. Tests include direct API writes on each side
(adding an equipment of another line, removing one side only), which must fail.

**After `super()`**: `asset_id` filled from `move_line_id.asset_id` when empty.

**Tests**: bill then receipt; receipt then bill; order 3, receive 1, bill 3 (1 linked,
2 draft created, then reused by the next receipts); order 3, bill 1 then bill 2;
receive 3, bill 2 then 1; bill 3 posted, reset to draft, quantity 2, posted again (one
released); same equipment never linked twice; cancelled bill releases its links; both
relations always consistent, including after direct API writes; one asset per unit;
purchase / bill quantities unchanged; posted refund creates nothing.

## 3. Write protection (model level, API included)

`ownership_status`, `owner_partner_id`, `integration_state`:
- `write()` refuses them unless the environment is superuser (`env.su`), which only
  server code can reach. Nobody writes them directly, managers included: a direct write
  cannot carry a reliable reason. A context key is not used, because any API caller can
  send a context.
- `create()` without superuser accepts only `owned`, the company partner and `draft`.
- Central methods, the only writers: `_set_ownership(status, owner, reason)` and
  `action_finalize_integration()`. They check the caller's right (business action of
  the phase 2 wizards, or the group « Equipment ownership managers » for a correction),
  write with `sudo()` limited to these fields and post the real author and the reason
  in the chatter. Corrections by a manager go through a small wizard « Correct
  ownership » (status, owner, mandatory reason) calling `_set_ownership`.

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
- Free loan, two overrides (both verified in OCA contract 18.0):
  - `contract.line._can_be_invoiced()` (the single filter of
    `contract._get_lines_to_invoice()`) returns False for `loan` lines: they keep a
    `recurring_next_date` (required by `_check_recurring_next_date_recurring_invoices`)
    but never produce an invoice line, not even at zero;
  - `contract.contract._compute_recurring_next_date()`: OCA takes the earliest date of
    all non-cancelled lines, and falls back to a computed date when it finds none. After
    `super()`, our override recomputes it from the non-`loan` lines only, and sets it
    empty when the contract has no other invoiceable line. A loan-only contract is
    then never selected by the invoicing job (`recurring_next_date <= today`), and in a
    mixed contract the loan date no longer holds the next date back.
  - `contract.line._compute_create_invoice_visibility()`: OCA shows the manual
    invoicing button whenever the line has a `recurring_next_date`; our override sets
    it to False for `loan` lines, so a loan-only contract shows no invoicing button.
  - Tests: run the invoicing job several times over several periods; a loan-only
    contract is never selected, produces no invoice and shows no invoicing button; a
    mixed contract invoices only the rental line, and its next date follows the rental
    line.

## 9. Supplier bills

- `contract_line_id` shown on supplier bill lines.
- Server-side check on posting (not only the screen domain): the contract line belongs
  to a supplier contract (`contract_type = purchase`) of the bill's partner and company,
  has nature `rental` and an equipment.
- Posting refused for a line on the rental expense account without a contract line.
  The account is a company setting `equipment_rent_account_id`; its default is looked
  up by code 613500 at installation and logged. (question C10 of
  docs/QUESTIONS_COMPTABLE.md).

## 10. stock.location

`place_type` moved (D2). `return_location_id`, required when `place_type = lent_out`
on an active location (archived locations ignored). `Bg/TEST Lent out` is archived by
the phase 1 script after checking it holds no stock (O2). Currency and the change of
meaning of `place_type` (only on monitor stocks) stay in phase 3.

## 11. lartdubati_investor_home

- `maintenance_equipment.py`: its constraint (internal location on every active
  equipment) is removed; the rule of 1 replaces it.
- `account_move_line.py`: no longer sets `current_location_id`; equipment created from
  a bill is `draft`, `owned`, company partner.
- Tests updated; the rest waits for phase 3.

## 12. Phase 1 script and server procedure (`docs/phase1/`, artdubati_test only)

Script (JSON-RPC, dry run by default, `--apply` only on artdubati_test, all checks
before any write):
- lists, then deletes the six test equipment records; the dry run shows for each one
  its bill line (`move_line_id`, `equipment_ids`), contracts
  (`maintenance_equipment_contract`), lot, asset and maintenance requests;
- archives `Bg/TEST Lent out` after checking it holds no quant;
- lists every storable `maintenance_ok` product not tracked by serial number (one
  known: « 1800W corded table saw, 254mm blade, with wheeled stand »), with its
  quantity on hand. A Python constraint does not fix existing data: the module update
  is not run until each of them is corrected (serial tracking), archived or deleted
  by the owner; the script refuses `--apply` while one remains.

Database check before the update, with `psql` (the Odoo API cannot see PostgreSQL
dependencies): views depending on the columns removed in phase 1.

```sql
SELECT DISTINCT v.relname AS view_name, t.relname AS table_name, a.attname AS column_name
FROM pg_depend d
JOIN pg_rewrite r ON r.oid = d.objid
JOIN pg_class v ON v.oid = r.ev_class
JOIN pg_class t ON t.oid = d.refobjid
JOIN pg_attribute a ON a.attrelid = d.refobjid AND a.attnum = d.refobjsubid
WHERE d.classid = 'pg_rewrite'::regclass
  AND t.relname IN ('maintenance_equipment', 'maintenance_request')
  AND a.attname IN ('accounting_ownership', 'ownership_state', 'rental_counterparty_id',
                    'rental_end_date', 'accounting_depreciation_active',
                    'physical_wear_active', 'return_obligation', 'initial_condition',
                    'repairer', 'repair_invoice_ref', 'repair_cost')
ORDER BY 1, 3;
```

Expected: no row. Any row stops the procedure (the view would be dropped by CASCADE).

Order on the server: backup, script dry run, product corrections, `psql` check,
`--apply`, update of both modules together, tests, control dry run.

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
- Verified in code (second audit): `maintenance_account` skips a line with any
  equipment; `contract._compute_recurring_next_date()` uses all non-cancelled lines
  and falls back to a computed date.
- Verified in code (third audit): `is_purchase_document()` includes `in_refund` and is
  used 8 times in Odoo's `account_move.py`; `create_invoice_visibility` depends only on
  `recurring_next_date`.
- Verified in code (fifth audit): Odoo 18 `_reverse_moves()` uses `copy()` and never
  calls `_reverse_move_vals()`; `asset_profile_id` of a bill line is recomputed from
  the account. The effect on assets is a hypothesis until the first refund test.
- Not verified: other database views reading removed columns (`psql` check of 12).
- Hypotheses: the four of CLAUDE.md, to be confirmed by the tests.

## Open decisions for the owner

None left for phase 1. For each non-serialised maintainable product listed by the
script, the owner chooses: serial tracking, archive or delete.

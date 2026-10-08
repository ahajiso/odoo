# Phase 2 plan – equipment operations (receiving, exit, return, restitution)

Status: revision 2 for audit (08/10/2026), after the audit of revision 1 and the owner's
answers to O1–O4. No code written yet.
Scope: `maintenance_shareholder_equipment` 18.0.3.0.0. Builds on phase 1 (data model,
`_set_ownership`, stock owner checks, contract line rules, bill reconciliation). The
monitor is phase 3, the manual phase 5.

Changes from revision 1: one receiving assistant for every way in (purchase, acquisition
without purchase, borrowed, rented, consumables), no equipment « to complete » after a
complete receipt, a dedicated group, a protected business link between operations and
stock moves, attachments in the assistant, explicit choice of the contracts stopped at
restitution, off-site stocks chosen or created per third-party site, return destination
kept on the operation, provisional block on any exit of equipment from the company.
DEFINITIONS.md (« Receiving (one wizard, four branches) ») is updated accordingly once
this plan is validated.

## 0. Facts checked in the code (Odoo 18, OCA heads used in phase 1)

- Receipt with an owner: `stock.picking.owner_id` is copied to the moves
  (`restrict_partner_id`) and to the move lines (`owner_id`) (`stock_picking.py`,
  around line 1265).
- No stock valuation for a third-party owner: `stock_account` excludes a move line or a
  quant whose `owner_id` is set and is not the company partner (`stock_move_line.py`
  line 128, `stock_quant.py` line 29).
- Quants of third parties are reservable by ordinary operations: without an owner,
  `_get_gather_domain(strict=False)` adds no owner filter (`stock_quant.py` line 770).
- Lent-out stocks are outside `Bg/Stock`: ordinary reservations (`child_of` the source)
  never pick them.
- OCA contract creates invoices and bills as drafts (`_recurring_create_invoice()` only
  calls `create`).
- `contract_line_successor` provides `contract.line.stop(date_end)` (a date before the
  start cancels the line).
- Contract rights: create / write only for `account.group_account_manager`
  (`contract/security/ir.model.access.csv`).
- Default serial number: sequence `stock.lot.serial`.
- `maintenance_account` takes the equipment category from
  `product.categ_id.equipment_category_ids` (first one) and creates one if none.
- 708300 « Locations diverses » exists in the French chart (`l10n_fr`, `pcg_7083`).

## 1. One business document: the equipment operation

A persistent model `equipment.operation` (not a transient wizard), shown as a guided
form with one « Validate » button. Persistent because it must keep: who asked, who did
it, the attachments and condition at receipt, the link to the stock moves, contracts,
purchase order and bill it created, and the reason posted with each status change.

- Types: **Receipt**, **Exit to a third party**, **Return from a third party**,
  **Restitution to the owner**. Reference from a sequence, state draft → done
  (or cancelled while draft).
- Validation runs in one transaction; any failed check rolls everything back and the
  operation stays draft. Nothing is created before « Validate » except the draft
  document itself.
- Common fields: company, date, requester (`res.users`), operator (current user,
  read-only), note, attachments (`many2many` `ir.attachment`, multiple upload in the
  form). At validation the attachments are linked to the operation and copied (same
  file, new attachment record) to each equipment created or moved, and to the picking.
- Lines: one per product and quantity for consumables, one per unit for equipment
  (serial number), with condition at receipt (text, posted in the equipment chatter
  with the attachments) and per-unit data (section 3).

## 2. Protected business link between operations and stock

- `stock.picking.equipment_operation_id` (and the same on `stock.move`): read-only,
  `copy=False`, written only in superuser mode (`create` / `write` refuse it otherwise;
  `env.su` cannot be reached by RPC). No context key is used.
- The operation creates its pickings and validates them itself, in superuser mode,
  after its own checks; the real user stays `env.uid` (Odoo 18 `sudo()` keeps the uid),
  so `create_uid` / chatter show the operator.
- Section 7 rules accept the stock moves that change the situation of an equipment only
  when their picking is linked to an operation of the matching type being validated
  (state set to `processing` in superuser mode during « Validate », then `done`).

## 3. Receiving assistant (type Receipt): five branches

First choice (mandatory): **Purchase**, **Acquisition without purchase**, **Borrowed**,
**Rented**. Family is per line: equipment (maintainable product tracked by serial
number, or non-stock asset) or consumable (any other storable product).

Header, according to the branch:

| Field | Purchase | Without purchase | Borrowed | Rented |
|---|---|---|---|---|
| Vendor / origin / owner | vendor | origin partner (optional) | owner (third party) | lessor |
| Purchase order | existing (confirmed, with quantities left to receive) or created | – | – | – |
| Supplier bill | none, existing, or draft created from the order | – | – | – |
| Contract | – | – | loan line (new supplier contract) | rental line (existing supplier contract of the lessor, or new) |
| Consumables allowed | yes | yes | no (v1) | no (v1) |

Always: requester, receipt type (incoming picking type, `warehouse_id` never used),
destination stock (active internal location, `place_type = physical`, same company;
non-stock assets: the monitor location instead), date, attachments.

Equipment line data (all mandatory unless stated): product, serial number (existing
draft equipment of the order, a new number, or « no manufacturer serial number » taken
from `stock.lot.serial`), name (default « product – serial »), responsible / holder
(`owner_user_id`), warranty status, insurance status (defaults from the product
category, shown and editable), condition at receipt; replacement value, currency, date
for borrowed / rented (optional otherwise); rent amount, periodicity, start date for
rented.

On validation:
1. checks: rights (section 6), branch rules, serial numbers not linked to another
   equipment, quantities not above what is left on the order, every mandatory value
   present (otherwise nothing is validated and the missing fields are listed);
2. purchase order: created and confirmed when « create » was chosen (vendor, lines,
   prices given in the assistant);
3. picking: for a purchase, the open receipt of the order (partial quantities: Odoo's
   backorder is created, the rest stays to receive by a next operation); otherwise a
   new incoming picking: source = the partner's supplier location (borrowed, rented),
   or the inventory adjustment location (acquisition without purchase, test choice
   C17); `owner_id` = owner for borrowed / rented; move lines with the serial numbers;
   linked to the operation (section 2) and validated;
4. equipment: for each unit, the draft equipment of the purchase line without serial
   number (bill posted before receipt, phase 1) is reused if any, otherwise one is
   created; status and owner through `_set_ownership()` with the operation as reason;
   all data written; then `action_finalize_integration()`. **A validated receipt
   never leaves an equipment « to complete ».**
5. bill: « create draft bill » calls the order's standard bill creation; the bill stays
   draft for the accountant. When it is posted, phase 1 links its lines to the
   received equipment and fills `asset_id` from the asset then created: the equipment
   is integrated from the receipt, the accounting asset appears only at posting;
6. contract: loan or rental line per equipment (products from the settings, section
   8), created in superuser mode;
7. chatter of operation, picking, equipment, order and contract cross-linked.

Non-stock assets: no picking, the monitor location is set; the rest is identical.

Standard « Validate » on a receipt of a maintainable serial product, outside an
operation: refused with a message pointing to the assistant (otherwise an equipment
would be created incomplete or not at all). Consumables keep the standard receipt.
Bills posted before receipt and bills without order still create draft equipment
through `maintenance_account` (phase 1): those are the only source of « to complete »
equipment; the receiving assistant offers them as serial number candidates.

## 4. Exit to a third party (lent out)

Header: third party, site (an address of that third party: the partner itself or one of
its contacts / delivery addresses), off-site stock, nature (free loan / rented out),
date, requester, attachments. Lines: owned, integrated equipment in an internal physical
stock (or non-stock); condition at exit.

Off-site stock (O4):
- proposed: active `lent_out` locations whose `address_id` (OCA stock_location_address)
  belongs to the third party's commercial partner, the chosen site first;
- or created from the assistant: name, address (must belong to the third party),
  parent = an internal location flagged « parent of off-site stocks » (new boolean,
  e.g. `WH/Chez tiers`; default: the flagged parent under the same root as the
  equipment's stock, changeable), `place_type = lent_out`, return location (phase 1
  constraint) = the equipment's current stock;
- several sites per third party are possible, and a site may be shared by several
  warehouses.

Return destination: stored **on the operation line** (the stock each equipment left
from). The location's `return_location_id` stays only a default for items without
recorded origin. A shared off-site stock therefore needs no single return destination.

Validation: `_set_ownership('lent_out', company partner, reason)`, internal picking
(no owner) from the current stock to the off-site stock linked to the operation,
customer contract (`sale`) with one `loan` line (no invoice) or `rental` line (price,
periodicity, start; draft invoices) per equipment. Asset kept, depreciation continues.

## 5. Return from a third party and restitution to the owner

**Return** (lent out → owned): lines = lent-out equipment of one off-site stock;
destination per line = the origin recorded at exit (changeable to another internal
physical stock). `_set_ownership('owned', company partner, reason)`, internal picking
back, customer loan / rental line of the equipment stopped at the date.

**Restitution** (borrowed / rented → back to the owner, O3): the assistant lists the
open contract lines **whose `equipment_id` is one of the returned equipment** (no
other line is ever shown or stopped):
- loan / rental lines of possession (supplier contract): always stopped, not editable;
- insurance and maintenance lines: shown checked, but the user must confirm each one
  (a line unchecked stays open; validation refused until every line is explicitly
  confirmed or unchecked);
then outgoing picking from the current stock to the owner's supplier location, move
lines with `owner_id` = owner, linked to the operation, validated; checked lines
stopped at the date (`stop()`); no internal quantity of the serial number left;
equipment archived (status kept for history).

A new exit on the day of a return would overlap the closed interval of the previous
line: the assistant proposes the next day as start date.

## 6. Rights (O1)

New group **« Equipment operator »** (implies `stock.group_stock_user` only): creates
and validates equipment operations. It gets no Maintenance manager, Purchase, Invoicing
or contract rights.

Controlled elevation, inside the private validation methods only (not callable by RPC),
after the checks of the operation, each step in superuser mode:
- allowed: create / confirm a purchase order from the assistant's lines; create a
  draft bill from that order; create stock lots, pickings, moves and validate them;
  create equipment and set ownership / integration; create off-site stocks; create
  contracts and lines, stop the lines selected in a restitution or return; copy
  attachments;
- never: post a bill or invoice, confirm or modify an asset, change prices of an
  existing order, write any other record.
The operator is the author everywhere (uid kept; chatter messages name them).
Manual corrections of ownership stay with « Equipment ownership managers » (phase 1).
Record rule: an operator sees the operations of their companies; equipment managers
read them; ownership managers can cancel a draft of anyone.

## 7. Stock rules (validation of done move lines, any screen, API included)

For a move line carrying the serial number of an equipment:
- entering a `lent_out` location, leaving a `lent_out` location, receiving a
  third-party owned serial number, or leaving the internal locations for a borrowed /
  rented equipment: only in a picking linked to an operation of the matching type being
  validated (section 2). An ordinary delivery that reserved a borrowed item (section 0)
  is refused.
- owned equipment leaving the company (sale, scrap, supplier return, inventory loss):
  **provisionally refused** for everyone except « Equipment ownership managers »
  (group checked on the user, not on the context), until a disposal operation exists
  (later phase, with the accountant's answer on asset disposal, C18). After such an
  exit, the daily job creates one activity « Equipment no longer in stock » to archive
  it.
- moves between internal physical stocks: allowed (no ownership change).
For a move line without equipment: a consumable entering a `lent_out` location is
refused (v1: consumables owned only).
Phase 1 rules (owner on stock consistent with the status) stay.

## 8. Settings and phase 2 script

Company settings (block « Equipment », Invoicing settings, phase 1):
- « Loan product », « Rent product (paid) » (expense 613500, C10), « Rent product
  (received) » (income 708300, C16): service products, not maintainable;
- « Source of acquisitions without purchase » (default: the inventory adjustment
  location, C17);
- off-site parents: the boolean on locations (section 4).

`docs/phase2/setup_phase2.py` (dry run, `--apply` only on artdubati_test): looks up or
creates the three products and checks their accounts; flags `WH/Chez tiers` (id 109,
looked up and shown) as off-site parent; sets the settings; lists serial numbers of
maintainable products in internal stock without equipment (expected none), lent-out
locations without address, and the incoming picking types with their default
destinations.

## 9. Accounting (test choice, configurable, listed)

- C10 (existing): rent paid on 613500, through the product « Rent product (paid) ».
- C16 (new, accepted by the audit as a test choice): rent invoiced to customers on
  708300, through the product « Rent product (received) ».
- C17 (new): acquisition without purchase (gift, contribution, regularisation): test
  choice = receipt from the inventory adjustment location; consumables get Odoo's
  standard inventory valuation entry (accounts to be measured by test and reported);
  equipment of a fixed-asset category (manual valuation) gets no entry and no automatic
  asset: the accountant creates the asset and links it (`asset_id`, phase 1). Change:
  setting « Source of acquisitions without purchase ». Linked to C9 (handover value).
- C18 (new, for the later disposal operation): sale, scrap or loss of an equipment with
  an asset: removal through OCA `account_asset_management` (removal wizard), gain or
  loss accounts? Test choice: provisional block (section 7).

## 10. Tests

- Purchase, existing order: receipt before bill, bill before receipt (draft equipment
  reused, no duplicate, integrated), partial receipts over two operations with backorder,
  draft bill created and posted later (asset filled, equipment unchanged).
- Purchase, order created by the assistant; consumables only; mixed lines.
- Missing mandatory value (warranty, replacement value, serial): nothing validated.
- Standard « Validate » of a maintainable serial receipt refused; consumable receipt
  accepted.
- Acquisition without purchase: equipment and consumable; valuation entries measured.
- Borrowed: owner on stock, no valuation layer, loan line; invoicing job over several
  months creates nothing. Rented: draft bills on 613500 with the contract line; posting
  passes the phase 1 rent check.
- Exit: proposed off-site stocks per site; creation from the assistant; two sites for one
  third party; free and rented out; draft customer invoices only for rented out.
- Return: to the recorded origin; **two warehouses sharing one off-site stock**, each
  item back to its own warehouse; re-lending the same day refused, next day accepted.
- Restitution: possession line always stopped; insurance unchecked stays open; another
  equipment's lines untouched; refused if quantity left; equipment archived.
- Section 7 through ordinary pickings and the API: borrowed item delivered to a
  customer, rented item scrapped, lent-out item moved back, owned item moved to a
  lent-out stock, owned equipment sold by a stock user, consumables to a lent-out
  stock: refused; same sale by an ownership manager: accepted, one activity.
- Protected link: writing `equipment_operation_id` by API refused; a forged context key
  has no effect.
- Rights: operator without other rights validates every operation; the elevation never
  posts a bill; a stock user without the group cannot validate (API).
- Attachments: present on operation, equipment and picking.

## 11. Server procedure, translations, manual

- `docs/phase2/README.md`: backup, `git pull`, script dry run, apply, update and tests
  with `deploy.sh` (phase 1 script made generic: modules, test tags and expected count
  as arguments), interface checks. One `odoo_web` for every database: no real
  production yet (docs/deployment/investor_home.md, section 0).
- `.po` from `--i18n-export`; FR / FA translations.
- Manual: phase 5 (receiving assistant, exit, return, restitution, operator profile).

## Verified / not verified / hypotheses

- Verified in code: section 0.
- Not verified: incoming picking types and their destinations on artdubati_test;
  613500 and 708300 in the test database (the script checks them); the accounts used by
  Odoo for an inventory adjustment receipt of a consumable (C17, measured by test).
- Hypotheses, to be confirmed by tests: validating a purchase receipt in superuser mode
  keeps the purchase / bill matching of phase 1; Odoo's backorder of a linked picking
  does not copy the link (`copy=False`) and is then received by a next operation;
  `address_id` of stock_location_address can be set on creation; `stop()` keeps the
  invoiced periods.

## Open decisions for the owner

None blocking. To confirm: the operator group implies only « Inventory / User »
(proposed), and consumables keep the standard receipt in addition to the assistant.

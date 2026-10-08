# Phase 2 plan – receiving, exit, return and restitution

Status: draft for audit (08/10/2026). No code written yet.
Scope: `maintenance_shareholder_equipment` 18.0.3.0.0. Builds on phase 1 (data model,
`_set_ownership`, stock owner checks, contract line rules, bill reconciliation). The
monitor is phase 3, the manual phase 5.

Reference: docs/DEFINITIONS.md, « Ownership status » and « Receiving (one wizard, four
branches) ».

## 0. Facts checked in the code (Odoo 18, OCA heads used in phase 1)

- Receipt with an owner: `stock.picking.owner_id` is copied to the moves
  (`restrict_partner_id`) and to the move lines (`owner_id`) (`stock_picking.py`,
  around line 1265).
- No stock valuation for a third-party owner: `stock_account` excludes a move line or a
  quant whose `owner_id` is set and is not the company partner (`stock_move_line.py`
  line 128, `stock_quant.py` line 29). Borrowed and rented items therefore never create
  valuation layers or journal entries at receipt or restitution.
- **Quants of third parties are reservable by ordinary operations**: without an owner,
  `_get_gather_domain(strict=False)` adds no owner filter (`stock_quant.py` line 770).
  An ordinary delivery can reserve a borrowed item. Section 6 blocks it at validation.
- Lent-out stocks are outside `Bg/Stock`, so ordinary reservations (which search
  `child_of` the source location) never pick them (DEFINITIONS, « Stock »).
- OCA contract creates invoices and supplier bills as **drafts**
  (`contract._recurring_create_invoice()` only calls `create`); posting stays with the
  accountant.
- `contract_line_successor` provides `contract.line.stop(date_end)`; a date before the
  line's start cancels the line instead.
- Contract rights: create / write only for `account.group_account_manager`, read for
  `account.group_account_invoice` (`contract/security/ir.model.access.csv`).
- Default serial number: `stock.lot.name` defaults to the sequence `stock.lot.serial`.
- `maintenance_account` takes the equipment category from
  `product.categ_id.equipment_category_ids` (first one), and creates one if none.
- Account 708300 « Locations diverses » exists in the French chart (`l10n_fr`,
  `pcg_7083`).

## 1. Principle: the ownership comes from the business action, the stock checks it

- Purchase (owned): standard purchase order and receipt. No wizard is needed, because
  the equipment is created by the receipt itself (section 2), whichever screen
  validates it.
- Borrowed, rented (receipt), lent out (exit), return from a third party, restitution
  to the owner: four wizards. Each one checks the user's rights, then, in one
  transaction: writes the status through `_set_ownership()` (superuser mode, reason
  posted in the chatter), creates and validates the stock operation, creates or stops
  the contract lines, and checks the final consistency.
- A stock operation alone never changes the status. The rules of section 6 refuse any
  stock operation that contradicts the status, so the wizards are the only path for
  third-party property and lent-out items.

## 2. Purchase branch: equipment created at receipt

On validation of stock move lines (`_action_done`, after phase 1's owner check), for
each done line that
- brings a serial number into an internal location from a non-internal one (supplier,
  inventory adjustment, production),
- of a storable `maintenance_ok` product (serial tracking is already mandatory),
- without owner (owned),
- and whose serial number has no equipment yet (archived ones included):

1. if the line comes from a purchase order line P and P has draft equipment without a
   serial number (created when the bill was posted before the receipt, phase 1), the
   oldest one gets the serial number;
2. otherwise a new equipment is created: `draft`, `owned`, company partner, product,
   serial number, name « product – serial », category as `maintenance_account` does it
   (first equipment category of the product category, created if none), vendor and
   date from the picking, warranty / insurance defaults of the product category.

The equipment is then completed and integrated by an equipment manager (« To complete »
filter, « Integrate » button, phase 1). The bill reconciliation of phase 1 already
finds these equipment by their serial number on the purchase line's moves.

A receipt line with a third-party owner is still refused when no borrowed / rented
equipment of that owner exists for its serial number (phase 1): third-party receipts
go through the wizard.

## 3. Receiving wizard (borrowed / rented)

Menu: Maintenance → Equipment → « Receive borrowed or rented equipment », and Inventory
→ Operations. One wizard, branch chosen first.

Header (mandatory): status (borrowed / rented), owner (third party, not the company
partner), destination stock (active internal location, `place_type = physical`, same
company) or, for non-stock assets, the monitor location; receipt date; reason / note.
Consumables are refused (v1, owned only): only `maintenance_ok` products tracked by
serial number, or non-stock products (vehicle, installation).

Lines (one per item): product, serial number (or « no manufacturer serial number »:
taken from the `stock.lot.serial` sequence), replacement value, currency (default:
company), date (default: receipt date), warranty and insurance status (default from the
product category, otherwise mandatory).

Contract part:
- borrowed: one supplier contract (`contract_type = purchase`) per owner and receipt,
  one `loan` line per item, product = company setting « Loan product » (service, not
  maintainable), no invoicing (phase 1 overrides);
- rented: an existing supplier contract of the lessor or a new one, one `rental` line
  per item: rent product (company setting « Rent product (paid) », expense account
  613500, see C10), price, periodicity, start date, optional end date. Bills are created
  as drafts by OCA contract and posted by the accountant.

Validation, in this order, in one transaction:
1. checks (rights, owner, products, serials not already linked to an equipment, stock);
2. serial numbers created (`stock.lot`);
3. equipment created in superuser mode: status, owner, serial number, replacement
   value, warranty, insurance; then integrated (`action_finalize_integration`) when
   complete;
4. incoming picking: type = incoming type chosen in the wizard (default: the incoming
   type whose default destination contains the stock; `warehouse_id` is never used),
   source = the owner's supplier location, `owner_id` = owner, one move line per serial
   number; validated (phase 1's owner check runs and passes);
5. contract and lines created;
6. chatter: picking, equipment and contract cross-linked; attachments (photos,
   condition report) added afterwards in the chatter of the equipment.

Non-stock assets: steps 2 and 4 are skipped; the monitor location is set instead.

## 4. Exit wizard (lent out)

Entry: button « Lend to a third party » on owned equipment (list and form).

Mandatory: third party (not the company partner), exit date, nature: free loan or
rented out. Selected equipment must be `owned`, integrated, and in an internal physical
stock (or non-stock).

Off-site stock: the existing active `lent_out` location of that third party under the
parent « Chez tiers » (company setting, see 9), or one created on the fly:
name = third party, parent = setting, `place_type = lent_out`, `address_id` = third
party (OCA stock_location_address), return location = the current stock of the first
item (phase 1 constraint).

Contract: one customer contract (`contract_type = sale`) per exit, one line per
equipment: `loan` (product « Loan product », no invoice) or `rental` (product « Rent
product (received) », income account 708300, see C16; price, periodicity, start date).

Validation: `_set_ownership('lent_out', company partner, reason)`, internal picking from
the current stock to the off-site stock (no owner), validated, contract created. The
equipment keeps its asset; depreciation continues.

## 5. Return wizard (lent out → owned) and restitution wizard (borrowed / rented)

Return from a third party (button on lent-out equipment): destination = return location
of the off-site stock (changeable to another internal physical stock), return date.
`_set_ownership('owned', company, reason)`, internal picking back, open customer
contract lines of the equipment stopped at the return date (`stop()`).

Restitution to the owner (button on borrowed / rented equipment): restitution date,
optional note. Outgoing picking from the current stock to the owner's supplier location,
move line with the serial number and `owner_id` = owner, validated; all open contract
lines of the equipment (loan, rental, insurance, maintenance) stopped at the date; then
check that no internal quantity of the serial number is left, and archive the
equipment (status kept for history; it leaves the active monitor).

A new exit on the day of a return would overlap the closed interval of the previous
line: the wizard proposes the next day as start date.

## 6. Stock rules completing phase 1 (checked at validation, any screen, API included)

For a done move line carrying the serial number of an equipment:
- destination is a `lent_out` location → the equipment must be `lent_out` (set by the
  exit wizard just before the move);
- source is a `lent_out` location and destination is not → the equipment must not be
  `lent_out` anymore (set by the return wizard just before the move);
- borrowed / rented equipment leaving the internal locations → only to a supplier or
  customer location, with `owner_id` = the equipment owner (restitution). Blocks the
  ordinary delivery that reserved a borrowed item (section 0), scrap and inventory loss
  of third-party property (to be handled by an ownership manager).
For a done move line without equipment:
- a consumable (no equipment, any product not `maintenance_ok`) entering a `lent_out`
  location is refused (v1: consumables owned only; the 5 cement bags of
  `Bg/TEST Lent out` were such a case).

Owned equipment leaving the company (sale, scrap, supplier return) stays allowed with the
standard operations; the daily job (phase 1) gets a second check: integrated, active
equipment with a serial number and no positive internal quantity → activity « Equipment
not in stock », once.

## 7. Rights

- Receiving, exit, return and restitution wizards: users in `stock.group_stock_user`
  **and** `maintenance.group_equipment_manager` (proposal, O1).
- The contract part is written in superuser mode by the wizard after these checks, since
  only billing administrators can create contracts; the contract's chatter names the
  real author. Bills and invoices stay drafts for the accountant.
- Ownership corrections without stock movement: unchanged (ownership managers, phase 1).

## 8. Product rules and settings

Company settings (block « Equipment », Invoicing settings, phase 1):
- « Loan product », « Rent product (paid) », « Rent product (received) »: service
  products, not maintainable (phase 1 contract line constraint);
- « Off-site stocks parent »: internal location outside the warehouse stock
  (`WH/Chez tiers`, id 109 on artdubati_test, looked up and shown by the phase 2 script,
  never hard-coded).

Phase 2 script (`docs/phase2/setup_phase2.py`, same rules as phase 1: dry run, `--apply`
only on artdubati_test): looks up or creates the three service products (« Prêt de
matériel », « Location de matériel (payée) » with expense account 613500, « Location
de matériel (facturée) » with income account 708300), checks the accounts exist, sets
the four settings; lists serial numbers of maintainable products in internal stock
without equipment (expected: none) and lent-out locations without return location or
address.

## 9. Accounting (rule: test choice, configurable, question listed)

- C16 (new): account for equipment rent invoiced to customers. Test choice: 708300
  « Locations diverses », on the product « Location de matériel (facturée) ». Change: the
  product's income account, or another product in the setting.
- C10 (existing) reused for rent paid: 613500, on the product « Location de matériel
  (payée) ».
- Lent-out equipment keeps its asset and its depreciation (DEFINITIONS): no question.

## 10. Tests

- Purchase: receipt creates draft equipment once per serial number; bill before receipt
  then receipt: the draft equipment gets the serial number (no duplicate); inventory
  adjustment of a maintainable serial creates draft equipment; receipt with owner and
  no equipment still refused.
- Borrowed: wizard creates lot, equipment (borrowed, owner, integrated), receipt with
  owner (no valuation layer), loan line; the contract invoicing job run over several
  months creates no bill.
- Rented: rental line on a new and on an existing supplier contract; the job creates
  draft bills on 613500 with the contract line; posting passes the phase 1 rent check.
- Exit free and rented out: off-site stock created once per third party with address
  and return location; status lent_out; customer invoice drafts only for the rented-out
  line.
- Return: status owned, stock back in the return location, line stopped; re-lending the
  same day refused, next day accepted.
- Restitution: stock at the owner's location, lines stopped, equipment archived; refused
  if an internal quantity remains.
- Stock rules of 6 through ordinary pickings and the API: delivery of a borrowed item to
  a customer, scrap of a rented item, moving a lent-out item back without the wizard,
  moving an owned item to a lent-out stock, consumables into a lent-out stock: all
  refused. Daily job: owned equipment sold → one activity.
- Rights: a stock user without equipment manager rights cannot run the wizards (API).
- Non-stock assets: borrowed vehicle with monitor location, no picking.

## 11. Server procedure, translations, manual

- `docs/phase2/README.md`: backup, `git pull`, script dry run, apply, update and tests
  with `deploy.sh` (phase 1 script made generic: modules, test tags and expected count
  as arguments), interface checks. Reminder: one `odoo_web` for every database, so no
  real production yet (docs/deployment/investor_home.md, section 0).
- `.po` from `--i18n-export`; FR / FA translations of the wizards.
- Manual: phase 5 (new cards: receiving borrowed / rented, lending, return,
  restitution; PARC and INV cards to rewrite).

## Verified / not verified / hypotheses

- Verified in code: section 0.
- Not verified: incoming picking types available on artdubati_test for `Bg/Stock`
  (the script lists them); whether 613500 and 708300 exist in the test database (the
  script checks them).
- Hypotheses, to be confirmed by tests: a receipt with owner validated by the wizard
  passes phase 1's owner check when the equipment is created just before; the
  `stock_location_address` `address_id` can be set on creation of the off-site stock;
  `stop()` on a rental line keeps the already invoiced periods and only limits the next
  ones.

## Open decisions for the owner

- O1: who runs the wizards: stock users who are also equipment managers (proposed), or
  only the ownership managers.
- O2: purchase branch without wizard, equipment created at receipt (proposed), or a
  mandatory wizard for purchases too (an ordinary « Validate » would then have to be
  refused for maintainable products).
- O3: restitution stops every open contract line of the equipment, insurance and
  maintenance included (proposed), or only loan / rental.
- O4: off-site stock created automatically per third party under the parent setting
  (proposed), or chosen by hand among existing ones.

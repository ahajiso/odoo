# Phase 2 plan – equipment operations (receiving, exit, return, restitution)

Status: revision 4, development authorised by the audit (08/10/2026). Revision 3 was audited: two corrections
here (purchase order confirmed before its receipt is taken over; approval separated
from the physical execution, with an `approved` state), plus the free-loan rule and the
contribution nature of C17. No code written yet.
Scope: `maintenance_shareholder_equipment` 18.0.3.0.0. Builds on phase 1. The monitor is
phase 3, the manual phase 5. DEFINITIONS.md (« Receiving (one wizard, four branches) »)
is updated once this plan is validated.

## 0. Facts checked in the code (Odoo 18, OCA heads used in phase 1)

- Receipt with an owner: `stock.picking.owner_id` is copied to the moves
  (`restrict_partner_id`) and move lines (`owner_id`) (`stock_picking.py` ~1265).
- No stock valuation for a third-party owner (`stock_account`, `stock_move_line.py`
  line 128, `stock_quant.py` line 29).
- Quants of third parties are reservable by ordinary operations
  (`_get_gather_domain(strict=False)`, `stock_quant.py` line 770).
- Incoming valuation: the unit cost is the move's `price_unit` when it is not zero,
  otherwise the product cost (`stock_move.py` `_get_price_unit`, line 44); the credited
  account is the source location's `valuation_out_account_id`, otherwise the category's
  stock input account (`_get_src_account`, line 536).
- OCA contract creates invoices and bills as drafts; `contract_line_successor` provides
  `stop(date_end)`; contracts are created only by `account.group_account_manager`.
- Default serial number: sequence `stock.lot.serial`.
- `maintenance_account` takes the equipment category from
  `product.categ_id.equipment_category_ids`.
- French chart (`l10n_fr_account`): 708300 Locations diverses, 778000 Autres produits
  exceptionnels, 455100 Associés – comptes courants, 603200 Variation des stocks des
  autres approvisionnements.

## 1. The business document `equipment.operation`

Persistent model, guided form, buttons « Submit », « Approve », « Execute ».
- Types: **Receipt**, **Exit to a third party**, **Return from a third party**,
  **Restitution to the owner**. Sequence reference.
- States: `draft` → `to_approve` → `approved` → `processing` → `done`; `cancelled`
  from `draft`, `to_approve` or `approved`. `processing` is internal, set only during
  the execution (section 3). An operation without commitment goes from `draft` to
  execution directly.
- Approval and physical reality are separate: the approver authorises the commercial
  and legal conditions, with no stock movement; the operator executes the operation
  when the physical event happens. A user with both roles approves and executes in one
  click. **Prior approval is mandatory**: an operation needing approval cannot be
  executed before it (goods arrived without approval are not received until then).
- Once approved, the commitment fields (partner, order, products and quantities
  ordered, prices, rents, contract, dates of the contract, nature) are read-only;
  changing one sends the operation back to `draft` for a new approval. Physical fields
  (serial numbers, condition, photos, responsible, received quantities within the
  approved ones) stay editable until execution.
- Common fields: company, date of the operation, requester (`res.users`), operator
  (creator, read-only), approver (read-only), note, common documents (attachments).
- Lines: one per unit for equipment (serial number), one per product and quantity for
  consumables; each line has its own condition text and its own attachments (photos of
  that item).
- Attachments at validation: common documents linked to the operation and to each
  picking; line attachments copied to the equipment of the line, and posted with the
  condition text in its chatter.

## 2. Protected business link with stock

- `stock.picking.equipment_operation_id` and `stock.move.equipment_operation_id`:
  read-only, `copy=False` (a backorder is not linked), written only in superuser mode
  (`create` / `write` refuse it otherwise; `env.su` is not reachable by RPC). No context
  key is used anywhere.
- An existing picking (receipt created by a purchase order) is taken over by the
  operation: the link is set during validation, in superuser mode.
- Section 8 accepts the stock moves governed by this phase only when their picking is
  linked to an operation of the matching type in state `processing`.

## 3. Approval and execution: order, transaction, concurrency

**« Approve »** (approver; state `to_approve` → `approved`): lock, checks of section 6,
rights; records approver and date; no other write. Approvers get an activity when an
operation is submitted.

**« Execute »** (operator; from `draft` without commitment, or from `approved`), in one
database transaction:
1. lock the operation row (`SELECT … FOR UPDATE NOWAIT`, read lock, no SQL write) and
   re-read its state: anything else than `draft` / `approved` → error « already
   executed or being executed », nothing done; checks of section 6 again (the data may
   have changed since approval) and rights; a `draft` operation that needs approval →
   state `to_approve`, nothing else (or approved at once if the user is also approver);
   then state `processing`;
2. purchase order created by the operation: created and confirmed;
3. receipt: the picking generated by that confirmation, or the open receipt of the
   existing order, is taken over and linked (a new incoming picking only for the
   branches without order); never a second receipt for the same order line;
4. serial numbers (`stock.lot`) created; equipment created or completed (draft
   equipment of the order line reused) with their **target** ownership through
   `_set_ownership()` (reason = the operation) and all their data, integration still
   `draft`;
5. move lines set (serial numbers, owner for borrowed / rented, unit value for
   acquisitions without purchase) and the picking validated: phase 1's owner check
   finds the borrowed / rented equipment of that owner; the stock date is the
   execution date (no back-dating);
6. `action_finalize_integration()` on each equipment;
7. draft supplier bill, contract lines, stops (section 5);
8. final consistency check (status, owner, quant owner, location type, contract lines),
   cross-links in the chatters, state `done`.
Any failure rolls back the whole transaction: no order, lot, equipment, move, contract
or bill remains, and the operation is back in its previous state. A second call on a
`done` operation does nothing and raises (idempotence); two concurrent calls: the
second one fails on the lock. Exit, return and restitution follow the same steps
without 2 and 3 (their picking is created by the operation).

## 4. Receipt: five branches

Branch (mandatory): **Purchase**, **Acquisition without purchase**, **Borrowed**,
**Rented**. Family per line: equipment (maintainable product tracked by serial number, or
non-stock asset) or consumable. Consumables are allowed in Purchase and Acquisition
without purchase (v1: owned only).

Header by branch:

| Field | Purchase | Without purchase | Borrowed | Rented |
|---|---|---|---|---|
| Partner | vendor | donor / contributor (mandatory for gift and contribution, optional for regularisation) | owner | lessor |
| Nature | – | gift / contribution to a shareholder current account / regularisation (mandatory) | – | – |
| Order | existing confirmed order (its open receipt is taken over) or created | – | – | – |
| Bill | none, existing, or draft created: vendor reference, bill date and PDF mandatory then | – | – | – |
| Contract | – | – | loan line, existing supplier loan contract of the owner or new | rental line, existing supplier contract of the lessor or new |
| Contract data | – | – | start, planned end (or « open-ended » ticked), contract documents | start, planned end (or open-ended), rent, periodicity, contract documents |

Always: requester, receipt picking type (`warehouse_id` never used), destination stock
(active internal location, `place_type = physical`, same company; non-stock assets: the
monitor location), date, documents.

Line data: product, quantity (consumables) or serial number (existing draft equipment of
the order line, a new number, or « no manufacturer serial number » from
`stock.lot.serial`); for equipment: name, responsible / holder, warranty and insurance
status (category defaults, shown, editable), replacement value / currency / date
(mandatory for borrowed / rented), condition, photos; unit value for acquisitions
without purchase (mandatory, default product cost; see C17). For a contribution to a
shareholder current account, the value and date entered are also written to the
equipment's `handover_value` and `handover_value_date` (information only, C9).

Purchase details:
- bill posted before receipt: the draft equipment created by `maintenance_account`
  (phase 1) are offered as candidates and completed by the operation (no duplicate);
- receipt before bill: the draft bill may be created by the operation, or later by the
  accountant; when it is posted, phase 1 links the equipment and fills `asset_id`: the
  equipment is integrated from the receipt, the asset appears only at posting;
- partial receipt: quantities ≤ what is left; Odoo creates the backorder (not linked),
  received by a next operation.

## 5. Exit, return, restitution

**Exit to a third party** (lent out). Header: third party, site (the partner or one of
its addresses), off-site stock, nature (free loan / rented out), start, planned end (or
open-ended), rent and periodicity if rented out, requester, documents. Lines: owned,
integrated equipment in an internal physical stock (or non-stock), condition, photos.
- Off-site stock: proposed among active `lent_out` locations whose `address_id`
  (stock_location_address) belongs to the third party's commercial partner, the chosen
  site first; or created from the assistant (name, address of that third party, parent
  = a location flagged « parent of off-site stocks », default the flagged parent under
  the same root as the equipment's stock; `place_type = lent_out`; return location =
  current stock of the first item, phase 1 constraint). Several sites per third party,
  and a site may be shared by several warehouses.
- Return destination stored on the operation line (the stock each item left from).
- Result: `lent_out`, internal picking (no owner), customer contract with one `loan` or
  `rental` line per equipment. Asset kept, depreciation continues.

**Return from a third party** (lent out → owned): lines = lent-out equipment, destination
per line = the recorded origin (changeable to another internal physical stock),
condition and photos at return. Result: `owned`, internal picking back, customer
loan / rental lines of these equipment stopped at the date.

**Restitution to the owner** (borrowed / rented): condition and photos at restitution;
the assistant lists the open contract lines **whose `equipment_id` is one of the
returned equipment**, and no other:
- loan / rental lines of possession: always stopped, not editable;
- insurance and maintenance lines: proposed checked; each must be explicitly confirmed
  or unchecked before validation;
then outgoing picking to the owner's supplier location with `owner_id` = owner,
selected lines stopped, no internal quantity left, equipment archived (status kept).

A new exit on the day of a return would overlap the closed interval of the previous
line: the assistant proposes the next day.

## 6. Server-side checks of the values (before any write)

Rights are checked first, then every record and amount sent by the client, as the real
user (`check_access('read')` on each referenced record, then explicit rules):
- company: every partner, product, location, picking type, order, contract, currency,
  tax and account belongs to the operation's company (or is shared);
- partners: active; not the company partner as owner / lessor / third party; the
  donor / contributor required by the nature; the site belongs to the third party's
  commercial partner; an existing order or contract belongs to the given partner;
- products: active; purchase products `purchase_ok`; equipment lines maintainable and
  serial-tracked (or non-stock); consumable lines storable, not maintainable; contract
  products = the configured service products only;
- amounts: quantities > 0 and whole for equipment; prices, rents, replacement values
  ≥ 0; currencies active; taxes of type purchase (supplier) or sale (customer) and of
  the company;
- an existing order: confirmed, same vendor, quantities ≤ left to receive; its prices
  and lines are never modified by the operation;
- dates: start ≤ planned end; no overlap (phase 1 constraint, checked again).

## 7. Rights and approval

- **« Equipment operator »** (implies only `stock.group_stock_user`): prepares
  operations, submits them, executes them (without commitment, or once approved).
- **« Equipment operations approver »** (new): approves. Approval is required for any
  of: a purchase order created by the operation, a supplier bill, a rental line
  (supplier or customer), a customer contract (free loan included), a **new** supplier
  loan contract, the stop of a rental line, an acquisition without purchase
  (accounting entry, C17). A user with both roles approves and executes in one click.
- Operator alone: receipt on an existing confirmed order without bill creation;
  borrowed receipt on an **existing** loan contract of the owner (a new loan line is
  added to it); return or restitution of a free loan (no financial consequence); return
  of a free lent-out item.
- Elevation: superuser mode only inside the private execution steps of section 3, after
  sections 6 and 7; never posting a bill or invoice, never confirming or changing an
  asset, never writing an existing order's prices or lines. Operator and approver are
  named in every chatter message.
- Manual ownership corrections: « Equipment ownership managers » (phase 1), without
  stock movement.

## 8. Stock rules (validation of done move lines, any screen, API included)

- Supplier receipts (incoming picking type, source supplier location) and acquisitions
  (source = one of the acquisition locations of section 9): only in a picking linked to
  a Receipt operation in `processing`, **consumables included**.
- Inventory adjustments: consumables keep the standard physical inventory for count
  corrections, with Odoo's standard rights (Inventory / Administrator) and
  traceability; a serial number of a maintainable product can never appear or
  disappear through them, for anyone (an equipment comes in only by an operation).
- Equipment serial numbers: entering or leaving a `lent_out` location, receiving with a
  third-party owner, leaving the internal locations (borrowed / rented): only in a
  picking linked to an operation of the matching type in `processing`.
- **Owned equipment leaving the company (sale, scrap, supplier return, loss): refused
  for everyone**, until the disposal operation (later phase, C18).
- Consumables entering a `lent_out` location: refused (v1).
- Internal transfers between internal physical stocks: standard, allowed.
- Phase 1 rules (owner on stock consistent with the status) stay.

## 9. Settings and phase 2 script

Company settings (block « Equipment », Invoicing settings):
- « Loan product », « Rent product (paid) » (expense 613500, C10), « Rent product
  (received) » (income 708300, C16): service products, not maintainable;
- acquisition locations, one per nature (inventory usage, each with its
  `valuation_out_account_id`, C17): « Acquisitions / Gift » 778000, « Acquisitions /
  Shareholder current account » 455100, « Acquisitions / Regularisation » 603200;
- off-site parents: the boolean on locations.

`docs/phase2/setup_phase2.py` (dry run, `--apply` only on artdubati_test): looks up or
creates the three products and the three acquisition locations, checks their accounts
exist; flags `WH/Chez tiers` (id 109, looked up and shown) as off-site parent; sets the
settings; lists serial numbers of maintainable products in internal stock without
equipment, open incoming pickings not yet received (to be taken over by operations),
lent-out locations without address, and the incoming picking types with their
destinations.

## 10. Accounting (test choice, configurable, listed)

- C10: rent paid on 613500 (product « Rent product (paid) »).
- C16: rent invoiced to customers on 708300 (product « Rent product (received) »),
  accepted by the audit as a test choice.
- C17: acquisition without purchase. Valuation basis: unit value entered on the line
  (mandatory, default the product cost), used as the move's unit cost (average cost
  updated). Entry for automatically valued categories: debit the category's stock
  valuation account, credit the acquisition location's account: gift 778000,
  contribution to a shareholder current account 455100 (an advance in current account,
  not a capital contribution; other forms of contribution wait for C9), regularisation
  603200. For equipment, value and date also go to `handover_value` /
  `handover_value_date`. Fixed-asset
  categories (manual valuation): no entry, no automatic asset; the accountant creates
  the asset and links it (`asset_id`). Change: accounts of the three locations, or other
  locations in the settings.
- C18: sale, scrap or loss of an equipment: **blocked for everyone** until the disposal
  operation; asset removal (OCA removal wizard) and gain / loss accounts to be given by
  the accountant.

## 11. Tests

- Order of validation: borrowed receipt passes phase 1's owner check; a failure at each
  step (lot, equipment, picking, integration, contract) leaves nothing behind.
- Idempotence and concurrency: second « Execute » refused without effect; two cursors
  validating the same operation: one succeeds, the other fails on the lock.
- Approval: an operator alone gets `to_approve` for each commitment of section 7 and
  nothing is created; approval creates nothing either (no order, no move); the operator
  then executes; a user with both roles approves and executes at once; execution
  before approval refused; changing a commitment field after approval returns to
  `draft`; borrowed receipt on an existing loan contract by the operator alone, on a
  new contract refused without approval.
- Purchase order created by the operation: exactly one receipt, taken over (no second
  picking), stock date = execution date.
- Server-side checks: partner of another company, existing order of another vendor,
  negative price, sale tax on a supplier line, non-configured contract product, order
  line quantity exceeded: refused.
- Purchase: receipt before bill, bill before receipt (draft equipment reused), partial
  receipts over two operations, draft bill with reference / date / PDF, posted later
  (asset filled, equipment unchanged); order created by the operation; consumables only;
  mixed lines.
- Standard « Validate » of a supplier receipt (equipment or consumable) refused;
  physical inventory count correction of a consumable accepted; inventory adjustment
  creating a maintainable serial refused.
- Acquisition without purchase: each nature, partner rule, consumable entry measured
  (accounts and value), fixed-asset equipment without entry, handover value and date
  filled for a shareholder current account contribution.
- Borrowed / rented: no valuation layer; loan never invoiced; draft rent bills on 613500
  passing phase 1's rent check.
- Exit / return: sites proposed per third party; creation from the assistant; two sites
  for one third party; **two warehouses sharing one off-site stock**, each item back to
  its own origin; re-lending the same day refused, next day accepted.
- Restitution: possession line always stopped; insurance unchecked stays open; other
  equipment's lines untouched; refused if quantity left; equipment archived.
- Section 8 through ordinary pickings and the API, for every group including ownership
  managers: borrowed item delivered to a customer, rented item scrapped, owned equipment
  sold or returned to the supplier, lent-out item moved without operation, consumables
  to a lent-out stock: all refused.
- Protected link: API write of `equipment_operation_id` refused; forged context keys
  have no effect.
- Attachments: common documents on operation and picking; line photos on the right
  equipment; at exit, return and restitution too.

## 12. Server procedure, translations, manual

- `docs/phase2/README.md`: backup, `git pull`, script dry run, apply, update and tests
  with `deploy.sh` (phase 1 script made generic), interface checks. Open incoming
  pickings listed by the script must be received through operations after the update.
  One `odoo_web` for every database: no real production yet.
- `.po` from `--i18n-export`; FR / FA translations.
- Manual: phase 5 (operations, operator and approver profiles).

## Verified / not verified / hypotheses

- Verified in code: section 0.
- Not verified on artdubati_test: picking types and destinations, existence of the
  accounts 613500, 708300, 778000, 455100, 603200, open incoming pickings (the script
  lists them).
- Hypotheses, to be confirmed by tests: validating a purchase receipt in superuser mode
  keeps phase 1's purchase / bill matching; an existing order's receipt can be taken
  over and validated with our move lines; `address_id` can be set on creation;
  `stop()` keeps the invoiced periods; the move's `price_unit` drives the acquisition
  valuation as read in the code.

## Decisions taken (audit of revision 3, owner)

- Prior approval mandatory; `approved` state separate from execution.
- Free loan: existing approved loan contract → operator alone; new loan contract →
  approver; return / restitution of a free loan → operator alone.
- C17: nature « contribution to a shareholder current account » (455100); other
  contributions wait for C9.
- Consumable count corrections stay standard (Inventory / Administrator), never for
  serialised equipment.

## Criteria for the code audit (green light of 08/10/2026)

- The approval covers a complete snapshot of the commitments: partner, products,
  maximum quantities, prices, taxes, currencies, acquisition values, contract and
  dates. Any change, through the lines or the API included, invalidates it. The
  quantity actually received may be lower than the approved one: both are distinct
  fields.
- An existing loan contract accepts a new line from an operator alone only if it is
  active, a supplier contract, of the right company and owner, without incompatible
  overlap.
- Tests use four profiles: operator only, approver only, both roles, Inventory user
  without either group.

## Implementation notes (code of 08/10/2026, for the audit)

- Code: `models/equipment_operation.py` (operation, lines, contract lines to stop),
  `models/stock.py` (protected link on pickings and moves, `_check_equipment_operation`),
  `models/res_company.py` (settings), `security/`, `views/equipment_operation_views.xml`;
  tests `tests/test_operation.py` (32 new tests; phase 1 receipts now go through a
  purchase operation). 79 tests with `lartdubati_investor_home`.
- Buttons: « Submit for Approval » (operator), « Approve » (approver), « Execute »
  (operator; approves first when the user has both roles). Physical fields (serial
  numbers, condition, photos, responsible, executed quantity) are outside the snapshot.
- Deviations: a same-day re-lending is refused with a message naming the first
  possible day, instead of proposing it automatically; the approver group does not
  imply the operator group (four distinct test profiles); operators and approvers get
  read access to purchase orders, contracts and every equipment of their companies
  (record rule), needed to choose and check them in the form.
- Concurrency: the lock (`FOR UPDATE NOWAIT`) is tested by simulating PostgreSQL's
  refusal (a test transaction is never committed, so a second real cursor cannot see
  the operation); idempotence is tested directly.
- Not covered: receipts in two or three steps (input then stock): the operation sends
  the supplier move straight to its destination stock; to check if such a route is
  ever configured.
- Server: `docs/deploy_modules.sh` (phase 1 script made generic: backup, expected
  count, label), `docs/phase2/setup_phase2.py`, `docs/phase2/README.md`.

## Corrections after the code audit of e8aa06e

Each point has a test that fails on e8aa06e and passes now (88 tests in all):
1. Executed quantity: defaults to the approved quantity at creation and follows it while
   equal; an explicit 0 receives nothing for that line; all lines at 0 → nothing executed.
   Exit, return and restitution always move the whole equipment.
2. Non-stock equipment: no move for them except when their order line has an open
   receipt move; mixed operations build moves only for the lines that move; a service
   product (no receipt) is handled without picking.
3. Draft bill: built from the operation's order lines and executed quantities only
   (bounded by what is received or ordered and not yet invoiced); other billable lines
   of the order are never billed. Order line prices and taxes are in the snapshot.
4. « Bill already received » mode: the bills carrying the received order lines are
   linked (`bill_ids`); at least one is required. No accounting read right is given to
   the operator: the bills are found by the server.
5. Internal transfers of equipment: refused to a `virtual` place, and between two
   off-site stocks (only physical → lent-out by an exit, lent-out → physical by a
   return).
6. Contract lines to stop: `company_id` stored and multi-company record rule.
7. Contract lines changed after the approval (added, ended): refreshed at execution;
   the approval is cancelled and the execution stops without error (the cancellation is
   kept), the operation is back in draft for review.
8. Attachments: only files uploaded by the current user (not yet attached, or attached
   to this operation or its lines) and readable by them can be added; any other id sent
   through the API is refused before the elevated write. Common documents are copied on
   each transfer.
9. Receipts in several steps: refused by the operation (warehouse of the operation type
   not in one step, or receipt moves chained to other transfers) and by the setup
   script.
Also: the setup script filters products and locations by company; the company settings
check that products and locations belong to the company and that acquisition sources
are inventory locations; the tests fail with an explicit message when `l10n_fr_account`
is not installed (instead of an attempted installation inside the tests).

## Correction after the audit of 3e7c39a

« Bill already received » is checked on the lines really executed (executed quantity
> 0): a bill of a line received with 0 no longer justifies the mode; at least one bill
must carry an executed line, otherwise nothing is executed (and the execution also
refuses if none is found). Rule kept: at least one bill for the executed lines (one bill
per executed line would be a new business decision). Test added (fails on 3e7c39a);
89 tests in all.

## Fix after the deployment of 09/10/2026 (user form)

On artdubati_test the two groups were not visible in the user form, and the Maintenance
section had disappeared: Odoo shows a category as a drop-down list only when its groups
form a single chain, otherwise as check boxes reserved to developer mode. Each group now
has its own category (« Equipment Operations — Execution », « Equipment Operations —
Approval »); implied groups unchanged (operator implies Inventory / User; approver and
operator independent). Test `test_user_groups_view.py` (fails on 5ab6c36): both groups
give a visible `sel_groups_*` field, the Maintenance section is a drop-down list again.
Also: setup_phase2.py says « WILL » instead of « WOULD » with --apply. 91 tests.

## Fix of 09/10/2026 (2): menu position and form (owner's remarks)

Menu moved under Inventory → Operations → Transfers (first item). Form: transfer type
computed and hidden (`picking_type_id` computed, stored, editable in developer mode);
partner labelled after the choices; existing order fills vendor, destination and lines
(onchange); « Existing Order » by default; filtered lists and line columns per case.
Tests: transfer type per operation and from the order; lines loaded from an order
(Form). 93 tests. No change of the business rules: the server-side checks of section 6
are unchanged and still apply to any value sent.

## Corrections after the audit of 890a178

1. Transfer type of exits, returns and restitutions: taken line by line from the
   warehouse holding the equipment (type whose default source location contains it;
   for a return, whose default destination contains the return destination; most
   specific match), one transfer per type; never « the first type of the company ». The
   header field is only for receipts, where a missing match is an error (no blind
   fallback). Test with two warehouses for exit, return and restitution.
2. Products offered for an acquisition without purchase: maintainable or storable
   (non-stock equipment included).
3. Changing the order resets the destination stock to the new order's; test with two
   orders of two warehouses.
The three new tests fail on 890a178. 95 tests in all.

## Open decisions for the owner

- Members of the two new groups on artdubati_test (to give before the tests in the
  interface).

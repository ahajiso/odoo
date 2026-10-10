# Definitions: Investor Home and Stock Monitor

Status: design document, revisable. Version 1 validated by the owner on 03/10/2026.
Revision 2 (equipment data model, ownership, contracts) drafted on 07/10/2026,
pending owner validation. Points marked "to confirm" are open; points marked
"accountant" need the accountant's validation before the related development.

## Stock
A stock is a stock.location declared for the monitor: an internal location flagged
« Monitor Stock » (`is_monitor_stock`, phase 3; the place type alone no longer decides,
since every location has one). Attributes:
- place type: physical / off-site (held by a third party) / virtual (later); the type
  shown for a stock is the monitor stock's own (a shelf created under an off-site stock
  keeps the default « physical » as location type, its stock is still off-site);
- address: `address_id` from OCA `stock_location_address`, mandatory on every monitor
  stock (sub-locations inherit it for display only; the monitor and the access rules
  use the stored address of the stock itself);
- currency (`monitor_currency_id`, mandatory; company currency by default and for the
  stocks flagged at the phase 3 update);
- return location (off-site stocks only, mandatory): a stock inside a real warehouse
  where items go back.

Off-site stocks are internal locations of the company, placed OUTSIDE the warehouse
stock location, so that ordinary reservations never pick them: `Chez tiers`, child of
the warehouse root location, not of its stock location; one child location per third
party. On artdubati_test (warehouse « Bougival 1 », code Bg, root shown as WH):

    WH (warehouse root, view)
    ├── Bg/Stock
    └── Chez tiers
        ├── Customer A
        └── Partner B

Each quant (and each non-stock equipment through its monitor location) belongs to the
nearest monitor stock at or above its location (`parent_path`), never found through
`warehouse_id`. A lent-out location is always a monitor stock; an exit that creates one
gives it the site address (which needs a city and a country). An item in an internal
location under no monitor stock is shown to staff only, with the alert « Outside any
monitor stock ».
An employee is not a third party: equipment entrusted to an employee stays `owned`, in
a normal or job-site location, assigned through its responsible user and usage history.

## Item families
- Asset: maintenance.equipment, one record per physical item (quantity = 1).
  - Stock-managed asset: its product is tracked by serial number; `stock_lot_id` is
    mandatory and unique; its location and quant owner come from stock.quant.
    An internal serial number is generated when the manufacturer gives none.
  - Non-stock asset (vehicle, building, fixed installation): no lot; a monitor location
    is mandatory on the equipment and must be empty as soon as a lot exists.
  - Only archived historical equipment may have neither.
- Consumable: goods product with Track Inventory, quantity from stock.quant, no
  equipment record. Serial tracking optional.
  v1: consumables are always `owned`. A receipt of a consumable with a third-party
  owner is refused (constraint), because without a lot nothing tells a loan from a
  rental. Required for the next version: lot tracking for borrowed / rented consumables
  (e.g. scaffolding, props), with the ownership status on stock.lot and contract lines
  pointing to the lot.

## Sources of truth
| Information | Source |
|---|---|
| Product and category | product.product (equipment: OCA `maintenance_product.product_id`) |
| Serial number | stock.lot, linked by `maintenance.equipment.stock_lot_id` |
| Quantity and location | stock.quant (non-stock assets: equipment monitor location) |
| Legal owner | `maintenance.equipment.owner_partner_id`, synchronised with `stock.quant.owner_id` |
| Responsible / holder | `maintenance.equipment.owner_user_id` (label: "Responsible / holder") and OCA `maintenance_equipment_usage` |
| Supplier invoice line | OCA `maintenance_account.move_line_id` |
| Acquisition value, depreciation, net book value | account.asset (OCA `account_asset_management`), linked by `maintenance.equipment.asset_id` |
| Consumable valuation | stock valuation layers (average cost) |
| Rental, loan, insurance, maintenance agreements | OCA `contract`, one contract line per equipment |
| Repairs (repairer, invoice, cost) | purchase orders linked by OCA `maintenance_request_purchase` |
| Initial condition, photos, documents | chatter and attachments of the receipt |

The equipment field `partner_id` is the vendor, never the owner.

## Ownership status
`ownership_status`: owned | borrowed | rented | lent_out (stored, indexed, tracked) on
maintenance.equipment. Consumables are owned only in v1 (see Item families); the
monitor shows them as owned.
- owned: company property, in its stock.
- borrowed: belongs to a third party (possibly a shareholder), held for free.
- rented: belongs to a lessor, we pay rent.
- lent_out: company property, held by an external third party in an off-site stock,
  free or rented out.

Legal owner and quant owner must match:

| Status | `owner_partner_id` | `stock.quant.owner_id` | Physical presence |
|---|---|---|---|
| owned | `company_id.partner_id` | empty | internal stock |
| lent_out | `company_id.partner_id` | empty | off-site stock |
| borrowed | third party | same third party | internal stock |
| rented | lessor | same lessor | internal stock |

The company partner is never hard-coded. The quant owner is set on receipt move lines;
quants are never written directly. Consistency is checked by application code (on
positive quants of the serial number) when validating a receipt, an exit or a return,
on any ownership correction, and by a periodic integrity check. For non-stock assets
only `owner_partner_id` and the contracts apply.

The status is changed only by business actions, through one central method that checks
the user's group, writes the protected fields and logs the real author in the chatter:
purchase receipt, loan receipt, rental receipt, handover to a third party, return from
a third party, restitution to the owner, administrative correction. Manual edition is
reserved to the group "Equipment ownership managers". A stock move alone never changes
the status; moves are used to check physical consistency.

- Restitution of a borrowed or rented item: move to the owner's location, close the
  contract line, check no internal quantity is left, archive the equipment (it leaves
  the active monitor).
- Return of a lent_out item: move from the off-site stock to a warehouse, close the
  contract line or usage, status back to owned.

The former fields owner_type, acquisition_mode and accounting_ownership are removed in
favour of `ownership_status` and `owner_partner_id`.

## Equipment operations (receipt, exit, return, restitution)
Every entry, exit, return and restitution goes through a persistent business document
`equipment.operation` (revision of 08/10/2026, docs/phase2/PLAN.md), with its requester,
operator, approver, documents, per-line condition and photos, and the records it
created. Approval and physical execution are separate: the approver authorises the
commitments (snapshot invalidated by any later change of them), the operator executes
when the physical event happens; the stock is recorded on the execution date.
- Receipt, five branches: purchase (existing order, or order created and confirmed by
  the operation; bill already received and linked, or draft bill of the received lines
  only, with reference, date and PDF), acquisition
  without purchase (gift, contribution to a shareholder current account,
  regularisation; unit value mandatory, C17), borrowed (loan line, existing loan
  contract of the owner or new one), rented (rental line, draft bills), consumables
  (purchase and acquisition only, owned in v1). A validated receipt never leaves an
  equipment « to complete ».
- Exit to a third party (lent out): owner stays the company, move to an off-site stock
  (chosen among the third party's sites or created under the off-site parent), equipment
  and asset kept, customer contract line (draft invoices if rented out, none if free);
  the stock each item left from is recorded on the operation for its return.
- Return from a third party: back to the recorded origin, status owned, customer line
  stopped.
- Restitution to the owner: move to the owner, possession lines stopped, insurance and
  maintenance lines stopped only if the user confirms it, equipment archived.
- Supplier receipts and acquisitions, consumables included, are validated only through
  an operation; an equipment never enters or leaves the company, nor an off-site stock,
  without its operation; owned equipment cannot leave the company until the disposal
  operation exists (C18).
- Rights: « Equipment Operator » prepares and executes; « Equipment Operations
  Approver » approves orders, bills, rental lines, customer contracts, new loan
  contracts and acquisitions.

Equipment is created once, at receipt (the lot exists then; borrowed and rented items
have no purchase bill). When the supplier bill is posted, the equipment is linked to
its bill line through the common purchase line, and OCA `maintenance_account` only
creates equipment for bill lines without a matching receipt. Our `action_post()`
override depends on both `maintenance_account` and `account_asset_management`, so it
runs after both: it then fills `asset_id` from `move_line_id.asset_id` when `asset_id`
is still empty. A manual link set by an authorised user is never overwritten.

Warranty status (under warranty / no warranty / not applicable) and insurance status
(insured / not insured / not applicable) are chosen at receipt, unless a value is
explicitly configured on the product category. No silent default.

## Fixed assets tracked in stock (accountant)
Test choices (artdubati_test, not validated by the accountant, changeable at any
time; values and where to change them in docs/phase0/README.md): category
"All / Fixed Assets", average cost, manual valuation, expense account 215400; asset
profile "Matériel et outillage (test)" on 215400 / 281500 / 681120, linear 5 years,
prorata temporis, one asset per unit; rental expense account 613500.
Product categories flagged `is_fixed_asset_stock`. The flag is a declaration checked
per company, it changes nothing by itself:
- manual (periodic) valuation, so no stock journal entry at receipt;
- category expense account in class 21 carrying an asset profile;
- asset profile with `asset_product_item` enabled (one asset per unit);
- serial tracking for stock-managed products;
- profile and accounts belonging to the same company.
Quantity and location come from stock, financial value from account.asset. Their stock
valuation layers still exist and appear in the standard Odoo valuation report; the
monitor counts them as 0 in stock value. A separate "accounting stock valuation" action
excluding these categories may be added without changing the standard report.
Consumables keep automated valuation at average cost, standard stock accounts, and
never create assets.

## Contracts (OCA contract)
Each contract line about an equipment carries `equipment_id` and a nature:
rental | loan | insurance | maintenance. The direction comes from the contract type
(purchase = supplier, sale = customer): rent paid = rental on a supplier contract, rent
received = rental on a customer contract. Insurance is only allowed on supplier
contracts. One contract may hold several equipment, one line each, with its own amount.
- No overlap per equipment, nature and direction. Periods are closed intervals
  [start, end], as invoiced by OCA contract; an empty end means open-ended; cancelled
  or archived lines are ignored. A renewal closes the previous line and the next one
  starts the following day (OCA `contract_line_successor`).
- Free loans use a contract line without invoice recurrence; it must never produce an
  invoice, not even at zero.
- Contract lines must use non-maintainable service products, so that
  `maintenance_account` never creates equipment from rent or premium bills.
- Rent bills: normally generated as drafts by the supplier contract; the accountant
  reports the supplier's reference, attaches the PDF, checks and posts. A bill entered
  manually must let the user pick the contract line (`account.move.line.contract_line_id`,
  displayed by our module, filtered on supplier and company). Any bill line on the
  equipment rental account (613500, test choice, accountant) cannot be posted without a
  contract line.
- Insurance: insurer = contract partner, policy number = contract reference, dates,
  premiums, attachments, renewals. `insurance_status` stays on the equipment to tell
  "not insured" from "not applicable".

## Measures (per stock, in the stock's currency)
1. Quantity: number of assets, quantity on hand of consumables.
2. Inventory value (audience: store responsible): everything physically assumed to be
   in the stock, whoever owns it. Basis: acquisition value for owned and lent_out items
   (asset original value; consumables: average cost); replacement value for borrowed
   and rented items.
3. Accounting value (audience: accountant): net book value of company property only.
   - owned and lent_out: asset original value minus accumulated depreciation (assets);
     average-cost valuation (consumables). Fixed-asset categories count 0 in stock
     value, so nothing is counted twice.
   - borrowed and rented: 0.
4. Cost (rented items only): rent amount per period, period and start date from the
   active rental line of the supplier contract; cumulative rent paid = posted supplier
   bill and refund lines linked to the equipment's rental contract lines (refunds
   deducted).
For an asset the monitor shows separately: original value, net book value, replacement
value and its date.

Values as implemented in phase 3 (`lartdubati.stock.monitor`, docs/phase3/PLAN.md §3.4):
- inventory value: consumable = quantity × average cost; company equipment with a
  fixed asset = its original value; without one = its cost (phase 2f, provisional until
  the bill; unknown cost = no value and an alert, never 0); borrowed / rented =
  replacement value (none = no value and an alert);
- stock value (staff): what the stock valuation carries: quantity × average cost for an
  automated category, 0 for a manual one and for fixed assets;
- net book value (accountants): fixed asset = original value − posted depreciation (the
  salvage value is not deducted), provisional while the asset is a draft, 0 once
  removed; otherwise the stock value; borrowed / rented = 0 (C19, C20, C22);
- current rent (staff): the active rental line of the supplier contract, stored price ×
  quantity × (1 − discount), monthly equivalent by periodicity (daily and weekly: no
  equivalent, alert); rent paid (accountants): posted supplier bill and refund product
  lines linked to the equipment's rental lines, untaxed, refunds deducted (C21).
Equipment to complete (not integrated) is not in the monitor; staff see its count.

Costing method for consumables: average cost (AVCO), changeable later.

## Replacement value
Fields on the equipment: `replacement_value`, `replacement_currency_id`,
`replacement_value_date`. Mandatory for borrowed and rented items, optional otherwise.
Independent of insurance. A stored converted amount is added only once the currency
rule below is decided.

## Handover value (accountant, to confirm)
`handover_value` and `handover_value_date` stay on the equipment, never used
automatically in accounting, until the accountant states: legal meaning (transfer of
ownership, contribution in kind, or mere provision by a shareholder), date of transfer,
counterpart account (capital, 455 or other), VAT, required document.

## Taxes in labels
Every price or cost is untaxed and its label says so: « (HT) » in French, « (excl. tax) » in
English (owner's rule, 09/10/2026). A price entered tax included would say « (TTC) »; no
such entry exists today.

## Currency
Each stock is reported in its own currency. Totals are only ever summed within one
currency and shown grouped by currency. No consolidation in this version.
This holds in every interface (audit of 643f95e): the dashboard totals per currency; in
the standard views (pivot and its grand total, graph, grouped list, grouped export) a
group holding amounts in more than one currency shows no amount, whatever the grouping
chosen; the ungrouped list has no amount total.
Net book value, stock valuation and posted rents are in company currency at source.
Conversion to the stock's currency (phase 3, test choice C12): as
`res.currency._convert()` (company rate first, then the global one; the last rate on or
before the date, else the earliest later one, flagged « later rate used »), each amount
at its own date by default (fixed asset start, cost date, replacement value date, rent
start, each bill's accounting date; average cost at today), or every amount at today's
rate (setting). A currency without any rate gives no converted amount: the amount stays
in its own currency, outside the totals, with an alert (never Odoo's silent rate 1).

## Access
Access profiles (separate model, linked to users): any combination of allowed countries,
allowed stocks, allowed ownership statuses, allowed families (statuses and families are
small reference models so they can be used in many2many fields and translated).
Empty list = no restriction on that dimension. A user with no access profile sees
nothing. Enforced by record rules on the unified reporting model (SQL view exposing
company, stock, stock address, ownership status, owner, family...) and on every model
the monitor opens. Navigation from the monitor never uses sudo(). Restricted users get
a dedicated detail view rather than global rules on stock.quant that would break
Inventory.
Accounting value, original value, depreciation, rent paid and accounting entries carry
`groups=` restricted to the accounting group; cost is visible to the store group.
Phase 3: staff = Inventory / User or Accounting / Read-only; accountants = Accounting /
Read-only. Investors (internal users with the investor group, no Inventory group) read
text labels (product, stock, city, country...) denormalised in the monitor, never the
records behind them; every figure they may not read is absent from the dashboard, the
analysis views and exports (exports also need « Allow export »). The profile filters the
monitor rows (family, ownership, stocks and their sub-locations, country of the stock's
own address) and the internal locations (country of the monitor stock above them).
Investor accounts (phase 4, docs/phase4/PLAN.md §2): a user of « Stock Monitor
Investor » holds no other right than Internal User, what Internal User implies and
export (refused otherwise). Outside sudo, every model is refused to it except a short
list (the monitor, the home page, its own user, partner, company, currencies, languages,
settings, menus), narrowed by rules to its own records; the web client's mail and
filter models are readable with no record visible. It loads only four actions (home
page, dashboard, detailed analysis, « coming soon »), runs no server action, and sees
only the Stock Monitor menu. Its home page is the « Investor Home » screen of the
module.
Multi-company (audit of 643f95e): every user, investor or staff, sees only the monitor
rows of their active companies (global rule `company_id in company_ids`, ANDed with the
profile rule), in the dashboard, the analysis views and exports.
Move lines (decided after the audit of 888d229, phase 2f): standard stock gives every
internal user read, write, create and delete on all of them. An investor without
Inventory / User has no access at all to them; an equipment approver without
Inventory / User reads only those of the equipment operations and writes none. Both
through global rules computed per user; users with Inventory / User keep the standard
rights.

## Custom fields kept (everything else comes from standard or OCA)
- maintenance.equipment (phase 2f, 09/10/2026):
  - cost: `cost` (company currency) is meaningful only when `cost_known` is set;
  - `cost_date`, `cost_provisional`, `cost_source` (order, bill, bill_cancelled,
    bill_released, acquisition, migration, manual) and `cost_reference`;
  - order estimate (after discount, per product unit) at receipt, provisional; real cost
    `abs(balance) / quantity` at bill posting; corrected only through the wizard of
    Accounting / Administrator;
  - responsible (`owner_user_id`) required for an integrated equipment: an active
    internal user of the company, no « not assigned ».
- equipment operations (phase 2f): the approval freezes the planned accounting
  treatment of each line (account of the future bill line, asset profile, valuation,
  category, fiscal position). The approver reads only the operation and the documents
  it refers to.
- maintenance.equipment: ownership_status, owner_partner_id, stock_lot_id, asset_id,
  replacement_value, replacement_currency_id, replacement_value_date, warranty_status,
  insurance_status, monitor location for non-stock assets (former current_location_id,
  relabelled), handover_value and handover_value_date (temporary).
- stock.location: place type, currency, return location (address from OCA).
- product.category: is_fixed_asset_stock, optional default warranty / insurance status.
- contract.line: equipment_id, nature.
- Access profile model and its reference models.
Removed from maintenance.equipment: owner_type, acquisition_mode, accounting_ownership,
ownership_state, rental_counterparty_id, rental_end_date, accounting_depreciation_active,
physical_wear_active, return_obligation, initial_condition.
Removed from maintenance.request: repairer, repair_invoice_ref, repair_cost (replaced by
linked purchase orders and their bills).

## Hypotheses to confirm by tests
The integration with OCA modules (order of the `action_post()` overrides, one asset per
unit with `asset_product_item`, no duplicate equipment from `maintenance_account`, free
loan producing no invoice) is a design assumption until Odoo integration tests confirm
it. List and status in CLAUDE.md.

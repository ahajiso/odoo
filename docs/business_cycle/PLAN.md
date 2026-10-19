# Business-cycle acceptance before AI — plan revision 1

Status: **plan only, submitted for audit**. No user, access right, business record,
module or server configuration is changed by this revision.

Date: 19/10/2026. Target database: `artdubati_test` only. Production remains out of
scope and blocked by the isolation and rebuild decisions recorded in `CLAUDE.md`.

## 1. Goal and meaning of “complete cycle”

The owner wants named test profiles and an end-to-end business acceptance before the
AI work continues. The intended path is:

1. express a business need;
2. create the missing item or service through the governed catalogue;
3. authorise and place the purchase;
4. receive it physically;
5. check the supplier bill and the accounting result;
6. move the item out of the warehouse and record its use;
7. read the result as warehouse staff, accounting staff and shareholder;
8. perform every step from the applicable FR/EN/FA manual card;
9. correct the defects found, then replay the affected scenarios.

“Validated” means that each positive and negative step is performed with the named
role, never with Administrator or the combined historical `Test` account. A successful
action with an over-privileged account is not evidence for a business role.

## 2. Facts established before this plan

### 2.1 Supported today

- `product.creation.request` governs creation of products and services. Requesters are
  equipment operators, Purchase users and Inventory users. A distinct Product
  Catalogue Manager approves and executes requests made by another user.
- `equipment.operation` governs equipment and consumable receipts. Equipment Operator
  and Equipment Operations Approver are independent roles. A purchase receipt can use
  an existing confirmed purchase order or, after approval, create and confirm one.
- Equipment Operator implies Inventory / User. Internal transfers between internal
  physical stocks remain standard Odoo transfers.
- Vendor bills, assets, contracts and the stock monitor are linked for the paths already
  implemented and tested by the modules.
- A Stock Monitor Investor is deliberately incompatible with Inventory, Purchase,
  Accounting and administration rights and requires a Stock Access Profile.

### 2.2 Not supported as a complete business flow today

- A product creation request is **not** a purchase request. Its implementation states
  that it never creates a bill, order or stock move. There is no general business-need
  document for services and ordinary purchases before the RFQ.
- The controlled equipment operation can create a purchase order for a physical receipt,
  but this is not a generic service-purchase approval flow and it does not give the
  Purchasing Manager a mandatory step.
- Worksite consumption of materials is not implemented (`docs/ROADMAP.md`, phase G).
  A standard internal transfer can prove movement to an internal job-site location, but
  it cannot prove consumption, cost attribution to a worksite, surplus return or loss.
- A dedicated least-privilege “business requester / site requester” group does not
  exist. Giving such a user Purchase, Inventory or Equipment Operator rights solely to
  submit a catalogue request would grant unrelated operational rights.

The acceptance is therefore split into a **supported cycle** and **gap scenarios**.
It must never report the latter as validated until their design is decided and built.

## 3. Test profiles

All accounts are internal users of the single company. Names below are stable role
labels, not passwords. Logins and temporary passwords are supplied outside Git. No
password, invitation token or personal e-mail is stored in the repository or logs.

Before creation, an audited read-only characterisation resolves every external ID on
the installed server, expands implied groups, and records the menus and model rights.
The creation script then has a dry-run mode and an explicit `--apply` mode. It refuses
any database other than `artdubati_test`, existing users with unexpected rights, and
any incomplete profile.

| ID | Test profile | Groups to assign explicitly | Purpose and exclusions |
| --- | --- | --- | --- |
| P1 | Warehouse Manager | `maintenance_shareholder_equipment.group_equipment_operator`, `stock.group_stock_manager` | Manages stock and executes equipment operations. No purchase, catalogue approval, equipment approval, accounting or investor role. |
| P2 | Warehouse Operator | `maintenance_shareholder_equipment.group_equipment_operator` | Proves the daily path with Inventory / User only (implied). Cannot configure Inventory or approve commitments. Recommended in addition to P1. |
| P3 | Purchasing Manager | `purchase.group_purchase_manager` | Creates/checks RFQs and purchase orders. No catalogue approval, stock execution, equipment approval, accounting or investor role. |
| P4 | Product Catalogue Manager | `maintenance_shareholder_equipment.group_product_catalogue_manager` | Approves and executes requests made by other users. Never receives `group_product_catalogue_autonomous`. No Purchase or Inventory right is added merely to expose its own Catalogue app. |
| P5 | Equipment Operations Approver | `maintenance_shareholder_equipment.group_equipment_approver` | Read-only outside approval scope; approves commitments but cannot execute stock. |
| P6 | Accountant | `account.group_account_invoice`, `account.group_account_readonly` | Checks and posts ordinary supplier bills and reads accounting monitor columns. No Inventory, Purchase, equipment-operation or investor role. Whether these two exact groups are sufficient on the installed Odoo/OCA platform is an audit assertion, not an assumption. |
| P7 | Shareholder / Investor | `lartdubati_investor_home.group_stock_investor` plus one Stock Access Profile | Sees only Investor Home and the scoped stock monitor. Any unrelated group makes setup fail. |
| P8 | Business / Site Requester | **Missing least-privilege group; do not create yet** | Needed for the target flow. Must be able to submit its own item/service and purchase needs without receiving Purchase, Inventory or catalogue approval rights. |

### 3.1 Optional exceptional profile

P9, Accounting Administrator (`account.group_account_manager`), is created only if the
acceptance includes exceptional cost correction or replacement of a cancelled one-off
rental bill. It is not used for ordinary invoices and is never combined with P6 in the
evidence.

### 3.2 Why the extra profiles are required

The four roles requested by the owner (warehouse manager, purchasing manager,
shareholder and accountant) cannot alone demonstrate the current controls:

- P4 is required because the requester must not approve its own catalogue request;
- P5 is required because approval and physical execution of equipment operations are
  separate;
- P2 proves that daily warehouse work does not need Inventory Administrator;
- P8 is required by the target organisation, but its safe rights do not exist yet.

The superuser, Administrator and Autonomous Catalogue Manager are control accounts,
not business actors. They must not perform a positive acceptance step.

## 4. Language and access-profile matrix

- Every account starts in French for the reference run.
- The critical screen of each role is repeated in English and Persian by changing the
  user language, saving, signing out and signing in again.
- Persian checks include RTL layout, button order, date/amount readability and exact
  menu/field labels.
- P7 receives a deliberately restricted profile (initial proposal: `Bg/Stock`, owned
  and rented, equipment and consumables). The same account is tested temporarily with
  no profile (zero rows and warning), then restored.
- P7 must see neither accounting-only columns nor any staff menu. P6 must see the
  accounting value and posted-rent columns. P1/P2 must see the operational cost fields
  but not gain accounting administration.

## 5. Acceptance data and cleanup

Every created record uses the prefix `RECETTE-METIER-20261019` and fictitious contacts,
references, serial numbers and attachments. No real supplier is contacted and no real
payment is made.

The acceptance uses a new, small dataset rather than editing the records used by the
one-off-rental evidence. Accounting records are never deleted after posting. Cleanup
archives the test users and reversible master data; posted documents remain as clearly
labelled test history. The setup report lists every created record and its final state.

## 6. Scenario matrix

### S0 — profile and segregation baseline

For P1 to P7, record explicit and implied groups, visible applications/menus and a
model-rights probe. Verify forbidden combinations and negative actions. In particular:

- P4 cannot approve its own request and has no Autonomous Catalogue role;
- P5 cannot edit or execute the operation it approves;
- P2 cannot approve an operation;
- P3 cannot receive stock or post a bill;
- P6 cannot change stock, approve an operation or create a purchase order;
- P7 sees only the Investor home/monitor and cannot call staff actions;
- no business account has Settings / Administration.

### S1 — governed catalogue request

P2 submits one missing consumable and one missing durable equipment item. P4 reviews,
refuses an intentionally incomplete request, then approves and executes the corrected
request. Verify duplicate detection, accounting/category treatment, attachments,
requester/approver/executor trace and rejection of self-approval.

A service request is also tested (telecom or insurance test service) to validate the
catalogue form, but it stops after product creation because the general service
purchase/contract approval phase is not implemented.

### S2 — purchase prepared by Purchasing Manager

P3 creates and confirms an RFQ/PO for the accepted physical item. Verify supplier,
currency, taxes, quantity, unit, untaxed labels and order trace. P1/P2 can read/select
only what the receipt requires; they do not edit the confirmed order's lines or price.

This proves the current **existing-order** branch. It does not prove that the initial
business need was approved before P3 created the RFQ; that is gap G1 below.

### S3 — controlled receipt

P2 prepares a purchase receipt operation linked to the confirmed order and requests a
draft supplier bill. P5 approves the frozen commitments. P2 executes the physical
receipt. Verify exactly one completed transfer, expected quantity, lot/serial where
applicable, equipment creation for the durable item, provisional/final cost source,
and exactly one draft bill. Direct validation of the supplier receipt outside the
operation must be refused.

Also run a second small scenario where an approved equipment operation creates and
confirms the purchase order itself. This characterises the alternative current flow;
the audit decides which branch is the business reference because the actors differ.

### S4 — supplier bill and accounting visibility

P6 checks the order/receipt/bill match, supplier reference, attachment, date, taxes,
expense or asset treatment and posts the test bill. No payment is made. Verify that P6
can read the accounting columns of the monitor, including the previously open
`rent_paid` control, and that P1/P2/P7 cannot see accounting-only details.

Fixed-asset posting is performed only with a category/profile explicitly approved as a
test choice and recorded in `docs/QUESTIONS_COMPTABLE.md`. The Mac Mini correction is a
separate named scenario, never silently folded into this generic acceptance.

### S5 — warehouse exit and use: supported boundary

For a stock item, P2 performs a standard internal transfer from `Bg/Stock` to a test
internal job-site location and verifies the quant/serial destination. For durable
equipment, characterise and test the installed OCA usage history and the responsible /
holder assignment without directly rewriting ownership.

Then stop at the actual boundary:

- do not describe an internal transfer as consumption;
- do not invent an analytic/worksite cost entry;
- do not follow the current CH-01/CH-02 instruction to edit the equipment location if
  the item is stock-managed;
- record return to warehouse through a standard internal transfer.

The missing consumption/return-of-surplus/loss flow is gap G2.

### S6 — monitor and investor result

P1/P2, P6 and P7 inspect the same resulting stock in their respective views. Verify
quantity, ownership, inventory value, accounting value visibility, currencies, exports,
Detailed Analysis and scope restrictions. Repeat P7's existing home-page and menu
security smoke test to detect regressions.

### S7 — manuals and browser acceptance

Each actor follows the manual rather than an unpublished instruction. For every step,
record: card code, language, displayed menu/field label, actual result and discrepancy.
Links must use XML IDs, never database record IDs. Run `refresh.py`, `check.py`, desktop,
mobile and Persian RTL checks after corrections.

### S8 — replay and final regression

After fixing defects, rebuild the local database on the exact 122-module platform,
run the full module suites and route comparison, deploy only through the controlled
test procedure, and replay every failed scenario with fresh test references. A fix is
not accepted solely because the original record now works.

## 7. Manual conformity audit baseline

`lartdubati_manual/tools/check.py` currently passes: FR, EN and FA have the same card
codes, references, numbers and step counts. This is only a structural result.

The semantic audit already finds blocking contradictions in the published manual:

- CH-01 and CH-02 direct the user to edit “Current Location”; this is not a stock move
  and cannot be the instruction for a stock-managed serial item;
- several PARC, REF and CPT cards still use removed concepts such as acquisition mode,
  accounting ownership and the former ownership fields;
- the “Who reads what” table does not describe Purchasing Manager, Product Catalogue
  Manager or Equipment Operations Approver as separate roles;
- the current request, approval, execution and internal-transfer paths are not presented
  as one end-to-end role-separated procedure.

Therefore the manuals are **not yet conformant**, despite the green structural checker.
The manual correction is part of this acceptance, in FR first and then EN/FA, and is a
blocking exit criterion. New user profiles affect the prerequisites and “Who reads
what”; a truly new business profile/page follows the impact matrix in
`docs/manual/definitions-manuel.md`.

## 8. Gaps and decisions before calling the full objective complete

| Gap | Severity | Decision proposed |
| --- | --- | --- |
| G1 — no generic business purchase request/approval before RFQ | Blocking for “request-to-purchase” | Characterise Odoo/OCA `purchase_request` first. Either adopt it with requester/approver separation or design a minimal controlled request. Do not misuse a catalogue request as spending approval. |
| G2 — no worksite consumption document | Blocking for “to use/consume” | Implement ROADMAP G after accountant decision on consumable valuation. Until then validate only internal transfer and equipment assignment/usage. |
| G3 — no least-privilege requester group | High | Add a dedicated requester role together with G1; it may create/read its own requests only. Do not grant Purchase or Inventory as a shortcut. |
| G4 — manuals semantically obsolete | High and blocking for final acceptance | Rewrite the affected FR cards, align EN/FA, regenerate, check and replay them with the role accounts. |
| G5 — accounting choices still open (Mac Mini, C24/C25 and category treatment) | Scenario-specific blocker | Keep explicit test choices configurable and obtain accountant validation before any real accounting use. |
| G6 — shared transitional test service | Production blocker | Allowed only for `artdubati_test` under the owner's disposable-production decision; isolation and production rebuild remain mandatory. |

## 9. Execution order and stop rules

1. Audit this plan and decide G1/G2 scope.
2. Write the read-only platform/profile characterisation and profile-creation plan.
3. Audit the script and exact groups; then back up `artdubati_test`.
4. Dry-run profile creation; review explicit and implied rights.
5. Apply P1–P7 only; set temporary passwords outside the script.
6. Run S0. Any excessive right stops the acceptance and removes/archives the affected
   account before continuing.
7. Run S1–S6 with screenshots and structured evidence.
8. Correct the manuals and defects; audit every code or security change before deploy.
9. Run S7–S8.
10. Decide/implement G1 and G2, or explicitly narrow the declared business scope.

Rollback is mandatory after a failed module update or security migration. Functional
test data is not “rolled back” by deleting posted accounting history; it is labelled,
archived where possible and listed in the report.

## 10. Exit criteria before resuming the IA programme

- every P1–P7 account has the audited minimal rights and passes its negative tests;
- catalogue request, purchase, receipt, bill and internal transfer/usage scenarios pass
  with distinct actors;
- G1 and G2 are either implemented and accepted, or the owner explicitly records that
  the pre-IA milestone is limited to the supported boundary;
- the accountant monitor column previously left open is checked with P6;
- all applicable manual cards are factually correct in FR/EN/FA and work from their
  published links in desktop/mobile/RTL;
- no unresolved severity-blocking or severity-high defect remains;
- full tests, platform parity, HTTP-route comparison, backup/restore proof and final
  browser replay are green on `artdubati_test`;
- production remains untouched.

## 11. Evidence used for revision 1

- `maintenance_shareholder_equipment/security/security.xml`
- `maintenance_shareholder_equipment/security/ir.model.access.csv`
- `maintenance_shareholder_equipment/models/product_creation_request.py`
- `maintenance_shareholder_equipment/models/equipment_operation.py`
- `lartdubati_investor_home/security/security.xml`
- `lartdubati_investor_home/models/investor_security.py`
- `docs/DEFINITIONS.md`, `docs/ROADMAP.md`
- `docs/one_off_rental/LIVE_ACCEPTANCE_20261018.md`
- the published FR manual and the manual maintenance/impact rules


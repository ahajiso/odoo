# Phase 2f plan – corrections to phase 2 (audit of 09/10/2026)

Status: revision 2 (09/10/2026). No code written.
- Revision 1 was audited with phase 3 revision 3. This revision integrates its
  corrections:
  - A1, equipment cost (§2);
  - A2, accounting treatment (§3);
  - A3, approver's rights (§4);
  - C2, all candidate stocks (§6);
  - C3, existing equipment corrected before deployment (§5).
- The audit announced the green light for the 2f development once they are
  integrated, then an audit of the code before deployment.

Scope: `maintenance_shareholder_equipment` 18.0.3.1.0, and `lartdubati_investor_home`
18.0.1.6.0 (its bill-to-equipment cost hook moves to module 1). Deployed on
artdubati_test **before** phase 3, whose monitor reads the responsible, the cost and its
provisional flag.

Origin: the general audit of the existing code, after the owner's first real receipt
(EQOP/2026/0159, equipment 484, serial 1234):
- the equipment was integrated without a responsible;
- its product is in category « All »: the draft bill is on 607000, with no asset
  profile, so posting it will create no asset;
- the approver can write the operation header.

## 0. Facts checked in the code

Equipment and operations (maintenance_shareholder_equipment):
- `maintenance.equipment._integration_missing()` (maintenance_equipment.py:221) lists
  what an integrated equipment must have. It feeds `action_finalize_integration` and the
  constraint `_check_integrated_complete`. The responsible (`owner_user_id`) is not in
  it.
- `@api.constrains` runs only when one of its trigger fields is written, and never on
  existing data at module update.
- The receipt line's `responsible_user_id` is copied to `owner_user_id`
  (equipment_operation.py:1411) and is optional.

Cost:
- Equipment `cost` is set only for equipment created from a bill, by
  `lartdubati_investor_home/models/account_move_line.py`: `abs(balance) / quantity`,
  without a date. Equipment created by a receipt has no cost.
- At bill posting, `_reconcile_equipment()` (account_move.py:146) links the received
  equipment to the bill line, before `_fill_equipment_assets()`.

Account of a supplier bill line (Odoo 18):
- `account.move.line._compute_account_id` (account_move_line.py:553) takes the
  product's expense account through `get_product_accounts(fiscal_pos=…)`, so the fiscal
  position maps it.
- `stock_account` replaces it with the **stock input account** for a storable product
  with automated valuation under Anglo-Saxon accounting (stock_account/models/account_move.py:266).
- `purchase.order.line._prepare_account_move_line()` (purchase_order_line.py:572) gives
  the values of a bill line from an order line.
- OCA `account.account.asset_profile_id` makes a posted line create an asset.

Access rights:
- The approver gets read and write on `equipment.operation`
  (security/ir.model.access.csv, line 4). `action_approve` writes as superuser after
  `_is_approver()` (equipment_operation.py:396-410).
- `_check_user_access()` is called only by `action_execute` (line 476).
- Read rights of a plain internal user (`base.group_user`, the approver's only base
  group):
  - present: stock.location, stock.picking.type, stock.warehouse, product, product
    category, uom, account.tax, account.account, account.fiscal.position,
    maintenance.equipment, res.users, res.currency;
  - **absent**: purchase.order, purchase.order.line, stock.lot, stock.picking,
    stock.move, contract.contract, contract.line, account.asset.profile.

## 1. Point 9 – responsible required
- Add « responsible » to `_integration_missing()`: an `owner_user_id` that is an
  **internal** user (not share), **active**, and **allowed in the equipment's company**
  (`company_id in user.company_ids`).
- Receipt line: `responsible_user_id` becomes required for equipment lines at submit
  (`_check_values_receipt`), with the same three conditions, and its domain is limited
  to the internal active users of the company.
- No « not assigned » value (D6).
- **Existing data (C3)**: the constraint does not run on existing records, so their
  correction is mandatory before the deployment:
  - the 2f precheck (§5) refuses to deploy while an integrated equipment has no valid
    responsible;
  - `setup_phase2f.py --apply` sets the responsibles chosen by the owner (D1) before
    the update.
- Tests:
  - integration refused without a responsible, with a portal user, with an archived
    user, and with a user outside the company;
  - submit refused on a receipt line without a responsible;
  - the receipt copies the responsible;
  - the precheck query finds an equipment created without a responsible.

## 2. Equipment cost with date and provisional flag (correction A1)

New stored fields on maintenance.equipment, protected like the ownership fields
(written by business methods, or corrected by « Equipment ownership managers » with
`cost_source = manual` and a chatter trace):
- `cost_date` (Date);
- `cost_provisional` (Boolean);
- `cost_source`: order | bill | acquisition | manual.

The existing `cost` column (Float, company currency) keeps its type: the phase 3 view
reads it (phase 1 rule).

| Case | `cost` | `cost_date` | provisional | source |
|---|---|---|---|---|
| Receipt before bill (purchase) | order line unit price, untaxed, after discount, converted from the order currency at the receipt date (`_convert`, company of the order) | date the receipt is done | yes | order |
| Bill before receipt (equipment created from the bill by maintenance_account) | `abs(balance) / quantity in the product's unit` of the bill line | accounting date of the bill | no | bill |
| Bill posted after receipt | the estimate is replaced by `abs(balance) / quantity` of the line the equipment is reconciled with (`_reconcile_equipment()`) | accounting date | no | bill |
| Partial bill | only the equipment reconciled with the billed quantity get the real cost; the others keep the estimate | | | |
| Bill reset to draft or cancelled | the amount stays and becomes provisional again until a bill is posted again (source `order` if the equipment has an order line, otherwise `bill`) | unchanged | yes | order or bill |
| Acquisition without purchase | line `unit_value`, converted from the operation currency at the execution date | execution date | no | acquisition |
| Borrowed / rented | none (the monitor uses the replacement value) | | | |
| Owned with no source found | NULL, never 0; the monitor raises `alert_cost_missing` | | | |

- `balance` is already in company currency at the bill's rate, so a foreign-currency
  bill needs no other conversion.
- The bill-to-equipment hook of `lartdubati_investor_home/models/account_move_line.py`
  moves to `maintenance_shareholder_equipment`, so that the cost has one owner.
- Migration (post-migrate 18.0.3.1.0):
  - integrated equipment with a posted bill line: cost from that line, final;
  - otherwise, from the receipt move's `price_unit` (company currency, provisional,
    receipt date);
  - otherwise NULL, listed by the setup script.
- Tests:
  - order price different from the bill price (estimate, then real);
  - bill before receipt and receipt before bill;
  - order and bill in a foreign currency, with different rates at receipt and bill
    dates;
  - partial bill (two units, one billed);
  - acquisition without purchase;
  - bill reset to draft;
  - migration of an equipment with and without a bill.

## 3. Point 10 – accounting treatment shown in the receipt (correction A2)

- Computed field `accounting_treatment` (text) on each line of a receipt that brings
  **company property**: purchase, and acquisition without purchase. It is shown on the
  line sheet and in the approval summary.
- The account is the one the future bill line will actually use, under the current
  configuration:
  - **existing order**: an in-memory supplier bill (`account.move.new`, type
    `in_invoice`, partner, company, the order's fiscal position) with one line built
    from `purchase_line._prepare_account_move_line()`; its computed `account_id` is
    read. This runs Odoo's own resolution: product or category account, fiscal position
    mapping, and the stock input account of `stock_account`;
  - **new order**: the same in-memory bill, with the partner's fiscal position as the
    order would get it (`account.fiscal.position._get_fiscal_position(partner)`) and a
    line on the product.
  - Nothing is saved: `new()` records only.
- Wording, from the account found:
  - the account has an `asset_profile_id`: « Under the current configuration, posting
    the bill will create a fixed asset (profile <profile>, account <account>) »;
  - storable product with automated valuation: « Under the current configuration, the
    value will be carried by the stock (account <account>); no fixed asset »;
  - any other account: « Under the current configuration, the bill line will use
    account <account>; no fixed asset will be created automatically ». The account is
    named, never labelled as an expense.
- Acquisition without purchase: no bill exists, so the text says « No bill: if this
  equipment must be capitalised, the fixed asset is created manually by the accountant »
  and names the category's accounts.
- Confirmation `no_asset_confirmed` (« I confirm this equipment will not create a fixed
  asset automatically »):
  - required only on lines of company property (purchase, acquisition without
    purchase) whose treatment creates no asset;
  - never for borrowed, rented or consumable lines.
  It is part of the approval snapshot, so a change after approval invalidates the
  approval.
- The computed text is `compute_sudo=True`: it reads the account and the asset profile,
  which the operator may not read, and only displays their names. It grants no access
  to them.
- Tests:
  - the three wordings, including a manual-valuation category whose account carries an
    asset profile (asset, not expense);
  - fiscal position mapping the account;
  - automated valuation giving the stock input account;
  - acquisition wording;
  - confirmation required for a purchase without asset, not for a borrowed or rented
    line;
  - snapshot invalidated by a change of product after approval.

## 4. Point 11 – approver separated from the operator (correction A3)

- `equipment.operation` ACL for the approver: **read only** (`1,0,0,0`), as on its
  lines and stop lines. Approval, rejection and reset to draft stay methods that check
  the group, then write as superuser.
- `_mail_post_access = "read"`, so the approver can post in the chatter.
- **Minimal read ACLs** for `group_equipment_approver`: read only, no write, create or
  unlink, and no Inventory group. They cover what an operation shows or references and
  `base.group_user` cannot read:
  - purchase.order;
  - purchase.order.line;
  - stock.lot;
  - stock.picking;
  - stock.move;
  - contract.contract;
  - contract.line.
  Multi-company record rules of those models still apply.
  Locations, transfer types, products, taxes, currency and users are already readable
  by internal users (§0).
- `_check_user_access()` is called at **submit, approve and execute**. It also checks:
  - line taxes;
  - the operation's and the order's currency;
  - order lines;
  - responsible;
  - parent of off-site stocks;
  - replacement currency.
- Tests (Python):
  - approver: cannot write the header (AccessError), can approve, reject and post a
    message;
  - operator: cannot approve;
  - a user with both roles can do both;
  - an investor without Inventory rights can neither read nor create operations;
  - an unreadable referenced record blocks submit, approve and execute.
- **Interface test (tour, HttpCase)** with an approver-only user (`base.group_user` +
  approver):
  - open the operation list;
  - open a complete purchase receipt (order, lines with taxes, responsible, lot,
    destination, accounting treatment);
  - read every tab and line sheet without an access error;
  - approve;
  - check the state.
  Same tour for the operator, without the approve button.
- Interface checks on artdubati_test with four real profiles (Playwright, passwords
  given by the owner and never stored): operator only, approver only, both, investor
  without Inventory rights.

## 5. Deployment
- `docs/phase2f/precheck.sh` (read-only psql) exits 1, and stops the deployment, when:
  - an active integrated equipment has no responsible, or an inactive, portal or
    other-company responsible (C3);
  - an open receipt was not created by an operation (D4 not decided).
- `docs/phase2f/README.md`:
  1. backup of the database and filestore;
  2. `setup_phase2f.py` (dry run, then `--apply`: D1 responsibles, D3, D4 per the
     owner's answers);
  3. `precheck.sh`, which must pass;
  4. `git pull`;
  5. `deploy_modules.sh <dump> <count> phase2f`;
  6. interface checks.

## 6. Data to prepare (read-only queries, owner decisions)

| # | Item | Query (read-only) | Decision (audit's recommendation) |
|---|---|---|---|
| D1 | Equipment 484 (serial 1234) and any integrated equipment without a responsible | `select id, name, owner_user_id from maintenance_equipment where integration_state = 'done' and active and owner_user_id is null;` | the owner names the responsible |
| D2 | Address of **every candidate monitor stock**: `Bg/Stock`, `TBER/Stock`, `TIST/Stock`, every `lent_out` location (C2) | `select l.id, l.complete_name, l.place_type, l.address_id, p.city, p.country_id from stock_location l left join res_partner p on p.id = l.address_id where l.usage = 'internal' and l.active and (l.id in (select lot_stock_id from stock_warehouse) or l.place_type = 'lent_out') order by l.complete_name;` | structure each address (city, country) and set it on each stock |
| D3 | Active incomplete equipment named « Test » | `select id, name, integration_state, stock_lot_id, create_date from maintenance_equipment where name ilike 'test%';` | delete it, or archive it if a move references it |
| D4 | Open receipt Bg/IN/00004 | `select p.id, p.name, p.state, p.origin, p.equipment_operation_id from stock_picking p where p.name = 'Bg/IN/00004';` | cancel it if it is test data, otherwise take it over through an operation |
| D5 | Account with both « Investor » and Inventory rights | `select u.id, u.login from res_users u join res_groups_users_rel r on r.uid = u.id join ir_model_data d on d.res_id = r.gid and d.model = 'res.groups' and d.module = 'lartdubati_investor_home' and d.name = 'group_stock_investor' where u.stock_access_id is null;` (investors without a profile; their other groups are checked on the user form) | remove « Investor » from that account, unless an investor profile is explicitly needed |
| D6 | « Not assigned » responsible allowed? | — | no |

The old monitor's totals are not used for any check; its reports are removed in
phase 3.

## 7. Verified / not verified
- Verified in the code: section 0.
- Not verified (server):
  - the answers to D1 to D5;
  - the fiscal positions used with the suppliers;
  - whether Anglo-Saxon accounting is enabled on the company (it decides the stock
    input account);
  - the asset profiles on accounts other than 215400.

# Phase 2f plan – corrections to phase 2 (audit of 09/10/2026)

Status: revision 3 (09/10/2026), **development authorised** by the audit of 24d9027 (D7
and D8 accepted), with three precisions integrated below:
- order discount in the estimated cost (§2);
- `bill_released` distinct from `bill_cancelled` (§2);
- reliable fetch and script paths in the README (§5).
- The audit of revision 2 accepted P9, P10, P13 and D6, and asked for five corrections
  before the green light:
  - cost known explicitly (§2);
  - treatment frozen in the approval (§3);
  - possible deployment order (§5);
  - filtered dashboard domain and rates without a PostgreSQL function (phase 3 plan);
  - the scope of the approver's read rights (§4).
- They are integrated here and in docs/phase3/PLAN.md §1c.
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
- Phase 1 removes these links in two cases:
  - `button_cancel()` (account_move.py:305) unlinks every equipment of the bill;
  - `_release_excess()` (line 195) unlinks equipment when a draft bill's quantity is
    lowered.
  After that, `move_line_id` no longer says where the cost came from.
- A Float field reads back as 0.0 whether the column is NULL or 0: the ORM gives no
  reliable « unknown » for `cost`.

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

## 2. Equipment cost with date and provisional flag (corrections A1 and 1)

New stored fields on maintenance.equipment. They are protected: written only by the
business methods below or by the correction wizard.
- `cost_known` (Boolean, default False): the only test of « cost known ».
- `cost_date` (Date);
- `cost_provisional` (Boolean);
- `cost_source`: order | bill | bill_cancelled | bill_released | acquisition | migration | manual;
- `cost_reference` (Char): the document that explains the cost, e.g. « P00165 line 1 »,
  « Fr1223 », « Fr1223 (cancelled) », kept even after `move_line_id` is removed.

The existing `cost` column (Float, company currency) keeps its type, because the
phase 3 view reads it. Whenever `cost_known` is False, `cost` is ignored: the view
gives NULL. A real zero (`cost_known` True and `cost = 0`) stays 0.

| Case | `cost` | `cost_date` | provisional | source |
|---|---|---|---|---|
| Receipt before bill (purchase) | order line unit price, untaxed, **after discount** (`price_unit × (1 − discount / 100)`), then **per product unit** (`product_uom._compute_price(…, product.uom_id)`), converted from the order currency at the receipt date (`_convert`, company of the order) | date the receipt is done | yes | order |
| Bill before receipt (equipment created from the bill) | `abs(balance) / quantity` with the quantity converted into the product's unit (`product_uom_id._compute_quantity(quantity, product.uom_id)`) | accounting date | no | bill |
| Bill posted after receipt | the estimate is replaced as above, through `_reconcile_equipment()` | accounting date | no | bill |
| Partial bill | only the equipment reconciled with the billed quantity | | | |
| Bill reset to draft | amount kept; provisional again; the reference stays the bill's | unchanged | yes | bill |
| Bill cancelled (`button_cancel`) | the equipment concerned is **recorded before** the unlink. If it has an order line (through its receipt operation line), the order estimate is restored; otherwise the amount is kept | the restored estimate's date, otherwise unchanged | yes | order, or `bill_cancelled` with `cost_reference` « <bill> (cancelled) » |
| Equipment released by `_release_excess()` (draft bill's quantity lowered; the bill is **not** cancelled) | same rule, recorded before the unlink | as above | yes | order, or `bill_released` with `cost_reference` « released from <bill> » |
| Acquisition without purchase | line `unit_value`, converted from the operation currency at the execution date | execution date | no | acquisition |
| Borrowed / rented | none: `cost_known` False (the monitor uses the replacement value) | | | |
| Owned, no source found | none: `cost_known` False; the monitor shows NULL and `alert_cost_missing` | | | |

- `balance` is already in company currency at the bill's rate.
- The bill-to-equipment hook of `lartdubati_investor_home/models/account_move_line.py`
  moves to `maintenance_shareholder_equipment`.
- **Manual correction**: the wizard « Correct the equipment cost » (amount, date,
  provisional, mandatory reason) is reserved to **Accounting / Administrator**
  (`account.group_account_manager`), not to the ownership managers (decision D7). It
  writes through one method, which posts the old and new values with the reason and
  the author in the chatter. `cost_source` becomes `manual`.
- Migration (post-migrate 18.0.3.1.0):
  - equipment with a posted bill line: source bill;
  - otherwise from the receipt move's `price_unit` (per product unit): provisional,
    source migration, receipt date;
  - otherwise `cost_known` False, listed by the setup script.
- Tests:
  - order price different from the bill price (estimate, then real);
  - bill before receipt and receipt before bill;
  - order and bill in a foreign currency at different rates;
  - **order and bill in a unit different from the product's** (pack of 10);
  - **discount and different unit together** on the order line;
  - partial bill;
  - **bill reset to draft**;
  - **bill cancelled** (separate test: estimate restored from the order, source and
    reference explained);
  - bill cancelled for an equipment created from the bill (amount kept, source
    `bill_cancelled`);
  - `_release_excess` (source `bill_released`, reference « released from … », distinct from a cancellation);
  - acquisition without purchase;
  - real zero cost versus unknown cost;
  - correction wizard refused to an ownership manager, accepted for an accounting
    administrator, with its chatter trace;
  - migration.

## 3. Point 10 – accounting treatment shown in the receipt and frozen in the approval (corrections A2 and 2)

- Computed field `accounting_treatment` (text) on each line of a receipt that brings
  **company property**: purchase, and acquisition without purchase. It is shown on the
  line sheet and in the approval summary.
- The account is the one the future bill line will actually use, under the current
  configuration, computed on an in-memory supplier bill (`account.move.new`, type
  `in_invoice`):
  - existing order: a line from `purchase_line._prepare_account_move_line()` with the
    order's fiscal position;
  - new order: a line on the product with the partner's fiscal position
    (`account.fiscal.position._get_fiscal_position(partner)`).
  Odoo's `_compute_account_id` then applies the product or category account, the fiscal
  position and the `stock_account` input account. Nothing is saved.
- Wording, always prefixed « Planned treatment under the current configuration: »:
  - account with an asset profile: « posting the bill will create a fixed asset
    (account <code>) »;
  - storable product with automated valuation: « value carried by the stock (account
    <code>); no fixed asset »;
  - any other account: « the bill line will use account <code>; no fixed asset will be
    created automatically ». The account is named, never labelled as an expense.
  - acquisition without purchase: « no bill: if this equipment must be capitalised, the
    fixed asset is created manually by the accountant ».
- **Treatment signature in the approval**: per line, a tuple
  - account id;
  - asset profile id;
  - product valuation (`real_time` / `manual_periodic`);
  - the category that gave the account (product or category level);
  - fiscal position id;
  - Anglo-Saxon flag of the company.
  It is added to `_commitment_snapshot()`. At execution the server recomputes it like
  the rest of the snapshot. Any difference (category changed, fiscal position, account
  or profile changed, valuation changed) cancels the approval: the operation goes back
  to draft, with a chatter message naming the line and the old and new treatment, and
  must be approved again.
- **Confirmation** `no_asset_confirmed`:
  - only on lines of company property (purchase, acquisition) whose treatment creates no
    asset;
  - never for borrowed, rented or consumable lines.
  It is part of the snapshot.
- **Visibility**:
  - the account **code** is shown, which every internal user may read
    (account.account is readable by `base.group_user`);
  - the asset **profile name** is shown only to users who can read the profile
    (accountants);
  - everyone else sees the generic wording « a fixed asset will be created ».
  The computation reads the account's profile with `sudo()` inside the compute method
  only to know whether one exists; no name or value of a record the user cannot read
  is returned. This replaces `compute_sudo=True` on the whole field.
- Tests, each comparing the announced account with **the account of the real bill line
  Odoo generates** (`action_create_invoice()` on the order, then the line's
  `account_id`):
  - plain account;
  - fiscal position mapping the account;
  - automated valuation (stock input account);
  - manual valuation on an account carrying an asset profile;
  - acquisition wording;
  - confirmation required only for company property;
  - approval cancelled when, after approval, the category's account, the account's
    profile, the product's valuation or the partner's fiscal position changes;
  - profile name hidden from a non-accountant.

## 4. Point 11 – approver separated from the operator (corrections A3 and « approver's scope »)

- `equipment.operation` ACL for the approver: **read only** (`1,0,0,0`), as on its
  lines and stop lines. Approval, rejection and reset to draft stay methods that check
  the group, then write as superuser.
- `_mail_post_access = "read"`, so the approver can post in the chatter.
- Read rights on referenced documents, **limited to the documents referenced by an
  equipment operation** (option 2 of the audit, decision D8):
  - **read** ACLs for `group_equipment_approver` only on purchase.order,
    purchase.order.line, stock.lot, stock.picking, stock.move, contract.contract and
    contract.line;
  - **record rules of the approver group** restrict them to referenced documents,
    through reverse fields added for this purpose:
    - purchase.order: `equipment_operation_ids != False`;
    - purchase.order.line: `order_id.equipment_operation_ids != False`;
    - stock.picking and stock.move: `equipment_operation_id != False` (fields of
      phase 2);
    - stock.lot: `equipment_operation_line_ids != False`;
    - contract.contract: `equipment_operation_ids != False`;
    - contract.line: `contract_id.equipment_operation_ids != False`.
  - Group rules are ORed with the rules of the user's other groups. A user who is also
    a purchase user keeps their purchase rights, as expected. An approver-only user
    sees nothing else.
  - The alternative (company-wide read, documented as a business decision) is left to
    the owner (D8).
- `_check_user_access()` is called at **submit, approve and execute**. It also checks
  line taxes, currencies, order lines, responsible, parent of off-site stocks and
  replacement currency.
- Tests (Python):
  - approver: header write refused; approve, reject and message allowed;
  - operator: cannot approve;
  - a user with both roles can do both;
  - investor: no access to operations;
  - an unreadable referenced record blocks submit, approve and execute;
  - **an approver-only user cannot read an order, lot, transfer or contract that no
    operation references**, and can read the referenced ones.
- **Interface test (tour, HttpCase)** with an approver-only user:
  - open a complete purchase receipt and every line sheet;
  - see the treatment and approve;
  - no access error.
  Same tour for the operator, without the approve button.
- Interface checks on artdubati_test with four real profiles (Playwright, passwords
  never stored).

## 5. Deployment (correction 3: fetching the code is not deploying it)

`docs/phase2f/README.md`, run by the owner:
1. **Backup** of the database and filestore.
2. **Fetch the code without touching the working tree**:
   - `git -C /opt/odoo/addons/custom fetch origin +refs/heads/main:refs/remotes/origin/main`
     explicitly updates `origin/main`;
   - check it with `git -C /opt/odoo/addons/custom log -1 --oneline origin/main`
     against the commit announced;
   - extract the scripts: `rm -rf /tmp/phase2f && mkdir -p /tmp/phase2f && git -C
     /opt/odoo/addons/custom archive origin/main docs/phase2f | tar -x -C /tmp/phase2f`.
     The archive keeps its tree, so the scripts are in `/tmp/phase2f/docs/phase2f/`.
   The running Odoo and the checked out files are unchanged.
3. **`setup_phase2f.py --apply`** from `/tmp/phase2f/docs/phase2f/` (JSON-RPC against the running,
   unchanged Odoo; dry run first):
   - sets the responsibles chosen by the owner (D1);
   - handles D3 and D4 per the owner's answers.
   It uses only fields that already exist before the update.
4. **`precheck.sh`** from `/tmp/phase2f/docs/phase2f/`, which must pass (exit 0). It refuses when:
   - an active integrated equipment has no valid responsible;
   - an open receipt is not decided (D4).
5. **Stop the application**, then update the working tree:
   `git -C /opt/odoo/addons/custom merge --ff-only origin/main`.
6. **Update the modules and run the tests**: `deploy_modules.sh <dump> <count> phase2f`,
   which keeps odoo_web stopped on failure.
7. **Restart only if everything passed**. On failure, restore the backup and the
   previous commit (procedure 4b of phase 2).

Operations already approved before the update carry a snapshot without the treatment
signature. Their approval is therefore cancelled at execution, by design. The setup
script lists them in step 3, so that they can be approved again after the update.

## 6. Data to prepare (read-only queries, owner decisions)

| # | Item | Query (read-only) | Decision (audit's recommendation) |
|---|---|---|---|
| D1 | Equipment 484 (serial 1234) and any integrated equipment without a responsible | `select id, name, owner_user_id from maintenance_equipment where integration_state = 'done' and active and owner_user_id is null;` | the owner names the responsible |
| D2 | Address of **every candidate monitor stock**: `Bg/Stock`, `TBER/Stock`, `TIST/Stock`, every `lent_out` location (C2) | `select l.id, l.complete_name, l.place_type, l.address_id, p.city, p.country_id from stock_location l left join res_partner p on p.id = l.address_id where l.usage = 'internal' and l.active and (l.id in (select lot_stock_id from stock_warehouse) or l.place_type = 'lent_out') order by l.complete_name;` | structure each address (city, country) and set it on each stock |
| D3 | Active incomplete equipment named « Test » | `select id, name, integration_state, stock_lot_id, create_date from maintenance_equipment where name ilike 'test%';` | delete it, or archive it if a move references it |
| D4 | Open receipt Bg/IN/00004 | `select p.id, p.name, p.state, p.origin, p.equipment_operation_id from stock_picking p where p.name = 'Bg/IN/00004';` | cancel it if it is test data, otherwise take it over through an operation |
| D5 | Account with both « Investor » and Inventory rights | `select u.id, u.login from res_users u join res_groups_users_rel r on r.uid = u.id join ir_model_data d on d.res_id = r.gid and d.model = 'res.groups' and d.module = 'lartdubati_investor_home' and d.name = 'group_stock_investor' where u.stock_access_id is null;` (investors without a profile; their other groups are checked on the user form) | remove « Investor » from that account, unless an investor profile is explicitly needed |
| D6 | « Not assigned » responsible allowed? | — | **no (accepted, audit of 09/10/2026)** |
| D7 | Who may correct an equipment cost by hand? | — | proposal: Accounting / Administrator only, through the wizard |
| D8 | Approver's read scope | — | proposal: limited to the documents referenced by operations (record rules); alternative: company-wide read, documented |

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

## 8. Implementation notes (09/10/2026), for the code audit

Departures from the plan, each with its reason:
- **Units of measure, beyond the cost.** The test « discount and pack unit together »
  showed that a pack unit also broke the counts:
  - OCA `maintenance_account` creates `int(quantity)` equipment without converting;
  - phase 1 counted the equipment of a bill line in the line's unit;
  - phase 2 compared quantities in the product's unit with the order's.
  The rule is now that **operation lines and equipment count in the product's unit**:
  - the order line is converted when the form fills the lines and when the remaining
    quantity is checked;
  - transfer move lines use the product's unit;
  - the draft bill converts back into the order's unit;
  - `_equipment_units()` converts the bill line.
- **Acquisition cost**: `unit_value` is taken in **company currency**, as the stock move
  of phase 2 already values it, rather than « converted from the operation currency ».
  The operation's currency only serves a new purchase order.
- **Fiscal position of an order created by the operation**: it was empty. The order
  form sets it from the vendor; the code now does the same
  (`_get_fiscal_position(partner)`). Without it, the real bill would not have used the
  announced account (found by `test_new_order_uses_the_partner_fiscal_position`).
- **Execution after a change since approval**: the operation goes back to draft and the
  message names the line and the old and new treatment, without an error. Before, a
  UserError rolled everything back and left the operation « approved ».
- **Accounting administrators** (D7) are added to the existing equipment **read** rule.
  Otherwise they could not open the equipment whose cost they correct. They get no
  write right; the history message is posted as superuser with the real user as
  author.
- **Approver scope**: global read rules on 8 models (orders, order lines, transfers,
  moves, lots, contracts, contract lines, bills).
  - Their domain comes from `res.users._equipment_approver_domain()`.
  - It is always true for a user who has any other read right on the model. This
    avoids group rules, which Odoo ORs with those of the user's other groups.
  - Bills are included because the operation form shows them (`bill_ids`) once
    executed.
- **Interface tests**: three tours (HttpCase; the third added after the audit of bad8e9f).
  - They need Chrome and the Python module `websocket-client`. Locally they ran and
    passed.
  - On the server, if `odoo_web` lacks either, they are counted as **skipped**, not
    failed, so the expected total stays 133. The interface checks of README §8 then
    cover them.

Corrections after the audit of bad8e9f (09/10/2026):
1. **Order created in the purchase unit.** `_create_purchase_order()` writes the order
   line in the product's purchase unit (`uom_po_id`): quantity converted with
   `_compute_quantity(..., round=False)`, unit price with `_compute_price()`. The
   operation lines and the equipment still count in the product's unit; the receipt
   and the draft bill convert back without rounding.
   **Decision for a quantity that is not a whole number of purchase units** (for
   example 3 pieces with a purchase unit « pair »): refused at the checks, with a
   message naming the product, the quantity and the purchase unit; never rounded,
   because rounding would order or bill a quantity that is not received. The test is
   made with the rounding of the purchase unit. Tests: `TestPhase2fPurchaseUnit`
   (2 pieces → 1 pair at 120 on the order, received 1, 2 equipment at 60 provisional,
   bill line in pairs, cost 60 final; 3 pieces refused).
2. **Approver's access to the lines.** Global read rules added on `account.move.line`
   (lines of a bill linked to an operation), `stock.move.line` (lines of a move or
   transfer of an operation) and `contract.modification` (history of a contract of an
   operation), with the approver's read ACLs. `account.journal` gets an approver read
   ACL without a rule: configuration, its name is shown on the bill. New tour test
   `test_approver_alone_opens_every_document_after_execution`: after approval and
   execution, the approver alone opens the order (with lines), the receipt and the
   detailed operations of its move (serial number shown), the lot, the bill (with
   lines) and the contract of a borrowed equipment (with lines), each without an
   error dialog. The test enables « Lots & Serial Numbers » for internal users, as on
   artdubati_test (phase 0); without it the serial column is hidden.
3. **`setup_phase2f.py`**: `--responsible ID=login` is refused unless ID is in the D1
   list (integrated equipment without a responsible) and `--archive-equipment ID`
   unless ID is in the D3 list; both before any write, in dry run too.
4. **Currency of the acquisition value**: label « Unit Value (excl. tax, company
   currency) » and monetary widget with the company currency symbol on the line.
5. **Owner's rule « (HT) » (09/10/2026)**: every price or cost label says it is
   untaxed (DEFINITIONS.md, « Taxes in labels »): unit price, unit value, replacement
   value, rent per period, cost (equipment, correction wizard, form groups). Not
   changed: the handover value, whose meaning (and tax basis) waits for the
   accountant (C9); the « Replacement Price » setting of the monitor, a choice of
   source and not an amount, which phase 3 removes (moot while consumables are owned
   only).

Verified locally:
- 133 tests (Odoo 18, local OCA heads), the three tours included;
- full rehearsal of the deployment on a database made with the phase 2 code (2345e7e):
  - the precheck fails on the 3 integrated equipment without a responsible and the open
    receipt;
  - `setup_phase2f.py` dry run, then `--apply` (on the copy only);
  - the precheck becomes clean;
  - the update to 18.0.3.1.0 / 18.0.1.6.0 runs without an error;
  - the migration gives the saw (like 484) 329 € provisional from its order, the drill
    billed before receipt 520 € from its bill, and the acquisition 250 €.

Not verified (server):
- Chrome and `websocket-client` in `odoo_web`;
- the filestore path `/var/lib/odoo/filestore`;
- Anglo-Saxon accounting on the company;
- the real data of D1 to D5.

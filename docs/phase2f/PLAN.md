# Phase 2f plan – corrections to phase 2 (audit of 09/10/2026, points 9 to 11)

Status: revision 1 (09/10/2026), for the audit. No code written.
Scope: `maintenance_shareholder_equipment` 18.0.3.1.0. Deployed on artdubati_test
**before** phase 3 (whose monitor shows « responsible missing » and « equipment without
asset »).
Origin: the general audit of the existing code, after the owner's first real receipt
(EQOP/2026/0159, equipment 484, serial 1234):
- the equipment was integrated without a responsible;
- its product is in category « All »: the draft bill is on 607000, with no asset
  profile, so posting it will create no asset;
- the approver can write the operation header.

## 0. Facts checked in the code
- `maintenance.equipment._integration_missing()` lists what an integrated equipment
  must have (maintenance_equipment.py:221). The responsible (`owner_user_id`, labelled
  « Responsible / holder ») is not in it. The same list feeds
  `action_finalize_integration` and the constraint `_check_integrated_complete`.
- The receipt line carries `responsible_user_id`, which is copied to `owner_user_id`
  (equipment_operation.py:1411) and is optional.
- Access rights (security/ir.model.access.csv): `equipment.operation` gives the approver
  read and write (line 4). `action_approve` already writes as superuser after
  `_is_approver()` (equipment_operation.py:396-410).
- `_check_user_access()` is called only by `action_execute` (line 476). It checks
  partner, site, transfer type, destination, order, contract, off-site location,
  products, equipment and line destinations. It does not check taxes, currency, order
  lines, responsible, parent location or replacement currency.
- A Python constraint is not re-checked on existing data when the module is updated.

## 1. Point 9 – responsible required
- Add « responsible » to `_integration_missing()`: an `owner_user_id` that is an
  **internal** user (not share), **active**, and **allowed in the equipment's company**
  (`company_id in user.company_ids`).
- This covers the integration, the constraint on later edits and the receipt: the
  receipt line's `responsible_user_id` becomes required for equipment lines at submit
  (`_check_values_receipt`), with the same three conditions. The line field gets a
  domain on internal active users of the company.
- No « not assigned » value (decision D5 below): if the owner wants one, it will be an
  explicit setting, not an empty field.
- Existing data: equipment integrated without a responsible stays readable but cannot
  be edited until completed. The setup script lists it, and the owner fills it (D1).
- Tests:
  - integration refused without a responsible, with a portal user, with an archived
    user, and with a user outside the company;
  - submit refused on a receipt line without a responsible;
  - the receipt copies the responsible to the equipment.

## 2. Point 10 – accounting treatment shown in the receipt
- Computed field `accounting_treatment` (text) on each equipment line, from the
  product category, and shown on the line sheet:
  - « Will create a fixed asset with the profile <profile> when the bill is posted »,
    for a category flagged `is_fixed_asset_stock` whose expense account has an asset
    profile;
  - « Valued in stock (<account>), no fixed asset », for automated valuation;
  - « Expensed on <account>, no fixed asset », for manual valuation (the saw: category
    « All », 607000).
- When an equipment line (maintainable product) is in a category without a fixed asset,
  the line shows a warning. The operation cannot be submitted unless the operator
  ticks « I confirm this equipment is not capitalised » on that line
  (`no_asset_confirmed`). The confirmation is part of the approval snapshot, so a change
  after approval invalidates it.
- The same text appears in the approval summary seen by the approver.
- Tests:
  - text for each of the three treatments;
  - submit refused without the confirmation;
  - confirmation not needed for a fixed-asset category;
  - snapshot invalidated when the product changes after approval.

## 3. Point 11 – approver separated from the operator
- `ir.model.access.csv`: the approver gets **read only** on `equipment.operation`
  (`1,0,0,0`), as on the lines and stop lines. Approval, rejection and reset to draft
  stay methods that check the group, then write as superuser (already the case for
  `action_approve` and `action_reset_draft`).
- `_mail_post_access = "read"` on the operation, so the approver can post in the
  chatter without write access.
- `_check_user_access()` is called at **submit, approve and execute**. It also checks:
  - line taxes;
  - the operation's and the order's currency;
  - order lines;
  - the responsible;
  - the parent of off-site stocks;
  - the replacement currency.
  Each record must be readable by the real user before any elevation.
- Tests:
  - the approver cannot write the header (AccessError) but can approve, reject and post
    a message;
  - the operator cannot approve;
  - a user with both roles can do both;
  - an investor without Inventory rights can neither read nor create operations;
  - a referenced record the user cannot read blocks submit, approve and execute.
- Interface checks with four real profiles on artdubati_test (Playwright, passwords
  never stored, given by the owner): operator only, approver only, both, investor
  without Inventory rights.

## 4. Deployment
- `docs/phase2f/README.md`: backup, `git pull`, `deploy_modules.sh <dump> <count> phase2f`,
  `setup_phase2f.py` (dry run, then `--apply` on artdubati_test only), interface checks.
- `setup_phase2f.py` lists, and changes nothing except with `--apply` and the owner's
  answers:
  - integrated equipment without a valid responsible;
  - equipment whose category creates no asset;
  - the data of §5.

## 5. Data to prepare before phase 3 (read-only queries, owner decisions)

| # | Item | Query (read-only) | Decision |
|---|---|---|---|
| D1 | Equipment 484 (serial 1234) and any integrated equipment without a responsible | `select id, name, owner_user_id from maintenance_equipment where integration_state = 'done' and active and owner_user_id is null;` | the responsible to set |
| D2 | Address of Bougival (no city, no country, per the audit) | `select l.id, l.complete_name, l.address_id, p.city, p.country_id from stock_location l left join res_partner p on p.id = l.address_id where l.usage = 'internal' and l.active order by l.complete_name;` | structure the partner's address (city, country); set it on Bg/Stock and the lent-out locations |
| D3 | Active incomplete equipment named « Test » | `select id, name, integration_state, stock_lot_id, create_date from maintenance_equipment where name ilike 'test%';` | archive it, complete it, or delete it if no move references it |
| D4 | Open receipt Bg/IN/00004 | `select p.id, p.name, p.state, p.origin, p.equipment_operation_id from stock_picking p where p.name = 'Bg/IN/00004';` | cancel it, or take it over through an equipment operation |
| D5 | User with both « Investor » and Inventory rights, without an access profile (the query lists the investors without a profile; their other groups are then checked on the user form) | `select u.id, u.login from res_users u join res_groups_users_rel r on r.uid = u.id join ir_model_data d on d.res_id = r.gid and d.model = 'res.groups' and d.module = 'lartdubati_investor_home' and d.name = 'group_stock_investor' where u.stock_access_id is null;` | remove one of the two roles, or give a profile |
| D6 | « Not assigned » responsible allowed? | — | proposal: no |

The old monitor's totals are not used for any check (the audit found the saw counted as
a consumable with 329 € of accounting value); its reports are removed in phase 3.

## 6. Verified / not verified
- Verified in the code: section 0.
- Not verified (server): the answers to D1 to D5; the asset profile actually
  configured on the categories other than « All / Fixed Assets ».

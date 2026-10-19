# Audit request — business-cycle acceptance plan revision 2

Scope: `docs/business_cycle/PLAN.md`. This is a plan audit. No user or test record has
been created and no server command is authorised by this request.

## Questions for the auditor

1. Are P1–P7 the minimum safe combinations on the exact installed Odoo/OCA platform?
   In particular, verify P6 (`account.group_account_invoice` plus
   `account.group_account_readonly`) and the implied rights of P1/P3.
2. Does any standard or already installed OCA feature provide the missing generic
   purchase request without widening rights? If not, assess OCA `purchase_request`
   before custom development.
3. Confirm that the two purchase branches are represented accurately:
   an existing PO prepared by P3, and a PO created/confirmed by an approved equipment
   operation. State which one should be the reference business flow.
4. Confirm the supported boundary for stock “use”: internal transfer and equipment
   assignment/usage are not equivalent to worksite consumption.
5. Review every negative test in S0 for privilege escalation, record-rule interaction
   and menu-only false confidence.
6. Check whether P7's proposed restricted Stock Access Profile is sufficient to prove
   both positive access and isolation.
7. Verify that the manual baseline findings are complete. Search all FR/EN/FA cards for
   removed fields and direct-edit instructions, not only CH-01/CH-02.
8. Audit the complete campaign lifecycle in §5: immutable identity, exact clone,
   isolation from normal `odoo_web`, cron/mail shutdown, before/after inventory,
   quarantine, deletion confirmation and deletion certificate. Prefixes alone are not
   accepted as isolation.
9. Identify any step that still relies on Administrator, `sudo`, the autonomous
   catalogue exception or the historical combined `Test` account.
10. Return one of: green light for the characterisation/profile script; corrections
    required with severity and exact evidence; or an owner decision required.

## Preliminary audit findings already raised by the author

- **Blocking:** the desired generic purchase-request approval is absent.
- **Blocking:** worksite consumption is absent.
- **High:** there is no least-privilege business requester group.
- **High:** the manual is structurally aligned but semantically obsolete in several
  core cards.
- **Medium:** exact native group implications must be measured on the installed 122
  modules before any user is created.
- **Blocking:** profile creation or business acceptance must not start until the audit
  database/filestore lifecycle proves that all campaign operations can be isolated and
  removed without deleting posted records individually.

The auditor must challenge these findings and the proposed solutions; this file is not
an independent audit result.


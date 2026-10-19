# Audit request — business-cycle acceptance plan revision 3

Scope: `docs/business_cycle/PLAN.md`, revision 3. This request authorises only a plan
audit. No account, database, container, script execution or server mutation is
authorised.

## Changes made after the audit of `1383a33`

1. The campaign no longer restores a clone into live `odoo_db`. It requires a separate
   ephemeral PostgreSQL instance, private data/WAL volume, filestore volume and Odoo
   container, with exact database selection, cron disabled and a distinct hostname.
2. Existing backup/restore scripts are explicitly excluded from clone creation. A
   read-only inventory must first find stale `_verify_`, `_before_restore_` and other
   databases, active connections, backup/WAL/snapshot policies and network topology.
3. P3/P6 stock and purchase RPC capabilities, P2 adjustment, P1 scrap/configuration and
   P1/P3/P4 structural category rights are now blocking server-call tests, not menu
   assumptions. D1–D5 state the recommended owner policy.
4. The reference purchase path is the P3-created existing PO. `purchase_mode=create`
   must be disabled or explicitly restricted before the campaign.
5. G1/G3 now names `purchase_request` plus `purchase_request_tier_validation`; G2 names
   the OCA stock/worksite candidates to characterise after the accounting decision.
6. Attribution uses row-by-row primary-key snapshots and relation rows in separate
   configuration and business windows, with a narrow versioned noise allowlist.
7. Corrections deploy separately to `artdubati_test`; scenario replay uses a new
   ephemeral pair and campaign ID. The campaign itself never mutates the live test DB.
8. P7b is a distinct investor without a profile. Deliberate out-of-scope rows are
   required. P9 gains Accounting Read-only only if the monitor probe requires it.
9. The full known obsolete-manual card list is recorded. Links must be relative and
   stable/XML-ID based; the browser blocks the real ERP hostname.
10. Cleanup now covers containers, networks, DB/WAL and filestore volumes, host/provider
    backups, browser/Playwright artifacts, reverse-proxy/DNS entries and raw evidence.

## Decisions recommended to the owner

Please assess whether each recommendation is safe and complete:

- **D1:** forbid ordinary requester/operator + ordinary catalogue approver; exclude the
  autonomous historical exception from the campaign.
- **D2:** existing confirmed PO prepared by P3 is the reference; disable/restrict
  `purchase_mode=create`.
- **D3:** P2 cannot adjust inventory; P1 adjustment/scrap requires a narrow guard,
  reason and evidence.
- **D4:** accounting/category structural fields are configuration-admin only; P4 uses
  governed structural correction and P1 has only a named operational subset.
- **D5:** server guards block P3/P6 stock execution and P6 PO mutation.
- **D6:** characterise OCA purchase request + tier validation for G1/G3.
- **D7:** G2 may remain outside the pre-AI milestone if the owner explicitly limits the
  accepted scope to transfer/use/return.

## Questions for the auditor

1. Does the separate PostgreSQL/Odoo topology prevent the live Odoo service and every
   cron/worker from discovering or writing the audit database? Identify any remaining
   network, cookie, filestore, backup or neutralisation gap.
2. Is the read-only characterisation in §5.1 sufficient before infrastructure scripts
   are designed, including stale DBs, ERP credential scope, WAL/provider backups and
   injected service configuration?
3. Are D1–D5 the correct least-privilege production policies? Cite exact remaining code
   paths requiring server-side guards and tests.
4. Is the two-window, row-by-row inventory adequate for creates, modifications,
   deletions, M2M changes, `sudo()` and technical noise?
5. Confirm that corrections/replays no longer contradict the rule that the audit
   campaign itself leaves `artdubati_test` unchanged.
6. Is the manual-obsolescence set complete, and are relative stable/XML-ID links enough
   to prevent escape to the real service?
7. Assess OCA `purchase_request` + tier validation for G1/G3 and the named G2 candidates.
   Do not treat unguarded base approval as separation.
8. Confirm the added scenarios: consumable receipt, existing bill mode, refused refund,
   maintenance request, exit/return/restitution, P3/P6 direct-receipt attacks, and each
   role changing its own language.
9. Review sanitised-evidence criteria and complete deletion, including raw screenshots,
   attachments, contacts, sessions and provider-retained copies.
10. Return one of:
    - green light only for the read-only server characterisation;
    - corrections required with severity and exact evidence;
    - owner decision required before any next step.

Even a green audit does **not** authorise account creation or a campaign. The next
deliverable would be the read-only characterisation command set, separately audited
before use.

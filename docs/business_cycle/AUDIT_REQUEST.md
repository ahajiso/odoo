# Audit request — business-cycle acceptance plan revision 4

Scope: `docs/business_cycle/PLAN.md`, revision 4. No account, database, container,
profile/security script or server mutation is authorised. The audit of `1411d1d`
authorised only drafting the future read-only characterisation commands, which will be
submitted separately before execution.

## Corrections after the audit of `1411d1d`

1. Removed the false statement about catalogue self-approval. The actual dangerous
   combination is Equipment Operator + Equipment Approver, which can approve and execute
   in one click. §3.1 now contains the complete prohibited-combination matrix.
2. D6 now says `purchase_request` is not installed. It records the unguarded
   `tier.review` RPC problem and the broad PO/stock-move reads granted by the OCA user
   group. G1/G3 cannot use it without custom guards and a platform/route audit.
3. D3 covers scrap and every consumable crossing a non-internal boundary, not only
   inventory adjustment or supplier/acquisition locations.
4. D5 includes P3 mutation/deletion of operation-created draft bills. Legitimate P6 PO
   writes must be characterised before designing a guard.
5. The live-test exit criterion is now “no write attributable to audit infrastructure”,
   with writes classified by author and no deployment during an active campaign.
6. Inventory covers every PostgreSQL table, relation, sequence and filestore file.
7. Infrastructure characterisation adds actual DB selection, PostgreSQL role status,
   Docker logs, swap, proxy, snapshots, `web.base.url.freeze` and mail servers.
8. Audit code is a separate frozen read-only checkout; dump/filestore restore semantics
   are explicit.
9. The hostname is stable and neutral, proxy-authenticated and separately audited. No
   campaign ID is placed in DNS or a public certificate.
10. D9 recommends bounded `tmpfs`, then encrypted ephemeral storage with cryptographic
    erasure. Unavoidable provider/session copies are declared, not falsely “deleted”.
11. Manual audit is 67 cards × 3 languages and adds CPT-22–26, index/header/ranges and
    deletion of both CSV templates. Human testers follow the same no-real-host rule.
12. Added P10/D8 for the site actor, loaned/borrowed flows, all consumable-boundary
    attacks, `tier.review` attacks and P3 draft-bill attacks.
13. Corrected C8, P9 monitor rights and approval semantics for `bill_mode=existing`.

## Owner decisions

- D1–D7 are revised recommendations awaiting confirmation.
- **D8 confirmed 19/10/2026:** P10 Site Manager requests/acknowledges; P2 alone executes
  physical moves.
- **D9 confirmed 19/10/2026:** use bounded `tmpfs`, subject to characterisation;
  encrypted-erasure storage is the fallback and unavoidable external retention is
  declared rather than hidden.
- **D10 confirmed 19/10/2026:** stable neutral authenticated audit hostname, with
  separately audited DNS/proxy/network-policy changes.

## Questions for the auditor

1. Are all E1–E6, M1–M7 and F1–F3 findings from the audit of `1411d1d` now represented
   accurately and without creating a false security claim?
2. Is §3.1's prohibited-combination matrix complete after implied-group expansion?
3. Are the proposed guards for consumable boundaries, stock execution and draft bills
   correctly scoped, while preserving legitimate accounting reconciliation?
4. Does the proposed G1/G3 analysis correctly treat both unguarded `tier.review` and
   over-broad `purchase_request` reads as blockers?
5. Is a whole-catalogue/table/sequence/filestore diff sufficient in principle, subject
   to a separately audited implementation?
6. Are D8–D10 safe defaults to submit to the owner?
7. Is the 201-card manual verdict plus template/index/export audit now complete enough?
8. Return one of:
   - green light to draft the read-only characterisation commands only;
   - corrections required, with severity and precise evidence;
   - owner decisions required before that drafting step.

Even a green light does not authorise execution of the characterisation, creation of an
audit environment or creation of users. Each remains a later, separately audited step.

# Business-cycle acceptance before AI — plan revision 5

Status: **plan only, submitted for audit**. No account, business record, module,
database, container or server configuration is created or changed by this revision.

Date: 19/10/2026. Source: a verified backup of `artdubati_test`. The campaign runs on
an ephemeral Odoo/PostgreSQL pair dedicated to the audit. `artdubati_test` and
`artdubati` remain outside the campaign.

Revision 5 incorporates the audits of commits `1411d1d` and `f79f839`. Only the
preparation of the read-only server characterisation is authorised, and its commands
must be audited before use. Profile, security and campaign scripts remain forbidden.

## 1. Goal and exact meaning of “complete cycle”

The target is a role-separated acceptance from a business need to warehouse use:

1. request an item, service or purchase;
2. create a missing catalogue item through the governed catalogue;
3. approve the need, prepare and confirm the purchase;
4. receive the physical item under the equipment-operation controls;
5. check and post the supplier bill and verify the accounting result;
6. move the item out of the warehouse, record its use, return or restitution;
7. read the outcome as warehouse, purchasing, accounting and shareholder roles;
8. execute each step from the applicable FR/EN/FA manual;
9. correct defects and replay the scenarios with a new campaign identifier.

The currently supported boundary stops at internal transfer and equipment usage. It
must not be described as worksite consumption or analytic cost attribution. G1/G2 in
section 8 state what is still missing for the full target.

Every positive step is performed by its named role. Administrator, superuser, the
historical combined `Test` account and the Autonomous Catalogue profile are control
identities only and do not constitute business evidence.

## 2. Facts established by the code audit

### 2.1 Supported today

- `product.creation.request` governs creation of products and services. It refuses
  self-approval even when ordinary requester and catalogue-manager groups are combined;
  only the explicit Autonomous Catalogue group is exempt.
- `equipment.operation` governs equipment and consumable receipts. The installed code
  supports an existing confirmed purchase order and an operation-created order.
- Equipment Operator implies Inventory / User. Standard Odoo transfers move goods
  between internal locations.
- Vendor bills, assets, contracts and the stock monitor are linked on implemented
  paths.
- Investor access is constrained by incompatible staff groups. A missing Stock Access
  Profile is valid and deliberately produces zero rows plus a warning; it is not a
  database-level profile requirement.

### 2.2 Rights that cannot be inferred from menus

The exact installed core/OCA stack gives more RPC rights than the proposed role names
suggest:

- Purchasing Manager can validate pickings through installed stock/purchase methods;
- Accountant has create/write access on stock pickings/moves and can write purchase
  orders/lines through inherited core/OCA access;
- Inventory User can perform inventory adjustment and scrap, so both are available to
  P2 through implied rights;
- consumable protection covers only supplier/acquisition sources. Other non-internal
  sources and destinations (Customers, Inventory, Production and Transit) can change
  stock without a governed equipment operation;
- Purchase users can modify `account.move`; P3 can therefore alter or delete an
  operation-created draft supplier bill unless a server guard prevents it;
- warehouse, purchasing and catalogue roles can reach structural product-category or
  accounting fields in combinations that require explicit server-side restriction;
- hiding menus does not remove any of these RPC capabilities.

No acceptance campaign starts while these facts are merely assumptions. Section 6.1
defines RPC probes; section 8 records the owner's decisions and required hardening.

### 2.3 Functional gaps

- A catalogue request is not a purchase authorisation. No generic least-privilege
  business-need document currently precedes the RFQ.
- Worksite consumption, analytic attribution, surplus return and loss are not
  implemented as a controlled flow.
- A dedicated Business/Site Requester group does not exist.
- The manuals are structurally consistent across languages but semantically obsolete
  in many cards (section 7).

## 3. Test profiles and separation policy

All accounts are internal single-company users. Their logins, display names and every
operation are labelled with the immutable campaign ID. Passwords are supplied outside
Git and never logged.

Before creation, a read-only characterisation expands implied groups and records menus,
ACLs, record rules and RPC outcomes on the exact installed stack. The future setup tool
must dry-run first and refuse the live source databases, unexpected existing users,
incomplete profiles and prohibited group combinations.

| ID | Test profile | Explicit groups | Purpose |
| --- | --- | --- | --- |
| P1 | Warehouse Manager | Equipment Operator + Inventory Manager | Operational stock administration and equipment execution. No purchase, catalogue approval, accounting, investor or equipment-approval group. |
| P2 | Warehouse Operator | Equipment Operator | Daily receipt, transfer and return with Inventory/User implied. No configuration or commitment approval. |
| P3 | Purchasing Manager | Purchase Manager | Creates and confirms RFQ/PO. No catalogue approval, stock execution, accounting or investor group. |
| P4 | Product Catalogue Manager | Product Catalogue Manager | Approves/executes another user's catalogue request. Never autonomous and receives no Purchase/Inventory group merely for menus. |
| P5 | Equipment Operations Approver | Equipment Approver | Approves frozen commitments; cannot edit or physically execute them. |
| P6 | Accountant | Accounting/Billing + Accounting Read-only, exact installed IDs to be characterised | Checks/posts ordinary supplier bills and reads accounting monitor columns. It must not validate stock, edit purchase commitments or configure catalogue accounting through RPC. |
| P7 | Shareholder / Investor | Stock Monitor Investor + restricted profile | Only Investor Home and scoped stock monitor. |
| P7b | Investor without profile | Stock Monitor Investor, no Stock Access Profile | Separate account proving zero rows and the warning; P7 is never modified during the run. |
| P8 | Business / Site Requester | **missing group; do not create yet** | Target role for own requests only, without Purchase/Inventory/approval rights. |
| P9 | Accounting Administrator | Accounting Manager + Accounting Read-only | Exceptional accounting correction only; never ordinary invoice evidence. Read-only is explicitly required by the stock monitor. |
| P10 | Site Manager / Site Requester | **missing least-privilege group; do not create yet** | Requests stock for a site and acknowledges use/return without stock execution, Purchase or approval rights. The recommended D8 assigns physical moves to P2. |

### 3.1 Prohibited combinations

The recommended policy, pending the owner's explicit confirmation, is:

- Equipment Operator and Equipment Operations Approver may not be combined: current
  code intentionally approves and executes in one click for this combination;
- P6 Accounting may not be combined with Purchase;
- P3 Purchase may not be combined with Inventory;
- Investor may not be combined with any other business group;
- no business profile may have Settings or Administration;
- the historical `Test` exception and Autonomous Catalogue group are excluded from the
  campaign;
- profile creation refuses every prohibited combination after expanding implied groups;
- positive evidence never uses P9 where P6 is the intended actor.

This is not considered enforced until the relevant server methods and setup validator
have auditable tests. A UI-only restriction is insufficient.

## 4. Language, data scope and monitor matrix

- Every role starts in French. The role itself changes its language to English, signs
  out/in, performs its critical screen, then repeats in Persian and signs out/in.
- Persian validation covers RTL layout, button direction/order, date and amount
  readability and exact labels.
- P7 receives a restricted profile, initially `Bg/Stock`, owned/rented, equipment and
  consumables. P7b remains without a profile.
- The clone must contain deliberate out-of-scope rows (including TBER/TIST ownership,
  other locations and excluded statuses) so isolation proves exclusion, not absence.
- P7 sees no accounting-only field or staff menu. P6 and, if required, P9 see the
  accounting monitor columns. P1/P2 see only operational values.

## 5. Audit infrastructure, identity and verified removal

### 5.1 Read-only characterisation before design freeze

Before any script is written, a read-only server report must establish:

- all PostgreSQL databases, owners, active connections and stale `_verify_`,
  `_before_restore_`, restore or prior audit databases;
- Docker containers, networks, volumes, mounts and the exact Odoo image digest;
- Odoo configuration values affecting database discovery, cron, proxying, mail,
  webhooks and filestore;
- reverse-proxy/DNS topology and the identity/scope of injected ERP credentials,
  without printing any secret value;
- actual `db_name`, `dbfilter`, `list_db`, `web.base.url.freeze`, mail servers and the
  PostgreSQL `odoo` role's superuser status;
- Docker log driver, host swap, reverse-proxy configuration, provider snapshot schedule,
  backup agents, WAL archiving and volume-backup inclusion.

Existing `backup_db.sh` and `restore_db.sh` are not used to create the campaign clone:
they intentionally create or preserve databases in the live PostgreSQL instance. Any
stale databases they left are handled by a separate, audited maintenance decision, not
silently by the campaign.

### 5.2 Separate PostgreSQL and Odoo are mandatory

The audit clone must not share the live `odoo_db` service. Odoo can enumerate databases
for scheduled work even when HTTP `dbfilter` would hide them. The campaign therefore
uses:

- one ephemeral PostgreSQL container and private volume containing only the audit DB;
- one ephemeral filestore volume;
- one ephemeral Odoo container using the exact tested image digest and checked-out
  code from a separate frozen checkout mounted read-only, never the live
  `/opt/odoo/addons/custom`, connected only to the audit PostgreSQL network;
- `db_name` fixed to the exact audit database, an exact anchored `dbfilter`,
  `list_db = False` and `max_cron_threads = 0`;
- no network path from normal `odoo_web` to audit PostgreSQL and no path from audit Odoo
  to live PostgreSQL;
- a stable neutral hostname, containing no campaign or business identifier, not merely
  another port, so cookies and sessions cannot collide;
- authentication at the reverse proxy in addition to Odoo authentication;
- removal of the proxy's own `Authorization` header before forwarding to Odoo, so it
  cannot interact with Odoo bearer authentication or an injected ERP key;
- an explicit audit banner carrying the campaign ID;
- no Internet egress, real SMTP, invitations, payment/provider callback or webhook.

The verified source database/filestore snapshot is taken while writes are stopped. This
requires a separately planned and authorised stop of real `odoo_web`, during which both
real databases are unavailable; it is not part of read-only characterisation. The
database is restored only into the ephemeral PostgreSQL instance, then neutralised with
`odoo db load --neutralize`. A fresh `database.uuid`, `database.secret` and audit base
URL are verified. `web.base.url.freeze` is explicitly reset/verified because Odoo
initialisation does not necessarily reset it. A dump restore copies the filestore
separately; only an Odoo zip restore includes it. Scheduled actions are disabled in the
clone, including Odoo cron and installed `autovacuum_job`; no unattended worker may run.

The stable audit hostname, proxy authentication, DNS and reverse-proxy configuration
will require a later audited infrastructure change and explicit network-policy addition.
A public certificate would leave a permanent Certificate Transparency record, so the
name is neutral and stable. Nothing is provisioned now.

### 5.3 Immutable campaign identity

The owner chooses an ID such as `AUDIT-METIER-20261019-01`. It is used in the exact DB,
containers, networks, volumes, hostname, users, partners, references, serials,
attachments, browser profile and evidence directories.

A signed machine-readable manifest records source hashes, code/image/platform,
infrastructure identifiers, database/filestore counts, configuration generations,
accounts with explicit/implied groups and all scenario documents. A target cannot be
registered to two campaign IDs. A rerun after a correction uses a new campaign ID and a
fresh clone.

### 5.4 Attribution and before/after inventory

Authors alone cannot prove every write: `sudo()` may retain a real user, `write_uid`
only holds the last author, relation-table changes lack authors and deletions disappear.
The evidence therefore uses two explicit windows:

1. **configuration window** — neutralisation, profile creation and deterministic audit
   setup; its complete row-level diff is reviewed and frozen;
2. **business window** — a second baseline is taken after configuration and before S0;
   business scenarios then run without configuration changes.

Both snapshots cover **every table in the PostgreSQL catalogue**, including relation
tables. They export primary keys (or deterministic full-row identities where no PK
exists), stable field hashes, sequence values and the complete filestore path/hash
inventory. The comparison reports created, modified and deleted rows/files and changed
sequences. A small, versioned noise allowlist names
each permitted session/login/asset technical write and its reason; no catch-all pattern
is allowed. Chatter, request/approval/execution fields and linked documents prove the
business actor. Every unexplained diff blocks acceptance.

No generic context or campaign prefix changes permissions. Identification is evidence,
never an authorisation bypass.

### 5.5 Complete removal

The confirmed storage is size-bounded `tmpfs` for PostgreSQL data/WAL and filestore,
subject to the read-only size and memory characterisation. The fallback is an encrypted
ephemeral volume with a per-campaign key followed by verified cryptographic erasure.
Ordinary persistent volumes are not acceptable merely because a backup exclusion is
claimed. If host swap, provider snapshots, Docker logs or backup/WAL retention can hold
campaign content and cannot be avoided or cryptographically erased, the owner must make
the explicit D9 retention decision and complete deletion cannot be claimed.

Any audit-container or host restart loses a `tmpfs` campaign. Such a campaign is
abandoned and restarted from the clean source under a new campaign ID; it is never
recovered from a persistent copy. Host swap is disabled during the campaign, or is
encrypted under an independently verified ephemeral key, otherwise `tmpfs` is not an
acceptable deletion boundary.

Audit containers use Docker's `none` log driver where operationally possible, otherwise
the size-bounded `local` driver on the encrypted/ephemeral boundary. They never use
`journald`, because its entries cannot be deleted selectively.

After a signed, sanitised report and a separate owner confirmation, cleanup resolves
and prints exact targets, stops audit services, revokes sessions and removes only:

- the audit Odoo/PostgreSQL containers;
- their exact network, database/WAL volume and filestore volume;
- audit reverse-proxy/DNS entry and certificate material;
- browser profiles, downloads, Playwright traces/videos/screenshots, temporary files,
  raw evidence, Docker/journald logs where applicable and any temporary source snapshot
  labelled with the campaign ID.

Cleanup refuses globs, symlinks, unresolved variables, broad paths and either live
database name. A deletion certificate proves absence of every exact target and verifies
unchanged fingerprints for live containers, databases and filestores. Only sanitised
evidence remains; it contains no real contact, credential, session, attachment content
or unrestricted screenshot.

Conversation transcripts or images already copied into an external audit/AI service
cannot be deleted by these scripts. They are declared retained external copies and must
contain only sanitised evidence under the relevant provider's retention policy.

## 6. Scenario and security matrix

### S0 — profile, ACL, record-rule and RPC baseline

For P1–P10 as applicable, capture explicit/implied groups, menus, ACLs, record rules and
direct RPC results. Mandatory server calls, not UI observations, include:

- profile setup rejects every prohibited combination in §3.1, after implied-group
  expansion, especially Equipment Operator + Equipment Approver;
- P4 cannot self-approve and has no Autonomous Catalogue role (already enforced by the
  current catalogue code and retained as a regression test);
- P5 cannot edit or execute the operation it approves; P2 cannot approve;
- P3 and P6 cannot validate pickings, create/write stock moves or move lines, or perform
  a controlled receipt outside its operation;
- P6 cannot write purchase orders/lines; P3 cannot post supplier bills;
- P2 cannot adjust or scrap, and cannot change consumable stock through any non-internal
  source/destination (Customers, Inventory, Production or Transit) outside the governed
  operation;
- P1's scrap/adjustment and non-internal consumable movement scope follows D3 and
  records mandatory reason/evidence;
- P1/P3/P4 cannot change product-category accounting fields, valuation, accounts,
  asset profile or other structural fields outside governed correction;
- P1 can change only an explicitly approved operational monitor subset, if D4 keeps it;
- P3 cannot modify or delete an operation-created draft supplier bill;
- on a local rebuilt database, P8 cannot create/write/delete its own `tier.review`,
  change its status directly or be selected as reviewer of its own request;
- P7/P7b cannot call staff actions; no business account reaches Settings/Admin.

Current code is expected to fail some probes. That is a discovery result, not a waiver:
required hardening is audited and deployed separately, then a fresh campaign is made.

### S1 — governed catalogue requests

P2 requests a missing consumable and durable item. P4 refuses one incomplete request,
then approves and executes corrected requests from another user. Verify duplicates,
account/category treatment, evidence and actor trace. A telecom or insurance service is
created but stops at catalogue creation until G1 exists.

### S2 — approved need and purchasing reference path

The recommended reference path is an existing RFQ/PO prepared by P3, then selected by
the equipment operation. The `purchase_mode=create` alternative is disabled or limited
to an explicitly approved exceptional role before the campaign. P3 verifies supplier,
currency, taxes, quantity, unit and untaxed amounts.

If G1 is implemented first, P8 submits the purchase request and a distinct tier
approver approves it before P3 creates the RFQ. This is conditional on a custom server
guard around `tier.review`: installed OCA ACLs otherwise let any internal user create,
write or delete reviews and derive approval from their statuses. Otherwise the report
labels the pre-RFQ approval step “not implemented”.

### S3 — controlled durable and consumable receipts

P2 prepares operations linked to P3's confirmed orders: one serialised durable item and
one consumable. P5 approves only when the operation needs approval, including when it
creates the invoice; P2 executes. Verify one transfer, quantities/lots, equipment
creation, cost source and bill behaviour. P3/P6 direct validation attempts must be
refused by RPC.

Also test `bill_mode=existing`: name the authorised accountant who created the
pre-existing draft bill, then link/check it without an operation-created duplicate.
The plan must not claim P5 approval if `_needs_approval` is false. Do not silently
exercise `purchase_mode=create`. P3 also attempts to edit/delete the operation-created
draft bill and must be refused.

### S4 — bill, asset and refund controls

P6 checks the match, attachment, supplier reference, date, taxes and expense/asset
treatment, then posts the bill. No payment is made. A supplier refund violating the
frozen operation is first probed because no existing one-off-rental guard covers refund
moves (`out_refund`). The expected result is explicitly unknown: acceptance is a defect
to classify, not a successful negative test. Separately, C8 tests the specific
asset-supplier-refund restriction; it is not described as an operation freeze.
The Mac Mini remains a separate named scenario requiring accountant choices.

### S5 — warehouse exit, worksite and maintenance boundary

P2 performs an internal transfer from `Bg/Stock` to an audit job-site location for the
consumable and durable item. Verify quants/serials, holder/usage and CH-03 maintenance
request. Record return to warehouse and, where applicable, rental return/restitution.
Do not call this consumption or analytic allocation.

Also test an approved output to a “loaned” stock and receipt of a “borrowed” item, with
P5 approval where required. D8 depends on the request document selected under D6 for a
purchase need and D7 for a stock/worksite need. Until either document exists, P10 is not
created and the CH cards state that the site reports the need to the warehouse through
the current organisational channel outside Odoo; this gap is not counted as validated.
P2 performs every physical movement and the manual never instructs a site worker to
execute stock.

### S6 — monitor and investor isolation

P1/P2, P6/P9, P7 and P7b inspect the same records. Verify operational/accounting
columns, `rent_paid`, currencies, Detailed Analysis and exports. Confirm deliberate
TBER/TIST/out-of-location/out-of-status rows remain outside P7's scope.

### S7 — manuals in each user's language

Every role follows the manual after changing its own language and reconnecting. Record
card, language, labels, outcome and discrepancy. Browser network policy blocks the real
`erp.lartdubati.com` hostname during the campaign.

Manual links must be relative to the current host and resolve through XML IDs or stable
routes; numeric database IDs and absolute production/test links are forbidden. Run the
structural checker, desktop/mobile and Persian RTL validation.

### S8 — correction and replay

Each module/security/manual correction is independently audited and deployed to
`artdubati_test` by the controlled procedure. A deployment closes any active campaign;
replay occurs only on a new audit pair and campaign ID. The live test database may have
ordinary cron or owner writes, but no write may be attributable to audit infrastructure.
Writes in the campaign window are classified by author. Platform fingerprints may
change only through a separate audited deployment, never through an audit run.

## 7. Complete manual-conformity baseline

The known affected set from the audit is:

- **Current Location obsolete/invisible with serial tracking:** CH-01, CH-02, PARC-03,
  PARC-04, ADM-03, ADM-06, CPT-06, REF-01 and REF-05 through REF-08;
- **removed fields or ownership/acquisition concepts:** PARC-01, PARC-05 through
  PARC-08, CPT-01, CPT-03, CPT-04, CPT-05, REF-01 and REF-05;
- **direct equipment/product creation or import contradicting governed catalogue:**
  PARC-01, PARC-02 and related CSV templates;
- **direct receipt invalid and consumables limited to owned-only:** PARC-10;
- **removed M2M / `bi_sql` reporting:** PARC-11, CPT-14, CPT-15, INV-03 and ADM-12;
- **removed replacement-price setting:** ADM-12 and INV-03;
- **obsolete `WH/Stock` instead of `Bg/Stock`:** CH-02, ADM-03 and REF-07;
- **absolute links and numeric database IDs:** CPT-22 through CPT-26;
- **index/header errors:** remove “Base: artdubati”, correct the ADM-13 and CPT-26
  ranges, and include every current card;
- **obsolete import artifacts:** remove both CSV templates, not only references to them;
- index ranges and “Who reads what” omit purchasing, catalogue, equipment-approval and
  requester roles.

The keyword list above is not treated as exhaustive. The audit produces a verdict for
each of the 67 cards in each of FR, EN and FA (201 verdicts), plus templates, index and
exports. All FR cards are corrected semantically first, then EN/FA aligned and exports
rebuilt. Manual correction and role replay are blocking exit criteria. Human testers
receive the same no-real-host rule as Playwright and stop if a link leaves the neutral
audit hostname.

## 8. Owner decisions and functional gaps

Decisions D8–D10 were confirmed by the owner on 19/10/2026. D1–D7 remain recommendations
to confirm before security or campaign scripts are written:

| ID | Subject | Recommended decision |
| --- | --- | --- |
| D1 | Prohibited group combinations | Forbid the complete §3.1 matrix, especially Equipment Operator + Equipment Approver. Catalogue self-approval is already refused except for the autonomous exception, which remains outside the campaign. |
| D2 | Purchase reference path | Use P3's existing confirmed PO. Disable or restrict `purchase_mode=create` before acceptance. |
| D3 | Consumable entries/exits, adjustment and scrap | P2 cannot adjust, scrap or change consumable stock through any non-internal boundary outside a governed operation. P1 may do so only with explicit reason/evidence under a narrow server guard. |
| D4 | Structural configuration | Only accounting/config administration alters category accounting fields. P4 uses governed structural correction; P1 edits only a named operational subset. |
| D5 | P3/P6 RPC rights | Guard P3/P6 stock execution and P3 edits/deletion of operation-created draft bills. Characterise legitimate P6 purchase-order writes before guarding them so invoice matching is not broken. Menus are not controls. |
| D6 | Generic purchase request (G1/G3) | `purchase_request` is **not installed**. Evaluate adding it plus tier validation as a platform change, including route inventory, but only with a custom `tier.review` guard and least-privilege rules that prevent P8 reading all POs/moves. P8 must also be added explicitly to catalogue `REQUESTER_GROUPS`, with positive/negative tests. |
| D7 | Worksite consumption (G2) | Characterise `stock_request`, `stock_analytic` and `project_task_stock` after the accountant decides valuation. Until implemented, limit the milestone to transfer/use/return. |
| D8 — **confirmed** | Site actors | P10 requests/acknowledges through the future D6 purchase-request or D7 stock-request document; P2 alone executes stock. Until that document exists, P10 is not created and CH records the out-of-Odoo organisational request as an unvalidated gap. |
| D9 — **confirmed** | Ephemeral storage and retained copies | Use bounded `tmpfs`, subject to size/memory characterisation. Per-campaign encrypted storage with cryptographic erasure is only the audited fallback. Any unavoidable provider/session retention is declared instead of claiming deletion. |
| D10 — **confirmed** | Human/browser access | Use one stable neutral audit hostname, proxy authentication plus Odoo login, no campaign ID in DNS/certificate, and a separately audited proxy/DNS/network-policy change. |

Open accounting choices remain Mac Mini treatment, C24/C25 and category treatment. No
test choice becomes a production rule without accountant signoff.

## 9. Ordered roadmap and stop rules

1. Audit revision 5 and obtain decisions D1–D7; D8–D10 are confirmed.
2. Perform only the read-only server characterisation in section 5.1; audit its output.
3. Write and audit a lifecycle plan for the separate PostgreSQL/Odoo pair, backup
   exclusions, hostname, neutralisation and deletion proof.
4. Characterise and design S0 security hardening; implement/test/audit it separately.
5. Decide and, if in scope, implement G1/G3; decide whether G2 is pre-AI or later.
6. Correct the manual baseline and absolute-link mechanism.
7. Only then write clone/profile/scenario tools with dry-run/apply separation and audit.
8. Take the clean snapshot, create the pair and run the configuration window.
9. Freeze the business baseline; execute S0. Any unexpected right stops the campaign.
10. Execute S1–S7; replay corrections only on a new clone/campaign.
11. Execute S8, sanitise/sign evidence, confirm deletion, remove and verify everything.

No step in this plan authorises campaign creation or destructive cleanup yet.

## 10. Exit criteria before resuming the AI programme

- separate PostgreSQL/Odoo isolation and deletion proof are green;
- every profile has minimal audited rights and passes UI plus RPC negatives;
- catalogue, existing-PO purchase, durable/consumable receipt, bill modes, accounting,
  transfer, use, maintenance, return/restitution and monitor scenarios pass;
- G1/G3 and G2 are implemented, or the owner explicitly narrows the milestone;
- `rent_paid` is checked with an authorised accounting role;
- affected manuals are correct in FR/EN/FA and relative links work on desktop/mobile/RTL
  without contacting the real host;
- every business-window row diff is explained and no blocking/high defect remains;
- full tests, platform parity and route comparison are green after separate deployments;
- campaign containers, volumes, DB/WAL, filestore, sessions and raw artifacts are
  removed with a deletion certificate, subject to explicitly declared external retained
  copies under D9;
- no live write is attributable to the audit infrastructure; ordinary live writes are
  classified by author and no deployment occurs during an active campaign; production
  remains untouched.

## 11. Evidence used for revision 5

- independent audits of commits `1383a33`, `1411d1d` and `f79f839`, supplied on
  19/10/2026;
- installed security, access CSVs and server methods for product requests, equipment
  operations, stock, purchase, accounting and investor access;
- `docs/DEFINITIONS.md`, `docs/ROADMAP.md`, manual sources and generation rules;
- `docs/one_off_rental/LIVE_ACCEPTANCE_20261018.md`;
- existing backup/restore/deployment scripts, unsuitable for campaign clone creation
  until the separate lifecycle audit is complete.

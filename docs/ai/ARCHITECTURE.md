# AI assistant – architecture (IA-0, revision 4, 12/10/2026)

Design only; names are proposals for the audit. Revision 2: separate server, three
processes, asynchronous jobs, three AI functions. Revision 3: `jobs.db` / `ledger.db`,
explicit concurrency, `ack` after Odoo's commit, Docker-aware egress filtering. Revision 4:
SQLite settings fixed (§5.1), stack started only after the firewall is verified
(DEPLOYMENT.md §3.1).

## 1. Components

```
 Odoo VPS (unchanged infrastructure)            AI server (separate, D1)
 ┌───────────────────────────────┐             ┌──────────────────────────────────────────┐
 │ odoo_web                      │   mTLS +    │  ai_gateway (API + worker, jobs/ledger)  │
 │  module lartdubati_ai_assistant├──HMAC────►│   holds: Odoo HMAC key, server cert,     │
 │  - local confidentiality      │  HTTPS,     │          LiteLLM client key              │
 │    pre-check                  │  Odoo calls │   no provider key, no Internet route     │
 │  - searches, duplicates,      │  out only   │        │ net_llm (internal)  │ net_doc   │
 │    questions, draft mapping   │             │        ▼                     ▼ (internal)│
 │  - cron: submit / poll        │             │  ai_litellm (proxy)     ai_extractor     │
 │ odoo_db (never reachable from │             │   holds: provider keys   no secret,      │
 │  the AI server)               │             │   no UI, no DB           no egress,      │
 └───────────────────────────────┘             │        │ net_egress (internal) per-doc   │
                                               │        ▼                  child process  │
                                               │  ai_egress (CONNECT proxy, allow-list)   │
                                               └────────┬─────────────────────────────────┘
                                                        ▼ Internet: approved API hosts only
```

| Component | Holds | Talks to | Never |
|---|---|---|---|
| Odoo module | Odoo client cert + HMAC key (files, D16) | gateway (outbound HTTPS) | provider keys; calls to LiteLLM or providers; `sudo()` for final writes |
| `ai_gateway` | HMAC verification key, TLS server cert, LiteLLM client key, `jobs.db` (temporary) and `ledger.db` (financial metadata) | Odoo (answers only), LiteLLM, extractor | provider keys; Internet; PostgreSQL; Odoo account; writes to Odoo |
| `ai_litellm` | provider keys only | egress proxy | Odoo key; inbound from anything but the gateway; UI; database; retries or fallbacks of its own |
| `ai_extractor` | nothing | answers the gateway | network egress; secrets; files after the job |
| `ai_egress` | allow-list | approved API hosts | TLS interception; other hosts or raw IPs |

A compromise of LiteLLM exposes the provider keys (limited by provider-side spend caps and
key rotation) but not the Odoo HMAC key nor the client certificate; a compromise of the
extractor exposes neither.

## 2. Asynchronous jobs (D15)

```
Odoo cron (short run)                     ai_gateway API              ai_gateway worker
 ─ POST /v1/jobs {idempotency_key, …} ──► one transaction:
                                            job 'received' + budget
                                            reservation (or 402/409)
 ◄─ 202 {job_id, state} ────────────────
                                                                       claims 'received' → 'running'
                                                                       marks attempt_started
                                                                       calls extractor / LiteLLM
                                                                       one transaction: validate,
                                                                       'succeeded'|'failed', settle cost
 ─ GET /v1/jobs/{id} (later, backoff) ──► state, result when final
 Odoo validates, stores, COMMITS
 ─ POST /v1/jobs/{id}/ack (after commit) ► result purged from jobs.db (idempotent)
```

Result handling order in Odoo (revision 3, audit point 4):
1. `GET` the final job;
2. validate it (schema copy, then Odoo data, §6);
3. store it on the request (valid result, or the discard reason if invalid) and **commit**;
4. only then `POST …/ack`;
5. `ack` is idempotent: an already acknowledged or purged job answers `204`; a failed
   `ack` is retried by the next cron run; a never-acknowledged result is purged after
   7 days anyway. A crash between 3 and 4 only delays the purge; a crash before 3 loses
   nothing (the result is still in `jobs.db`).

- Odoo never waits on a model: each cron run submits and polls, then ends (seconds).
- Same `idempotency_key` + same body digest → the existing job (no second call); same key +
  other digest → 409.
- Provider answer arriving « late » is not a problem: there is no Odoo-side timeout on the
  job; the worker has its own call timeout per function.
- Worker crash after `attempt_started`: the lease expires → `failed` with
  `outcome_unknown`; **never retried automatically** (the provider may have billed); the
  reservation stays until the daily reconciliation with the provider's usage. A new
  attempt needs a user action and a new key.
- Worker crash before `attempt_started`: the job returns to `received` (nothing was sent).
- Results kept in `jobs.db` until acknowledged, at most 7 days; then purged (§5.1). A
  `POST` with the key of a purged job answers `410 result_purged` from the idempotency
  tombstone kept in `ledger.db`: never a second call.
- Worker concurrency is bounded explicitly (§5.2), not only by container memory.

## 3. What is AI and what is Odoo code

| Step | Implementation |
|---|---|
| Confidentiality pre-check of text and file type | **Odoo**, deterministic (SECURITY.md §4) |
| Understand the free text: intent, nature, search keys, amount / date / periodicity terms | **AI** `interpret_request` (`fast`) |
| Search partners, products, categories, contracts, stocks | **Odoo** ORM as the user (normalised names, VAT / SIREN, supplier references, `ilike`) |
| Duplicate checks | **Odoo**, the canonical keys already used by `product.creation.request` |
| Configuration check (allowed category for the intent, circuit available) | **Odoo**, mapping table intent → circuits → allowed categories; `missing_configuration` |
| Extract a document | extractor (local text / OCR) + **AI** `extract_document` (`document`) |
| Settle an ambiguity Odoo cannot settle (≥ 2 plausible candidates, or ≥ 2 allowed categories) | **AI** `resolve_ambiguity` (`fast`; `reasoning` only on the user's request, with its estimate) |
| Missing information and contradictions | **Odoo**: required fields of the target circuit vs the state; comparison of the user's values with extracted ones |
| Questions to the user | **Odoo**, translated templates per missing field (`.po`) |
| Proposal and mapping to a draft | **Odoo**, field whitelist per circuit |

Calls: text only 1; with documents 2; plus 1 if a real ambiguity remains.

## 4. Odoo module `lartdubati_ai_assistant`

### 4.1 Models (D8)

| Model | Purpose | Key fields |
|---|---|---|
| `lartdubati.ai.request` (mail.thread) | one need | name AIR/YYYY/NNNN, company, requester, text, state, intent, `confidentiality_detected`, `confidentiality` (≥ detected), `precheck_findings` (categories only, no values), outcome, `missing_configuration` (text), fingerprints (config, schema versions, candidates), « AI cost (excl. tax) », links to drafts |
| `lartdubati.ai.request.document` | supporting file | attachment, sha256, mimetype, size, pages, pre-check result |
| `lartdubati.ai.request.message` | questions / answers | template code, field, text, answer |
| `lartdubati.ai.proposal.line` | proposed value or object | kind (reuse / to_create / value / warning), target circuit, field (whitelist), value, choice ref, status (found / absent / ambiguous / contradictory / unsupported), evidence (page, excerpt ≤ 300 chars), user decision, corrected value |
| `lartdubati.ai.job` | one gateway job | idempotency key, function, profile, gateway job id, state, provider and exact model (as returned), prompt / schema / config versions, tokens, provider-currency cost, rate, EUR cost, document sha256, validation result, error code, fallback used |

No standard model is extended in IA-2 or IA-3.

### 4.2 States of a request

`draft → prechecked → submitted → interpreting → searching → extracting → needs_information
→ proposed → accepted / corrected / refused → drafted` plus `blocked_confidential`,
`missing_configuration`, `blocked_budget`, `failed`, `cancelled`. Steps without AI are run
by the same cron in its short runs.

### 4.3 Cron

One cron, triggered by `ir.cron._trigger()` on submission and re-armed with a backoff while
jobs are open (2 s, 5 s, 15 s, 60 s…):
1. requests to submit: build payload as the requester (`with_user`), POST, store the job id;
2. open jobs: GET; final results validated against Odoo data (§6), stored, **committed**,
   then acknowledged (`ack`, §2);
3. deterministic steps of requests whose jobs are done.

Each HTTP call has a short client timeout (10 s, just transport); a transport failure
leaves the job open on the Odoo side and the next run retries the same POST (idempotent)
or GET. Concurrent cron runs: a row lock `FOR UPDATE SKIP LOCKED` on the request (read
pattern of `ir.cron`; or Odoo 18's ORM helper if it has one, to check).

### 4.4 Groups

| Group | Rights |
|---|---|
| AI Assistant User | own requests; accept / refuse own proposals; « Prepare draft » only if `check_access('create')` on the target model succeeds as that user |
| AI Assistant Manager | company requests, cancel, job logs |
| AI Budget Manager | per-request budget override |

Company rule on every model; investors refused by phase 4's default deny (tested).

## 5. Gateway internals

### 5.1 Two databases: `jobs.db` (temporary) and `ledger.db` (financial metadata)

Revision 3 (audit point 1): one file could not be both purged after 7 days and backed up
for 13 months.

| | `jobs.db` | `ledger.db` |
|---|---|---|
| Content | job inputs (text, base64 files only while the job runs), validated results, errors | job id, request ref, opaque user ref, function, profile, route, provider, model, tokens, amounts in billing currency, rate, date and source, EUR equivalent, kind (reservation / settlement / reconciliation / manual correction), idempotency key and body SHA-256 with the final state (tombstone) |
| Never contains | – | document text, prompts, model output, extracted values, user text, file names |
| Lifetime | inputs deleted when the job ends; results deleted at `ack` or after 7 days; `secure_delete` on; `VACUUM` only in the maintenance window (below) | 13 months |
| Backup | **none** | daily online backup, encrypted, kept 13 months |
| Disk | encrypted volume of the AI server (DEPLOYMENT.md §2) | same, and encrypted backup target |

Atomicity across both files (revision 4, settings fixed):
- `ledger.db` is the **main** database; `jobs.db` is **attached** (`ATTACH`) on every
  connection;
- both files in the **same directory of the same encrypted filesystem** (`/opt/ai/data`),
  so the super-journal and both journals live on one filesystem;
- `PRAGMA journal_mode=DELETE` on both (never WAL: SQLite commits a transaction touching
  several attached databases atomically through its super-journal only when the main
  database is a file and the journal mode is not WAL);
- `PRAGMA synchronous=FULL` on both;
- one writer connection in the gateway (API and worker serialise their writes through it,
  `BEGIN IMMEDIATE`); throughput (a few jobs a minute) makes this sufficient;
- the gateway refuses to start if a pragma read back differs, or if the two files are not
  on the same filesystem (`st_dev` compared).

**Maintenance window for `VACUUM`** (weekly): the gateway answers new jobs with `503
maintenance`, waits until no job is `running`, runs `VACUUM` on `jobs.db` only, then
resumes; never during job execution. `ledger.db` is not vacuumed (append-mostly).

Tests: an application exception and a `SIGKILL` of the gateway during the commit, and a
**hard stop of the test machine** (reset of the virtual machine) during a loop of commits;
after restart, each transaction is either fully present in both files or absent from both
(T-S32).

`POST /v1/jobs` in one `BEGIN IMMEDIATE` transaction over both files:
1. lookup of the key in `ledger.db` (tombstone) and `jobs.db`: same digest → the job, or
   `410 result_purged` if its result is gone; other digest → 409;
2. kill switch, `REAL_DATA_ALLOWED` (false until D6), month and request caps with the
   **worst-case** estimate;
3. insert job `received` (`jobs.db`), reservation and tombstone (`ledger.db`);
4. commit → 202. Any failure → rollback of both.

Worker transition `received → running` by a conditional update with a lease. Final
transition (`jobs.db`), settlement and tombstone state (`ledger.db`) in one transaction.

### 5.2 Concurrency (audit point 2)

Explicit semaphores in the worker, configured in `profiles.yaml`; jobs beyond them wait in
`received`:

| Limit | 4 vCPU / 8 GB (recommended) | 2 vCPU / 4 GB (fallback option) |
|---|---|---|
| jobs running in total | 5 | 2 |
| document extractions (text layer) | 3 | 1 |
| OCR | 2 | 1 |
| calls to LiteLLM in flight | 5 | 2 |

The extractor enforces its own maximum of child processes (same values), so a gateway
bug cannot exceed them. The load test (DEPLOYMENT.md §6) runs at exactly these values.

### 5.3 Pipeline of a job

1. second confidentiality pre-check on the inputs (and on extracted text);
2. extraction through `ai_extractor` when documents are present;
3. chunk selection (only the chunks needed for the fields Odoo asked);
4. versioned prompt; untrusted content in a delimited data block;
5. call to `ai_litellm` with the profile's pinned route (explicit model alias, LiteLLM
   retries and fallbacks off); `attempt_started` recorded before;
6. strict validation (JSON Schema, enums of Odoo's references, evidence present in the
   chunks sent); refusal or truncation → `invalid_output` / `refused`;
7. fallback (D10) only on availability errors **before** any answer, only to an allowed
   route of an equal or stricter data policy, recorded.

## 6. Odoo re-validation before showing a proposal

References resolvable, readable by the user, active, same company; values within the
allowed lists; dates and amounts parse, tax basis explicit; excerpts found in the
extracted text of the cited page; config / schema / candidates fingerprints unchanged.
Failure → result discarded, job marked `invalid` on the Odoo side. The same check runs
again at « Prepare draft »; a change since the proposal → « re-run the assistant ».

## 7. Opaque references

Candidates are sent as `p1`, `cat3`… never database ids; the model answers with these or
`none_fits`; Odoo maps them back and re-checks access.

## 8. Document chain

1. Upload in Odoo; type by magic bytes (PDF, PNG, JPEG), ≤ 10 MB, ≤ 50 pages; Odoo
   pre-check on the file metadata (and on the text layer if Odoo can read it locally
   without new dependencies; otherwise the gateway's pre-check is the first one on the
   content, which happens on the company's own AI server, before any external call).
2. Gateway → extractor: one disposable sandboxed child process per document
   (SECURITY.md §8): text layer per page, OCR only for pages without text (D7).
3. Pre-check on extracted text; detected sensitive content → job `blocked_confidential`
   before any LiteLLM call.
4. Chunking per page / paragraph with `chunk_id`, page, document sha256.
5. Selection of the chunks needed; `extract_document` call.
6. Evidence (page, excerpt) shown next to each value; the user opens the attachment.

## 9. Routing configuration (AI server, not Odoo)

`profiles.yaml` for the gateway and `litellm_config.yaml` for LiteLLM, both mounted
read-only, in a private configuration repository, with their SHA-256 returned as
`config_version`. Values in angle brackets stay placeholders until §1.3 of PLAN.md.

```yaml
# profiles.yaml (gateway)
profiles:
  fast:      {route: r_fast,  max_cost_eur: <…>, timeout_s: 30}
  document:  {route: r_doc,   max_cost_eur: <…>, timeout_s: 120}
  reasoning: {route: r_reas,  max_cost_eur: <…>, timeout_s: 180}
  local:     {route: r_local, enabled: false}
routes:
  r_fast: {litellm_alias: fast-primary, provider: <P>, model: <MODEL_FAST>,
           policy: {entity: <provider entity>, dpa: <ref>, region: <global|us|eu>,
                    retention: <days|zdr>, training: none},
           fallbacks: []}            # owner adds routes here only with an equal or stricter policy
budget: {month_cap_eur: 50, request_cap_eur: 0.50, rate_source: <…>}
allowed_providers: [anthropic, openai]
```

Load-time refusal: unknown provider, `latest` or unpinned model, a fallback whose policy is
not equal or stricter on every attribute, OpenRouter. LiteLLM's own config defines only
the aliases (no router fallbacks, `num_retries: 0`).

## 10. Model and software updates

A model change is a configuration change with a short plan and a capped comparison run on
the synthetic scenario set. Prompt and schema versions are recorded per job. Software
updates (LiteLLM, FastAPI, base images): SECURITY.md §9.

## 11. Ollama later (IA-5)

A `local` route pointing LiteLLM to an Ollama host on a private link; Odoo sends
`profile: local` for confidential requests. No Odoo module change.

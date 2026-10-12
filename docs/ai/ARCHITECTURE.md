# AI assistant – architecture (IA-0, revision 1, 12/10/2026)

Design only. Names of models, fields and files are proposals for the audit.

## 1. Components

```
 Browser (Odoo user)
      │  standard Odoo web client, no new HTTP route
      ▼
 odoo_web ── module lartdubati_ai_assistant ───────────────┐
      │  (requests, messages, documents, proposals, logs)  │ ORM searches with the
      │  cron worker, outbound HTTPS/HTTP only             │ user's rights; drafts in
      │                                                    │ existing circuits (IA-3)
      │  HMAC-signed JSON, private network                 │
      ▼                                                    │
 lartdubati-ai-gateway (FastAPI) ──── no DB access, no Odoo account, no write to Odoo
      │   ├─ auth, limits, idempotency cache, cost ledger (SQLite, metadata only)
      │   ├─ minimisation (removal / pseudonymisation)
      │   ├─ prompt templates (versioned), JSON schemas (versioned)
      │   ├─ LiteLLM (library, pinned) ── profile → pinned provider/model
      │   └─ strict response validation
      │
      ├──► lartdubati-ai-extractor (no network egress, no secrets):
      │       type/size checks, text extraction, OCR (Tesseract), chunking, page refs
      │
      └──► egress allow-list: api.anthropic.com, api.openai.com (or eu.api.openai.com),
              later the Ollama host (IA-5)
```

`odoo_db` is never reachable from the gateway or the extractor (separate networks,
DEPLOYMENT.md §3).

### 1.1 Responsibilities

| Component | Does | Never does |
|---|---|---|
| Odoo module | holds the user's request and its history; checks rights; searches real records; builds the allowed lists; sends minimal payloads; validates the gateway answer **again** against Odoo data; shows proposals; creates drafts through business methods (IA-3); records costs and outcomes | call LiteLLM or a provider directly; store API keys; create posted / approved records automatically; use `sudo()` for final writes |
| Gateway | authenticates Odoo; enforces size, time and cost limits; idempotency; selects the profile's pinned model; removes / pseudonymises data; renders versioned prompts; calls LiteLLM; validates the JSON strictly; returns a proposal or a typed error | read or write PostgreSQL; hold an Odoo account; run model-supplied code; follow URLs; expose tools to the model; keep documents or full prompts |
| Extractor | parses untrusted files in isolation; returns text chunks with page numbers and the file's SHA-256 | reach the network; hold secrets; keep files after the call |
| LiteLLM (library) | provider adapters (OpenAI, Anthropic, Ollama), usage and cost reporting | routing or fallback on its own (router fallbacks and retries disabled; the gateway decides) |

## 2. Independence from existing circuits

- `lartdubati_ai_assistant` depends on `maintenance_shareholder_equipment` (to reach
  `product.creation.request` and `equipment.operation`), **never the reverse**. No
  existing view, method or constraint is changed; integration happens by calling the
  existing public methods (`create` of a request in draft, `action_submit` only if the
  user chooses to submit).
- Kill switch: setting `ai_assistant_enabled` (company, default **off**) plus the
  gateway's own `ENABLED=false`. Off: the menu shows the assistant as disabled, nothing is
  queued, the cron does nothing; all other menus are unaffected.
- Gateway down: requests stay `queued` or go to `failed` with a typed reason; the user
  continues with the standard forms. No existing screen waits on the gateway.
- Uninstalling the module removes its own models only.
- Tests (IA-2): the full test suites of `maintenance_shareholder_equipment` and
  `lartdubati_investor_home` pass with the module installed and the gateway unreachable.

## 3. Request lifecycle

```
draft ─submit─► queued ─cron─► processing ─┬─► needs_information ─answer─► queued
                                            ├─► proposed ─accept─► accepted ─prepare─► prepared (IA-3)
                                            │            ├─correct─► (accepted with corrections)
                                            │            └─refuse──► refused
                                            ├─► failed (typed reason; retry = new attempt, same idempotency key)
                                            └─► blocked_budget (needs override or next month)
any non-final state ─cancel─► cancelled
```

- `prepared`: the drafts it created are linked; their own circuits continue as usual.
- IA-4 adds `executing` / `done`, driven by the circuits' own states, never by the AI.

### 3.1 Steps of one processing run (orchestrated by Odoo, not by the model)

1. `classify_request` (text only).
2. Odoo searches candidates (partners, products, categories, contracts, stocks) with the
   user's rights and record rules, limited to the active company.
3. `find_existing_records` ranks those candidates (opaque references, §6).
4. If documents: extractor → `extract_document` on the relevant chunks only.
5. `identify_missing_information` → questions, or continue.
6. `propose_catalogue_objects` and/or `analyse_contract` and/or `prepare_operation`.
7. Odoo re-validation (§7) → `proposed` or `needs_information`.

Each step is one gateway call, recorded in the call log; a step that fails stops the run
with a typed reason. The sequence is code in Odoo, not chosen by the model: there is no
agent loop and no tool use.

## 4. Odoo module `lartdubati_ai_assistant`

### 4.1 Models (D8: request + children)

| Model | Purpose | Key fields |
|---|---|---|
| `lartdubati.ai.request` (mail.thread, activities) | one business need | `name` (AIR/YYYY/NNNN), `company_id`, `user_id` (requester), `text`, `state`, `classification` (selection from the catalogue of intents), `confidentiality` (selection), `idempotency_key` (UUID, unique), `config_fingerprint` (gateway config version + prompt and schema versions of the last run), `candidates_fingerprint` (SHA-256 of the candidate lists sent), `estimated_cost`, `actual_cost` « AI cost (excl. tax) », `cost_currency_id`, `budget_override_by`, `accepted_by`, `accepted_date`, `outcome` (accepted / corrected / refused), links to created drafts (`product_creation_request_ids`, later others) |
| `lartdubati.ai.request.document` | a supporting document | `attachment_id` (standard `ir.attachment`, `res_model` = the request), `sha256`, `mimetype`, `size`, `pages`, `extraction_state`, `ocr_used` |
| `lartdubati.ai.request.message` | questions and answers | `author` (assistant / user), `question_code`, `text`, `answer` |
| `lartdubati.ai.proposal.line` | one proposed value or object | `kind` (reuse_record / request_creation / field_value / warning), `target_model` (allowed list), `res_id` (only for reuse, checked), `field_name` (allowed list), `value_text`, `value_choice_ref`, `confidence`, `status` (found / absent / ambiguous / contradictory), `evidence` (page, excerpt ≤ 300 chars), `user_decision` (accept / correct / refuse), `corrected_value` |
| `lartdubati.ai.call.log` | one gateway call | `function`, `profile`, `provider`, `model` (exact, as returned by the gateway), `prompt_version`, `schema_version`, `start`, `duration_ms`, `input_tokens`, `output_tokens`, `cost` « (excl. tax) », `document_sha256`, `validation` (valid / invalid / refused / error), `error_code`, `fallback_used` |

No standard model is extended in IA-2. IA-3 adds at most a reverse link field on
`product.creation.request` **only if** the request form must show its origin; otherwise
the link stays on the AI side.

### 4.2 Groups and access

| Group | Rights |
|---|---|
| AI Assistant User | create / read own requests, accept or refuse own proposals into drafts (D9) |
| AI Assistant Manager | read all requests of the company, cancel, read call logs |
| AI Budget Manager | approve a per-request budget override (D11) |

Record rules: own requests for users, company rule (`company_id in company_ids`) for all.
Investor accounts: refused by the phase 4 default deny (`_get_allowed_models`); tested.
Proposal lines reference records only after Odoo has checked the user can read them.

### 4.3 Asynchronous processing without a transaction open during the call

- Submit: the request goes to `queued`; `ir.cron._trigger()` wakes a dedicated cron
  (`ir_cron_ai_process`), no `queue_job` (not installed; standard first).
- The cron, per request:
  1. claims it: row lock with `SELECT … FOR UPDATE SKIP LOCKED` (a read, the pattern
     `ir.cron` itself uses; or the ORM locking helper if Odoo 18 has one, to check in
     IA-2), state re-read, then `queued` → `processing` by an ORM write; a second worker
     skips the locked or no longer queued row; **commit**;
  2. builds the payload from the database (candidate searches run **as the requester**,
     `with_user(request.user_id)`, so lists respect their rights); stores the payload
     fingerprint; **commit**; from here no query is issued until the answer arrives, so
     no PostgreSQL transaction is open during the HTTP call (H-AI-2);
  3. calls the gateway with a timeout below `limit_time_real_cron`;
  4. stores the answer, validates it against Odoo data (§7), moves the state; **commit**.
- A crash between 1 and 4 leaves `processing` with a `processing_since`; a watchdog in the
  same cron puts it back to `queued` after a delay; the idempotency key makes the replay
  free (the gateway returns its cached result).
- Users see progress through the standard bus notification of `mail.thread` (no new
  route).

### 4.4 Configuration in Odoo

Company settings (no secret): enabled flag, gateway URL, key id, per-request warning
threshold, retention days. The HMAC secret is **not** in the database: Odoo reads it from
a file mounted read-only in `odoo_web` (path in `odoo.conf`, e.g. `ai_gateway_key_file`),
SECURITY.md §3.

## 5. Gateway pipeline (per call)

1. **Authenticate**: HMAC over method, path, timestamp, nonce, body digest; clock skew
   ≤ 60 s; nonce cache 5 min; unknown key id → 401.
2. **Kill switch / budget**: disabled → 503 `disabled`; month cap reached → 402
   `budget_exhausted`.
3. **Envelope validation**: input schema of the function and version; size limits;
   unknown fields refused.
4. **Idempotency**: same key + same body digest → cached result (24 h); same key +
   different digest → 409.
5. **Minimisation**: removal and pseudonymisation (SECURITY.md §5); mapping kept in memory
   for the call only, to restore names in the output where needed.
6. **Cost pre-check**: estimate (token count of the rendered prompt + max output) against
   the request cap and the remaining month budget; reservation in the ledger.
7. **Render prompt**: versioned template; system instructions fixed; untrusted content in
   a delimited data block (SECURITY.md §4); allowed lists embedded as enums in the output
   schema.
8. **Call LiteLLM**: pinned model of the profile; provider structured-output mode; no
   tools; temperature-free or minimal per provider; timeout.
9. **Validate**: JSON parse, JSON Schema (draft 2020-12, `additionalProperties: false`),
   enum membership, evidence references point to chunks actually sent, no value outside
   allowed lists; `refusal` / truncated → typed error, never repaired.
10. **Fallback** (D10): only on availability errors, only to the profile's allowed
    fallback with the same jurisdiction; recorded.
11. **Settle cost** in the ledger with the provider's reported usage; return result +
    usage + exact provider/model + versions.

## 6. Candidate lists and opaque references

Odoo never sends database ids to the gateway. Each candidate gets an opaque reference
(`p1`, `p2`, `cat3`…) mapped in the request's payload record. The model can only answer
with these references or `none_fits`. Odoo maps them back and checks the record is still
readable, active and of the right company. This makes « choose among a list » enforceable
and prevents id probing.

Candidate lists are built by Odoo with deterministic searches (normalised name,
`ilike`, VAT / SIREN when present, supplier references), capped (e.g. 20 per kind), and
the categories list contains **only** categories allowed for the classified intent
(configuration table in the module, e.g. insurance → insurance service categories).

## 7. Split between AI and Odoo rules

| Concern | AI (gateway) | Odoo |
|---|---|---|
| Understand the need | classify among intents Odoo sends | decide which circuit applies |
| Find records | rank Odoo's candidates | search with the user's rights, re-check the chosen ones |
| Category | choose among allowed refs or `none_fits` | define the allowed list, re-check |
| Account, tax | **never** proposed | from the category / product / fiscal position configuration |
| Capitalisation | **never** decided | from the category (`is_fixed_asset_stock`, asset profile) |
| Periodicity, dates | extracted only if present, with evidence; else `absent` | asks the user; validates coherence |
| Amounts | extracted with evidence, `tax_basis` stated (excl. / incl. / unknown) | compares with the user's text, flags contradictions; taxes from configuration |
| Duplicates | flags likely duplicates among candidates | runs the same canonical-key checks as the existing circuits |
| Create / submit / approve / execute / post / pay | **never** | existing methods and groups; the assistant only creates drafts (IA-3) |

**Odoo re-validation of every answer** (before `proposed`): references resolvable and
readable; values inside the allowed lists; dates parse and are coherent; amounts positive
and with an explicit tax basis; evidence excerpts actually present in the extracted text
of the referenced page (substring check); the config and candidates fingerprints still
match the current state. Any failure → the answer is discarded and logged as `invalid`.

## 8. Document chain

1. **Upload** in Odoo (standard attachment). Accepted: PDF, PNG, JPEG; size ≤ 10 MB;
   ≤ 50 pages (configurable). Checked on magic bytes, not on the extension.
2. **Antivirus**: none in IA-1/IA-2 (D14); the extractor's isolation is the control.
3. **Text extraction** (extractor): text layer of PDFs (pypdf / pdfminer); per page.
4. **OCR** only for pages without a usable text layer (D7, Tesseract fra+eng+fas).
5. **Chunking**: per page, then by headings / paragraphs, ~1 500 tokens per chunk, each
   with `doc_sha256`, `page`, `chunk_id`.
6. **Selection**: only the chunks needed for the function (keyword and layout heuristics
   for amounts, dates, parties, cover; then the model sees at most N chunks); the full
   document is never sent by default.
7. **Evidence**: every extracted value carries `chunk_id`, `page`, and an excerpt.
8. **Display**: the proposal shows the excerpt and page next to each value; the user can
   open the attachment at that page.

The file is passed from Odoo to the gateway in the request body (base64) and from the
gateway to the extractor on the internal network; neither keeps it after the call.

## 9. Routing configuration (gateway, not Odoo)

File `profiles.yaml`, mounted read-only, versioned in a **private** configuration
repository (not this repo if it names accounts; no secret in it), loaded at start; its
SHA-256 is the `config_version` returned with every answer.

```yaml
version: 2026-10-12.1
defaults: {timeout_s: 60, max_cost_eur: 0.50}
profiles:
  fast:
    primary:  {provider: anthropic, model: <pinned id>, inference_geo: <D6>}
    fallback: [{provider: openai, model: <pinned id>, region: <D6>}]
    max_cost_eur: 0.05
  document:
    primary:  {provider: anthropic, model: <pinned id>, inference_geo: <D6>}
    fallback: [{provider: openai, model: <pinned id>, region: <D6>}]
    max_cost_eur: 0.30
  reasoning:
    primary:  {provider: anthropic, model: <pinned id>, inference_geo: <D6>}
    fallback: []
    max_cost_eur: 0.50
  local:
    primary:  {provider: ollama, model: <pinned tag@digest>, base_url: <private>}
    enabled: false
allowed_providers: [anthropic, openai]       # anything else refused at load time
jurisdiction_rule: same_as_primary            # a fallback of another region is refused at load time
budget: {month_cap_eur: 50, request_cap_eur: 0.50, usd_eur_rate: <configured, conservative>}
```

Load-time checks refuse: an unknown provider, a model id without a pinned version or with
`latest`, a fallback whose region differs from the primary's, OpenRouter. Changing models
= edit, review, restart the gateway; the Odoo module does not change (§10).

## 10. Model updates

A new model or version is a configuration change with its own small plan: run the
recorded scenario set (fake answers replaced by a capped real run, COSTS.md §6), compare
the validation rate and the extracted values with the previous model, then switch. Prompt
and schema versions are bumped when templates change; Odoo stores them per call, so old
proposals stay explainable.

## 11. Ollama later (IA-5)

`local` is just another profile: LiteLLM's Ollama adapter, base URL on a private network
(probably another machine, PLAN.md §1.2). Odoo sends `profile: local` for requests whose
confidentiality requires it; nothing else changes. A test in IA-2 already proves the
module never sees provider names.

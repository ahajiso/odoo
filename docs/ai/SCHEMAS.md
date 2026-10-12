# AI assistant – Odoo ↔ gateway contract (IA-0, revision 4, 12/10/2026)

The contract belongs to the project. Revision 2: asynchronous jobs, three AI functions.
Sketches for the audit; IA-1 writes them as JSON Schema draft 2020-12 files, versioned in
the gateway repository and copied with the same hash into the Odoo module's tests.
`//` comments are for reading only.

## 1. Endpoints

**All**, `/v1/health` included, over HTTPS with mTLS and HMAC (SECURITY.md §3). Docker's own
health checks do not use these routes (DEPLOYMENT.md §3.2).

| Method and path | Purpose | Answer |
|---|---|---|
| `POST /v1/jobs` | create a job (or return the existing one for the same key and body) | `202` job; `402` budget; `403` confidentiality / real data before D6; `409` key conflict; `410` result purged (same key, job already acknowledged or expired: never a new call); `400` invalid; `503` disabled |
| `GET /v1/jobs/{job_id}` | state, and result when final | `200` |
| `POST /v1/jobs/{job_id}/ack` | sent by Odoo **only after its own commit** of the result; gateway purges the result from `jobs.db` | `204`, also when already acknowledged or purged (idempotent) |
| `GET /v1/health` | for Odoo's cron before submitting; mTLS + HMAC like every route; `{"status": "ok" \| "disabled" \| "maintenance"}`, no detail | `200` |

## 2. Jobs

### 2.1 Create

```json
{
  "contract_version": "2.0",
  "function": "extract_document",          // interpret_request | extract_document | resolve_ambiguity
  "function_version": "1.0",
  "idempotency_key": "uuid",               // unique per (request, step, user-initiated attempt)
  "request_ref": "AIR/2026/0001",
  "user_ref": "u-9f2a",                    // opaque
  "company_ref": "c-1",
  "profile": "document",
  "confidentiality": "internal",           // declared by Odoo, ≥ Odoo's detected level
  "precheck": {"detected": "internal", "categories": [], "synthetic": true},
  "language": "fr_FR",
  "limits": {"max_cost_eur": 0.30, "budget_override": null},
  "input": { … function-specific … }
}
```

The gateway recomputes the pre-check on every input; a result above the declared level, a
`restricted` / `confidential` level for an external profile, or real data before D6 →
`403 confidentiality_refused` and no job.

### 2.2 Job object

```json
{
  "job_id": "j-…", "idempotency_key": "…", "body_sha256": "…",
  "state": "received",                     // received | running | succeeded | failed
  "created_at": "…", "updated_at": "…",
  "reservation": {"amount": "0.21", "currency": "<provider billing currency>", "rate_to_eur": "…", "rate_date": "…"},
  "result": null,                          // when succeeded (validated) — §3
  "error": null,                           // when failed: {"code", "message", "retryable"}
  "meta": {
    "profile": "document", "route": "r_doc", "provider": "<as configured>", "model": "<exact id as returned>",
    "fallback_used": false, "policy_ref": "…",
    "prompt_version": "extract_document/1", "schema_version": "1.0", "config_version": "sha256:…",
    "usage": {"input_tokens": 0, "output_tokens": 0,
              "cost": {"amount": "0.00", "currency": "<billing>", "rate_to_eur": "…", "rate_date": "…", "eur": "0.00"}},
    "duration_ms": 0, "document_sha256": ["…"], "precheck": {"detected": "internal", "categories": []}
  }
}
```

State rules: `received → running → succeeded | failed`; `running → received` only if the
worker died before `attempt_started`. Creation, reservation and idempotency tombstone are
one transaction across `jobs.db` and `ledger.db`; the final state and the cost settlement
are another (ARCHITECTURE.md §5.1). After `ack` or 7 days the job object answers only its
metadata (`state`, `meta`), `result` is gone.

### 2.3 Error codes

| Code | When | Retry by Odoo |
|---|---|---|
| `invalid_input` | schema, size, unknown field, unsupported function version | no |
| `idempotency_conflict` | same key, other body | no |
| `confidentiality_refused` | pre-check (§2.1) | no |
| `budget_request_exceeded` / `budget_exhausted` | worst-case estimate above cap | no (override for the first) |
| `disabled` | kill switch | later, same key |
| `provider_unavailable` | primary and allowed fallbacks unavailable, nothing billed | user may resubmit, new key |
| `timeout` | worker's call timeout | user may resubmit, new key |
| `outcome_unknown` | worker lost after `attempt_started` | **never automatic**; user decides, new key |
| `invalid_output` / `refused` | validation failure / provider refusal | no (same input gives the same failure) |
| `extraction_failed` | unreadable file, OCR failure | no |

## 3. Result conventions

Extracted value:
```json
{"value": "1650.00" , "status": "found",   // found | absent | ambiguous | contradictory | unsupported
 "confidence": 0.86,                        // informative, never used alone
 "evidence": [{"chunk_id": "d1-p3-c2", "page": 3, "excerpt": "≤ 300 chars"}],
 "alternatives": [], "note": null}
```
`absent` ⇒ `value: null`; `found` without evidence ⇒ `invalid_output`. Amounts add
`currency` (from Odoo's list or `unknown`) and `tax_basis` (`excl_tax` / `incl_tax` /
`unknown`). Choices: `{"choice": "<ref from Odoo's list>" | null, "status": "chosen" |
"none_fits" | "ambiguous", "alternatives": [...], "justification": "≤ 300 chars"}`; the
`choice` enum is generated per job from Odoo's references. No schema contains an account,
a tax, a capitalisation decision or a free identifier.

## 4. Functions

| Function | Profile | Input limits | Worker timeout | Cost cap (default, placeholder until COSTS.md is verified) | Max confidentiality | On uncertainty |
|---|---|---|---|---|---|---|
| `interpret_request` | fast | text ≤ 8 000 chars; intents ≤ 30; natures ≤ 50 | 30 s | `<CAP_FAST>` | internal | `intent: none_fits` / `ambiguous`; terms `absent` |
| `extract_document` | document | ≤ 3 files, ≤ 10 MB, ≤ 50 pages each; ≤ 40 chunks sent; ≤ 25 fields | 120 s | `<CAP_DOC>` | internal | `absent` / `ambiguous` / `contradictory` |
| `resolve_ambiguity` | fast (reasoning on user request) | ≤ 20 candidates; context ≤ 10 KB | 30 s (180 s) | `<CAP_FAST>` (`<CAP_REAS>`) | internal | `none_fits` / `ambiguous` |

The request total is capped at 0.50 € (D11) across its jobs.

### 4.1 `interpret_request`

Input: `{"text": "…", "allowed_intents": [{"ref": "i1", "code": "recurring_service", "label": "…"}], "allowed_natures": [{"ref": "n1", "code": "insurance", "label": "…"}]}`

Output:
```json
{"intent": {choice}, "nature": {choice},
 "search_terms": {"partner": ["AXA"], "product": ["RC professionnelle"], "reference": []},
 "amounts": [{amount with evidence: chunk_id "text", excerpt "1 800 € par an"}],
 "periodicity_term": {extracted value},      // the user's words, not a periodicity code
 "date_terms": [{extracted value}],
 "documents_announced": true}
```
Odoo turns terms into searches and into codes through its own tables.

### 4.2 `extract_document`

Input: `{"document_kind_hint": "insurance_policy" | "bill" | "quote" | "contract" | "unknown", "files": [{"name", "mimetype", "sha256", "content_b64"}], "fields": ["partner_name", "policy_number", "cover", "premium", "periodicity", "start_date", "end_date", "notice_period", "renewal", "…"], "allowed_currencies": ["EUR", "TRY"], "allowed_periodicities": [{"ref": "pm", "code": "monthly"}, {"ref": "py", "code": "yearly"}]}`

`fields` and their order come from Odoo's table per intent and document kind (contract
clauses included: this replaces revision 1's `analyse_contract`).

Output: `{"document_kind": {choice among the hint list}, "fields": {name → extracted value | amount | choice}, "lines": [{"description", "quantity", "unit_price"}], "warnings": [{"code": "instruction_like_text" | "low_ocr_quality" | "pages_skipped", "page": 2}]}`

### 4.3 `resolve_ambiguity`

Called only when Odoo's deterministic matching leaves ≥ 2 plausible candidates (or ≥ 2
allowed categories).

Input: `{"kind": "partner" | "product" | "category" | "contract", "subject": {terms and extracted values}, "candidates": [{"ref": "p1", "label": "AXA France IARD", "attributes": {"city": "Paris", "vat": "FR…"}}]}`

Output: `{"selection": {choice}}`

## 5. Idempotency

- Key generated by Odoo per (request, step, user-initiated attempt); Odoo's automatic
  retries of a transport error reuse it (same job, no second call).
- Unique key in `ledger.db` (tombstone, kept 13 months) and in `jobs.db`; body SHA-256
  compared; a key whose result was purged answers `410`, never a new call.
- A new attempt after `timeout`, `provider_unavailable` or `outcome_unknown` is a user
  action with a new key, after the estimate is shown again.

## 6. Versioning

`contract_version` major → new path prefix (`/v2`), previous one served for one Odoo
release. `function_version`: Odoo validates outputs strictly, so any output change is a
new function version, requested explicitly by Odoo. `prompt_version` changes freely and is
recorded per job. Schema files carry their SHA-256, checked by Odoo's tests.

## 7. Fake provider

In test mode the gateway points to a fake LiteLLM that returns recorded answers per
(function, fixture), and can delay, fail (5xx / 429), time out, truncate, refuse, return
invalid JSON, or die after `attempt_started`. A real provider key in the test environment
makes the test suite fail.

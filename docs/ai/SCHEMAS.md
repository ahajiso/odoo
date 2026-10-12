# AI assistant – Odoo ↔ gateway contract (IA-0, revision 1, 12/10/2026)

The contract belongs to the project, not to a provider or to LiteLLM. Schemas below are
sketches for the audit; IA-1 writes them as JSON Schema draft 2020-12 files, versioned in
the gateway repository and copied (same hash) into the Odoo module's tests.

## 1. Transport and envelope

`POST /v1/<function>` on the private network, JSON, HMAC headers (SECURITY.md §3).
`GET /v1/health` (no auth, returns only `{"status": "ok" | "disabled"}`).

Request envelope (every function; `//` comments are for reading only, JSON has none):

```json
{
  "contract_version": "1.0",
  "function": "extract_document",
  "function_version": "1.0",
  "idempotency_key": "6f1c…-uuid",
  "request_ref": "AIR/2026/0001",
  "user_ref": "u-9f2a",                 // opaque, stable per Odoo user, no login
  "company_ref": "c-1",
  "profile": "document",                // fast | document | reasoning | local | fallback
  "confidentiality": "internal",        // public | internal | confidential | restricted
  "language": "fr_FR",                  // answer language for questions and explanations
  "limits": {"max_cost_eur": 0.30, "timeout_s": 60, "budget_override": null},
  "input": { … function-specific … }
}
```

Response envelope:

```json
{
  "contract_version": "1.0",
  "function": "extract_document",
  "function_version": "1.0",
  "idempotency_key": "…",
  "status": "ok",                        // ok | error
  "result": { … function-specific, validated … },
  "error": null,                         // {"code": "...", "message": "...", "retryable": bool}
  "meta": {
    "profile": "document", "provider": "anthropic", "model": "<exact id>",
    "fallback_used": false, "inference_region": "<as configured>",
    "prompt_version": "extract_document/3", "schema_version": "1.0",
    "config_version": "sha256:…",
    "usage": {"input_tokens": 0, "output_tokens": 0, "cost_eur": 0.0, "cost_usd": 0.0},
    "duration_ms": 0, "document_sha256": ["…"], "cached": false
  }
}
```

`budget_override`: `null`, or `{"approved_by": "u-…", "max_cost_eur": 1.20}` set by Odoo
only for a member of « AI Budget Manager ».

### 1.1 Error codes

| Code | HTTP | Retryable | Meaning |
|---|---|---|---|
| `unauthenticated` | 401 | no | bad signature, timestamp or nonce |
| `invalid_input` | 400 | no | envelope or input schema failure, unknown field |
| `too_large` | 413 | no | size limit of §3 exceeded |
| `idempotency_conflict` | 409 | no | same key, different body |
| `budget_request_exceeded` | 402 | no (override) | estimate above the request cap |
| `budget_exhausted` | 402 | no | month cap reached |
| `confidentiality_refused` | 403 | no | level not allowed for any enabled profile |
| `disabled` | 503 | later | kill switch |
| `provider_unavailable` | 503 | yes | primary and allowed fallbacks unavailable |
| `timeout` | 504 | yes | time limit reached |
| `invalid_output` | 502 | no (same input) | model answer failed validation; never repaired |
| `refused` | 502 | no | provider refusal |
| `extraction_failed` | 422 | no | file unreadable, OCR failed |

## 2. Common result conventions

### 2.1 Extracted value

```json
{
  "value": "1650.00",                 // string, normalised (ISO dates, dot decimals) or null
  "status": "found",                  // found | absent | ambiguous | contradictory | unsupported
  "confidence": 0.86,                 // 0..1, informative only; never used alone to accept
  "evidence": [{"chunk_id": "d1-p3-c2", "page": 3, "excerpt": "Prime annuelle HT : 1 650,00 €"}],
  "note": "string ≤ 300 chars or null"
}
```

- `absent`: nothing in the inputs; `value` must be `null`. The model is instructed that
  inventing is an error; the gateway refuses a `found` value without evidence.
- `ambiguous`: several readings; `alternatives` (≤ 5) each with evidence.
- `contradictory`: the document and the user's text (or two pages) disagree; both sides
  given with evidence.
- Excerpts ≤ 300 characters; `chunk_id` must be one sent in the call.

### 2.2 Choice among Odoo's list

```json
{"choice": "cat3" , "status": "chosen", "confidence": 0.7, "justification": "≤ 300 chars"}
{"choice": null, "status": "none_fits", "justification": "…"}
{"choice": null, "status": "ambiguous", "alternatives": ["cat3", "cat5"], "justification": "…"}
```

`choice` is an enum generated per call from the references Odoo sent. There is **no**
field for an account, a tax, a capitalisation decision or a new identifier anywhere in
the output schemas.

### 2.3 Amounts

`{"amount": "1650.00", "currency": "EUR", "tax_basis": "excl_tax" | "incl_tax" | "unknown", …extracted value fields}`.
`currency` must be one of the currencies Odoo lists as active; otherwise `unknown`.

### 2.4 Questions

`{"code": "missing_start_date", "field": "start_date", "question": "…", "blocking": true, "options": ["…"] | null}`
Only blocking questions by default; at most 5 per call.

## 3. Functions

Common limits: `contract_version` 1.0; JSON body ≤ 15 MB (documents base64 included);
text inputs ≤ 8 000 characters; one call ≤ its `timeout_s`; the cost cap is the smaller
of the request's `max_cost_eur` and the profile's.

| Function | Default profile | Input limit | Timeout | Cost cap (default) | Confidentiality max | On uncertainty |
|---|---|---|---|---|---|---|
| `classify_request` | fast | text ≤ 8 000 chars | 20 s | 0.02 € | internal | `intent: unknown` + question |
| `extract_document` | document | ≤ 3 files, ≤ 10 MB each, ≤ 50 pages each; ≤ 40 chunks sent | 90 s | 0.30 € | internal | values `absent` / `ambiguous` / `contradictory` |
| `find_existing_records` | fast | ≤ 20 candidates per kind, ≤ 6 kinds | 20 s | 0.02 € | internal | `none_fits` / `ambiguous` |
| `identify_missing_information` | fast | the current structured state ≤ 20 KB | 20 s | 0.02 € | internal | lists the questions, never guesses |
| `propose_catalogue_objects` | fast (reasoning if ambiguous) | state ≤ 30 KB, allowed categories ≤ 50 | 30 s | 0.10 € | internal | `none_fits` + question |
| `analyse_contract` | document / reasoning | chunks ≤ 40 | 120 s | 0.50 € | internal | clause `absent`; contradictions listed |
| `prepare_operation` | reasoning | state ≤ 40 KB | 120 s | 0.50 € | internal | `needs_information` instead of a proposal |

### 3.1 `classify_request`

Input:
```json
{"text": "…", "allowed_intents": [
   {"ref": "i1", "code": "recurring_service", "label": "Recurring service (subscription, insurance, telecom…)"},
   {"ref": "i2", "code": "equipment_purchase", "label": "…"}, …],
 "allowed_natures": [{"ref": "n1", "code": "insurance"}, …]}
```
Output:
```json
{"intent": {"choice": "i1", "status": "chosen", "confidence": 0.9, "justification": "…"},
 "nature": {"choice": "n1", …},
 "mentions": {"partner_names": ["AXA"], "product_terms": ["RC professionnelle"],
              "amounts": [{"amount": "1800.00", "currency": "EUR", "tax_basis": "unknown", "status": "found", "evidence": [{"chunk_id": "text", "excerpt": "1 800 € par an"}]}],
              "periodicity_terms": ["par an"], "date_terms": ["1er janvier"]},
 "documents_expected": ["insurance_policy"],
 "questions": []}
```
`mentions` are search keys for Odoo, not decisions.

### 3.2 `extract_document`

Input: `{"document_kind_hint": "insurance_policy" | "bill" | "quote" | "contract" | "unknown", "files": [{"name": "…", "mimetype": "application/pdf", "sha256": "…", "content_b64": "…"}], "fields": ["partner_name", "policy_number", "insured_party", "cover", "premium", "periodicity", "start_date", "end_date", "notice_period", "renewal", "deductible", "limits", "bill_number", "bill_date", "lines"], "allowed_currencies": ["EUR", "TRY"]}`

`fields` is chosen by Odoo per intent; the model answers only those.

Output: `{"document_kind": {extracted value}, "fields": {"premium": {amount}, "start_date": {extracted value}, …}, "lines": [{"description": {…}, "quantity": {…}, "unit_price": {amount}}], "warnings": [{"code": "instruction_like_text", "page": 2}]}`

### 3.3 `find_existing_records`

Input: `{"query": {mentions and extracted values}, "candidates": {"partner": [{"ref": "p1", "name": "AXA France IARD", "vat": "FR…", "city": "Paris"}], "product": [{"ref": "pr4", "name": "Assurance RC Pro", "category": "Services / Insurance"}], "contract": [{"ref": "k2", "partner_ref": "p1", "name": "…", "date_start": "2025-01-01", "date_end": null}]}}`

Output: `{"partner": {choice}, "product": {choice}, "contract": {choice}, "duplicates": [{"kind": "contract", "ref": "k2", "reason": "same partner and cover, running", "confidence": 0.8}]}`

Odoo shows duplicates as warnings and runs its own canonical-key checks anyway.

### 3.4 `identify_missing_information`

Input: `{"intent": "recurring_service", "required_fields": ["partner", "product", "amount", "periodicity", "start_date"], "state": {field → extracted value or chosen ref}}`
Output: `{"missing": ["start_date"], "contradictions": [{"field": "premium", "sides": [{…evidence…}, {…}]}], "questions": [question…]}`

`required_fields` come from Odoo (the target circuit's mandatory fields), not from the
model.

### 3.5 `propose_catalogue_objects`

Input: `{"intent": …, "state": …, "allowed_categories": [{"ref": "cat3", "path": "Services / Insurance", "kind": "service"}], "allowed_uom": [{"ref": "u1", "name": "Units"}], "existing_choice": {"product": "pr4" | null}}`
Output: `{"objects": [{"action": "reuse", "kind": "product", "ref": "pr4"} | {"action": "request_creation", "kind": "product", "name": {extracted value}, "category": {choice}, "uom": {choice}, "product_type": {"choice": "service", …}, "justification": "…"}], "questions": […]}`

`action: request_creation` becomes a **draft `product.creation.request`** in IA-3, filled
only with values the user accepted; the catalogue manager's circuit applies unchanged.

### 3.6 `analyse_contract`

Input: chunks + `fields` (`parties`, `object`, `cover`, `start_date`, `end_date`,
`duration`, `renewal`, `notice_period`, `price`, `indexation`, `periodicity`,
`termination`, `special_conditions`).
Output: each field as an extracted value; `periodicity` as a choice among Odoo's list
(`monthly`, `quarterly`, `yearly`, …) or `absent`; `risks` (≤ 10 notes with evidence,
informative).

### 3.7 `prepare_operation`

Input: the accepted state + `target_circuit` (choice Odoo made: `product_creation_request`,
`equipment_operation_receipt`, `recurring_contract` when ROADMAP A exists) + that
circuit's field list and allowed values.
Output: `{"status": "ready" | "needs_information", "fields": {field → value or choice}, "questions": […], "summary": "≤ 1 000 chars, user language"}`

Odoo maps `fields` onto the circuit's draft **only** for fields of its whitelist; every
other key is an `invalid_output`.

## 4. Idempotency

- Key: UUID generated by Odoo per (request, step, attempt group); a retry of the same
  step reuses it.
- Gateway: result cached 24 h with the body digest; same key + same digest → cached
  answer, `meta.cached: true`, cost 0; same key + other digest → 409.
- Odoo: one `call.log` per key; a duplicate answer does not add cost twice.

## 5. Versioning

- `contract_version` (envelope): major change = new path `/v2`; the gateway serves the
  previous major for one Odoo release.
- `function_version`: Odoo validates outputs strictly (unknown fields refused), so any
  output change, even a new optional field, is a new function version; Odoo names the
  version it accepts in each request and the gateway answers in that version or refuses
  with `invalid_input`.
- `prompt_version` changes freely (no contract change) but is recorded per call.
- Schema files carry their SHA-256; Odoo tests check the copy matches.

## 6. Fake provider

The gateway's test mode replaces LiteLLM by a fake provider that returns recorded JSON per
(function, fixture id), can delay, fail with 5xx / 429 / timeout, truncate, refuse, or
return invalid JSON. All tests of IA-1 to IA-4 use it; an environment variable with a real
key makes the test suite **fail** (guard against paid calls).

# AI assistant – costs (IA-0, revision 1, 12/10/2026)

All amounts excl. tax. Providers bill in USD; the budget is in EUR (D11). Estimates to
be replaced by measurements of the IA-1 acceptance run (H-AI-5).

## 1. Prices used

### 1.1 Anthropic (official price list, cached 06/10/2026)

| Model (pinned id) | Input $/M tokens | Output $/M tokens | Candidate profile |
|---|---|---|---|
| Claude Haiku 5.5 (`claude-haiku-5-5`) | 0.10 (prompts ≤ 100 K; 0.50 beyond) | 0.50 (2.50 beyond) | `fast` |
| Claude Sonnet 5.5 (`claude-sonnet-5-5`) | 2.00 | 10.00 | `document` |
| Claude Opus 5.5 (`claude-opus-5-5`) | 4.00 | 20.00 | `reasoning` |

- `inference_geo: "us"` costs ×1.1 on every token category; `"global"` is the standard
  price (D6).
- Thinking tokens are billed as output and count inside `max_tokens`, so a call's worst
  case is bounded by its `max_tokens` (§5).
- Prompt caching (cache reads cheaper than input) can lower the cost of the fixed system
  prompt + schema; not counted below (conservative).

### 1.2 OpenAI (fallback; **not verified**, secondary sources disagree)

Third-party price lists of August–October 2026 give, per million tokens, about
0.05 / 0.40 $ (nano tier), 0.25 / 2.00 $ (mini tier), 0.75 / 4.50 $ (a newer mini).
Model identifiers and prices are to be taken from OpenAI's official pricing page in IA-1
before pinning D4's fallback. The EU residency endpoint adds about 10 % on recent models
(PLAN.md §1.4).

### 1.3 Infrastructure

Option (a) of D1: no extra cost. Option (b): a small VPS (2 vCPU / 4 GB class), to be
quoted by the owner. Ollama (IA-5): a larger machine, to size after measuring volumes.

## 2. Models per profile (D4, proposal)

| Profile | Primary | Fallback | Why |
|---|---|---|---|
| `fast` | Claude Haiku 5.5, effort `low` | OpenAI mini tier (id to pin) | classification, ranking among a short list, questions |
| `document` | Claude Sonnet 5.5, effort `medium` | OpenAI model of comparable tier (id to pin) | long inputs, extraction with evidence |
| `reasoning` | Claude Opus 5.5, effort `medium` | none by default (D10) | ambiguous or contradictory files only |
| `local` | Ollama, model to choose in IA-5 | none | confidential documents |

## 3. Estimates per function

Tokens include the fixed instructions and schema (~1 500 tokens). Output includes
thinking. Cost at `"global"` prices.

| Function | Profile / model | Input tokens | Output tokens (max_tokens) | Typical $ | Worst case $ at max_tokens |
|---|---|---|---|---|---|
| `classify_request` | fast / Haiku 5.5 | 2 500 | 800 (2 000) | 0.0007 | 0.0013 |
| `find_existing_records` | fast / Haiku 5.5 | 4 000 | 800 (2 000) | 0.0008 | 0.0014 |
| `identify_missing_information` | fast / Haiku 5.5 | 3 000 | 600 (2 000) | 0.0006 | 0.0013 |
| `propose_catalogue_objects` | fast / Haiku 5.5 | 5 000 | 1 500 (3 000) | 0.0013 | 0.0020 |
| `extract_document` (10 pages, ~15 chunks) | document / Sonnet 5.5 | 25 000 | 4 000 (8 000) | 0.09 | 0.13 |
| `extract_document` (50 pages, 40 chunks) | document / Sonnet 5.5 | 60 000 | 6 000 (8 000) | 0.18 | 0.20 |
| `analyse_contract` | document / Sonnet 5.5 | 40 000 | 5 000 (10 000) | 0.13 | 0.18 |
| `analyse_contract` | reasoning / Opus 5.5 | 40 000 | 5 000 (10 000) | 0.26 | 0.36 |
| `prepare_operation` | reasoning / Opus 5.5 | 10 000 | 6 000 (12 000) | 0.16 | 0.28 |
| `propose_catalogue_objects` escalated | reasoning / Opus 5.5 | 5 000 | 1 500 (4 000) | 0.05 | 0.10 |

Per business request (all its calls):

| Request type | Calls | Typical $ |
|---|---|---|
| Text only (« a ChatGPT subscription at 20 € a month ») | classify, find, missing, propose | ≈ 0.004 |
| With one 10-page document (RC Pro) | + extract | ≈ 0.10 |
| Complex (contract analysis + operation, Sonnet then Opus) | + analyse (Sonnet) + prepare (Opus) | ≈ 0.39 |
| Complex, contract analysis on Opus instead of Sonnet | | ≈ 0.51 → **above the 0.50 € cap**: confirmation needed |

Hence: `analyse_contract` stays on `document` by default; `reasoning` only when the
previous step returned `ambiguous` / `contradictory`, and it is shown to the user before
the call with its estimate.

## 4. Monthly scenarios

+10 % for retries and invalid outputs; +10 % if `inference_geo: "us"`. Caps are computed
at 1 USD = 1 EUR (conservative; the real rate is lower), so the figures are also the
upper bound in EUR.

| Scenario | Requests / month | Mix | Estimate $ (and € upper bound) |
|---|---|---|---|
| Light | 40 | 20 text, 20 with a document | ≈ 2.3 |
| Medium | 150 | 60 text, 70 document, 20 complex | ≈ 16.5 |
| Heavy | 400 | 150 text, 200 document, 50 complex | ≈ 44.1 → close to the 50 € cap |

The 50 € cap covers the medium scenario three times; the heavy one approaches it, which is
the moment to measure and decide (prompt caching, smaller chunk selection, `local`).

## 5. Limits and how they are enforced (D11)

| Limit | Default | Where | Behaviour |
|---|---|---|---|
| Month cap | 50 € | gateway ledger (authoritative), provider-side spend limit as a second barrier | at 80 %: alert; at 100 %: every call answers `budget_exhausted`, Odoo shows it, standard circuits unaffected |
| Per business request | 0.50 € | gateway, using the sum already spent by the request (Odoo sends it, the gateway checks its own ledger by `request_ref`) | call refused with the estimate; Odoo asks for an override |
| Per call | profile / function caps (SCHEMAS.md §3) | gateway | estimate = counted input tokens × input price + `max_tokens` × output price; above the cap → refused before calling |
| Override | per request, up to an amount | Odoo group « AI Budget Manager »; recorded on the request and in the ledger | never raises the month cap |
| Acceptance runs (real calls in IA-1 / model changes) | 5 € per run | separate provider project and key with its own provider-side limit | stops at the cap |

Reservation then settlement: before the call the worst case is reserved in the ledger;
after the call the reservation is replaced by the provider's reported usage. A crash
leaves the reservation (conservative) until a daily reconciliation.

All amounts configurable in `profiles.yaml` (gateway) and in the Odoo settings for the
display thresholds; changing them needs no module update.

## 6. Measurement

Recorded per call (Odoo `lartdubati.ai.call.log` and gateway ledger): function, profile,
provider, exact model, input / output tokens, cost in USD and EUR (rate used), user,
request, date. Reports (standard Odoo pivot on the call log, labelled « AI cost (excl.
tax) »): cost per month, function, profile, user, outcome (accepted / corrected /
refused), so the cost of refused proposals is visible.

Monthly check: ledger total versus the provider's usage page and bill; difference > 5 %
investigated.

The providers' bills themselves go through the existing supplier bill circuit (software /
SaaS category, C25); the ledger is a control, not an accounting record.

## Sources

- Anthropic prices: Claude API price list (cached 06/10/2026); `inference_geo` pricing:
  [data residency](https://platform.claude.com/docs/en/manage-claude/data-residency)
- OpenAI (secondary, to confirm): [spendlint.dev](https://spendlint.dev/pricing/openai-api),
  [morphllm.com](https://www.morphllm.com/openai-api-pricing),
  [benchlm.ai](https://benchlm.ai/openai/api-pricing)

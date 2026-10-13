# AI assistant – costs (IA-0, revision 3, 12/10/2026)

**Not a budget basis.** Model identifiers and prices are placeholders until verified on
the providers' official pricing pages and the owner's accounts (PLAN.md §1.3). This
document gives what does not depend on them: calls per request, token estimates, the cost
formula, the caps and the ledger. All amounts excl. tax.

## 1. Calls per request (revision 2)

| Request | AI calls | Functions |
|---|---|---|
| Text only | 1 | `interpret_request` |
| With documents | 2 | + `extract_document` |
| Real ambiguity left by Odoo's matching | +1 | `resolve_ambiguity` |
| Blocked by the pre-check | 0 | – |
| Out of scope (e.g. consignment) | 1 | `interpret_request` only |
| `missing_configuration` | same as above: 1 without document, 2 with | the extraction still runs so the structured proposal is complete for an authorised person (scenario S1) |

Revision 1 needed five to seven calls; searches, duplicates, questions and draft mapping
are now Odoo code (ARCHITECTURE.md §3).

## 2. Token estimates (ours, to measure in the acceptance run, H-AI-5)

Input includes fixed instructions and schema (~1 500 tokens); output includes any
reasoning tokens the model bills as output; `max_tokens` bounds the worst case.

| Function | Profile | Input tokens | Output tokens typical | `max_tokens` |
|---|---|---|---|---|
| `interpret_request` | fast | 2 500 | 800 | 2 000 |
| `extract_document`, 10 pages (~15 chunks) | document | 25 000 | 4 000 | 8 000 |
| `extract_document`, 50 pages (40 chunks) | document | 60 000 | 6 000 | 8 000 |
| `resolve_ambiguity` | fast | 3 000 | 500 | 1 500 |
| `resolve_ambiguity` | reasoning | 3 000 | 2 000 | 6 000 |

## 3. Formula

For a call on a route with input price `Pi` and output price `Po` (per million tokens, in
the provider's billing currency), region uplift `u` (1 if none), and rate `r` to EUR:

- typical cost = `(in × Pi + out × Po) / 1e6 × u × r`
- worst case reserved = `(in_counted × Pi + max_tokens × Po) / 1e6 × u × r`

`in_counted` comes from the provider's token-counting method when it has one, otherwise a
conservative character-based estimate (+20 %).

Illustration with **unverified** candidate prices (to be replaced): if `fast` were
0.10 / 0.50 and `document` 2 / 10 per million tokens, a request with a 10-page document
would cost about 0.0007 + 0.09 ≈ 0.09 in the billing currency, and its worst-case
reservation about 0.0013 + 0.13 ≈ 0.13. These figures only show the order of magnitude
against the 0.50 € cap; they are not a commitment.

Monthly scenarios (number of requests × mix) are recomputed in IA-1 once prices are
verified; the inputs will be: requests per month, share with documents, average pages,
share with ambiguity, +10 % retries and invalid outputs.

## 4. Caps, ledger and currency (D11)

| Limit | Default | Enforced by | Behaviour |
|---|---|---|---|
| Month cap | 50 € | gateway ledger (authoritative); provider-side spend limit as a second barrier | 80 %: alert; 100 %: `budget_exhausted` for every new job; existing circuits unaffected |
| Per request (all its jobs) | 0.50 € | gateway, by `request_ref` in its own ledger | `budget_request_exceeded` with the estimate; override by « AI Budget Manager » per request, recorded; never above the month cap |
| Per job | per function (`<CAP_…>`, SCHEMAS.md §4) | gateway, worst-case reservation | refused before the job is created |
| Acceptance runs | 5 € per run | separate provider project and key with its own provider-side limit | stops at the cap |

Ledger rows in `ledger.db`, financial metadata only (one transaction with the job,
ARCHITECTURE.md §5.1):
`job_id`, `request_ref`, `user_ref`, function, profile, **budget period** (month of the
reservation, kept by every later row of the job), route, provider, model (configured
catalogue only), kind (cost lines `reservation` / `settlement` / `manual_correction`;
cancellation lines `release` / `reversal`; `reconciliation` with WP4), **amount in the provider's billing currency**, currency, **rate
to EUR and its date and source** (configured list), EUR equivalent, tokens, SHA-256 of the
provider's request id. A cancellation (`release` for the reservation, `reversal` for a
settlement or a correction) is the exact negative of one cost line, with the same rate,
date and source, and names it (`reverses_id`); no row is ever modified, every row is true
by itself (`eur = amount × rate`). No free text in any row.
Caps are compared in EUR with the rate of the day from the configured source (to choose:
the ECB reference rate, or a fixed conservative rate set by the owner); the original
amount and rate are kept so a later reconciliation never rewrites history.

Reservation → settlement: the worst case is reserved at creation; the provider's reported
usage replaces it at the end.

`outcome_unknown` (revision 3): an exact settlement is possible only if the provider's
usage data identifies the individual request (request id recorded before the call, if the
provider returns or accepts one; to verify per provider in IA-1). Otherwise the
**reservation stays** as the cost of that job (conservative) and only a manual correction
can change it (audit of WP2): on a **final** job only, the « AI Budget Manager » gives the
**target cost** of the job (non-negative, in the reservation's currency); the store cancels
every active cost line of the job and appends one positive `manual_correction` line at the
target's own rate, date and source (none if the target is zero), all in the reservation's
budget period. Corrections read only the tombstone and the ledger: they stay possible for
13 months, after the job's row has left `jobs.db` (an invoice may arrive late). The row carries an opaque author reference, a
reason code from a closed list (`provider_usage_report`, `provider_invoice`,
`provider_refund`, `duplicate_charge`) and the SHA-256 of the supporting document; the
document and the human explanation stay in Odoo. Never an edit of an existing row.

All values configurable on the AI server (`profiles.yaml`) and, for display thresholds, in
Odoo settings; no module update needed.

## 5. Measurement

Per job in Odoo (`lartdubati.ai.job`) and in the ledger: tokens, cost in billing currency,
rate, EUR. Odoo pivot « AI cost (excl. tax) » by month, function, profile, user and outcome
(accepted / corrected / refused), so the cost of refused proposals is visible. Monthly:
ledger vs provider invoice, difference > 5 % investigated. Provider invoices go through
the existing supplier bill circuit (software / SaaS, C25); the ledger is a control, not an
accounting record.

## 6. Infrastructure

The separate AI server (4 vCPU / 8 GB recommended, D1) is a fixed monthly cost to be quoted by the owner;
it does not count against the 50 € API cap. Ollama (IA-5) needs a larger, separate machine,
sized after measuring volumes.

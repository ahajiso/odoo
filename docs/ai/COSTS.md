# AI assistant – costs (IA-0, revision 2, 12/10/2026)

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
| Blocked by the pre-check, `missing_configuration` before extraction, out of scope | 0 or 1 | – |

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

Ledger rows (one transaction with the job, ARCHITECTURE.md §5.1):
`job_id`, `request_ref`, `user_ref`, function, profile, route, provider, model, kind
(`reservation` / `settlement` / `reconciliation`), **amount in the provider's billing
currency**, currency, **rate to EUR and its date and source**, EUR equivalent, tokens.
Caps are compared in EUR with the rate of the day from the configured source (to choose:
the ECB reference rate, or a fixed conservative rate set by the owner); the original
amount and rate are kept so a later reconciliation never rewrites history.

Reservation → settlement: the worst case is reserved at creation; the provider's reported
usage replaces it at the end; `outcome_unknown` keeps the reservation until the daily
reconciliation with the provider's usage report.

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

The separate AI server (2 vCPU / 4 GB) is a fixed monthly cost to be quoted by the owner;
it does not count against the 50 € API cap. Ollama (IA-5) needs a larger, separate machine,
sized after measuring volumes.

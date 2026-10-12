# AI assistant – security (IA-0, revision 2, 12/10/2026)

Threat model and controls for PLAN.md and ARCHITECTURE.md. Nothing implemented.
Revision 2: local pre-check, mTLS + HMAC, three isolated processes, egress proxy,
hardened extractor, data-policy rule for fallbacks, job atomicity.

## 1. Assets

Odoo database integrity; documents (personal data, prices, bank details, terms); provider
API keys; Odoo client certificate and HMAC key; budget; audit trail.

## 2. Trust boundaries

1. Browser ↔ Odoo (existing rights, rules, phase 4 route whitelist).
2. Odoo VPS ↔ AI server (Internet; mTLS + HMAC; firewall).
3. Gateway ↔ LiteLLM ↔ egress proxy ↔ providers (internal networks, then Internet).
4. Gateway ↔ extractor (internal network; extractor without egress).
5. **Inside / outside the company**: Odoo and the AI server are company-controlled hosts;
   providers are outside. Every confidentiality rule applies at boundary 3.
6. Document content and model output: untrusted data everywhere.

## 3. Secrets and process separation (D13)

| Secret | Only in | Never in |
|---|---|---|
| Provider API keys | `ai_litellm` (files `/run/secrets`, 0400) | gateway, extractor, Odoo, Git, DB, env vars, logs |
| LiteLLM client key | gateway and `ai_litellm` | Odoo, extractor |
| HMAC key (Odoo ↔ gateway), two active for rotation | gateway; `odoo_web` (current one) as a file (D16) | Odoo database (`ir.config_parameter` is copied in every dump and readable by admins), Git, env vars, logs |
| TLS: private CA, gateway server cert, Odoo client cert | gateway (server key), `odoo_web` (client key, D16) | elsewhere |

Today's `odoo_web` receives its database credentials as environment variables (visible
in `docker inspect`); the AI secrets must not follow that pattern.

Odoo ↔ gateway (D2): HTTPS with **mutual TLS** (private CA, Odoo client certificate,
gateway accepts only that CA), firewall of the AI server open only to the Odoo VPS
address, plus **HMAC** headers (`X-AI-Key-Id`, timestamp ±60 s, nonce cached 5 min,
signature over method, path, timestamp, nonce, body SHA-256); answers signed the same
way. WireGuard is the alternative if the owner prefers a tunnel (needs an interface on the
Odoo host, which D1 avoids).

Rotation (90 days and on any doubt): HMAC B added → Odoo switches → A removed; client
certificate renewed before expiry (1 year), CA kept offline; provider keys: new key in
LiteLLM, restart, old key revoked at the provider. Provider-side spend limits and
project-scoped keys as a second barrier.

## 4. Confidentiality pre-check (D12), before any external call

Deterministic, no AI, run **in Odoo before submission** and **again in the gateway** on
every input and on extracted text, before the job may reach LiteLLM.

### 4.1 Levels

| Level | Meaning | External profiles |
|---|---|---|
| `public` | no business secret | allowed (after D6) |
| `internal` | ordinary business data (supplier quotes, standard contracts) | allowed (after D6) |
| `confidential` | personal data beyond business contacts, HR, legal disputes | **refused**; `local` only (IA-5) |
| `restricted` | bank, identity documents | **refused** everywhere |

Rules:
- the detected level is a floor: the user may **raise** it, never lower it; Odoo and the
  gateway both refuse a declared level below the detected one;
- a request or document **not classifiable** locally (unreadable file, scanned pages whose
  OCR failed, unknown language) → `blocked_confidential` (until a `local` profile exists);
- before D6 is answered, external profiles accept only requests flagged `synthetic` by a
  test fixture; real data → refused with « legal decision pending ».

### 4.2 Detectors (each tested on synthetic data)

| Category | Detection | Level |
|---|---|---|
| Bank | IBAN (with mod-97 check), BIC in a bank context, card numbers (Luhn), « RIB » | restricted |
| Identity | French NIR with key, passport / ID-card patterns and keywords, date and place of birth together | restricted |
| HR | payslip, salary, sick leave, employment contract, disciplinary, medical terms (fr / en / fa keyword lists) | confidential |
| Personal | e-mail or phone not belonging to a known company partner domain / number, home address of a natural person | confidential |
| Legal | litigation, court, lawyer correspondence keywords | confidential |

Findings are stored as categories and counts, never the matched values. False positives
are accepted (the user can still work manually); false negatives are a residual risk
(§11).

### 4.3 Minimisation for allowed external calls

Odoo ids, logins and instance URLs never sent (opaque references). Business contact names
of natural persons pseudonymised (`PERSON_1`) with an in-memory mapping per job. Company
names, amounts, dates, policy numbers kept. Provider vision refused (D7): text only.

## 5. Prompt injection

The model has no tools, no URLs, no code execution, no write path: its only output is a
JSON document validated against a strict schema whose choices are Odoo's opaque references,
re-checked by Odoo and accepted by a human before any draft. Controls: fixed versioned
instructions; untrusted text in a delimited data block with a random boundary; provider
structured-output mode plus gateway validation; evidence excerpts must exist in the cited
chunk; instruction-like text flagged as a warning.

Two kinds of tests (T-S01a / T-S01b, §10): the fake provider proves that validation blocks
every forbidden effect; a **capped acceptance run on the real models with synthetic
adversarial documents** measures whether the model is influenced (extracted values,
warnings) — its result is reported, it is not assumed.

## 6. Data policy of a route and fallbacks (D10)

Each route declares: provider legal entity and DPA; processing region (`eu` ⊂ `global`,
`us` ⊂ `global`, `eu` and `us` not comparable); retention (`zdr` < N days < M days);
training (`none` required); sub-processor list reference. A fallback is allowed only if on
**every** attribute it is equal or stricter than the primary **and** the owner listed it.
Examples: Anthropic `global` → OpenAI `eu`: stricter region but another entity and DPA →
only if the owner approved both routes for that profile; OpenAI `eu` → Anthropic `global`:
refused (wider region). Fallback only on availability errors before any answer; never on a
schema failure, refusal or `outcome_unknown`. Checked at configuration load (service does
not start otherwise) and recorded per job.

## 7. Egress (D1, audit point 4)

A Docker network alone does not restrict destinations; name-based firewall rules break
when provider IPs change. Design:

- `ai_gateway`, `ai_litellm` and `ai_extractor` are only on `internal: true` networks:
  **no route to the Internet** at all.
- `ai_egress` is the only container on both an internal network (`net_egress`, shared with
  `ai_litellm` only) and an external one. It is a forward proxy (Squid or similar, pinned
  digest) allowing **only** `CONNECT` to the approved host names on port 443:
  `api.anthropic.com`, `api.openai.com` (or the EU host if D6 chooses it); IP literals,
  other ports, plain HTTP and every other host refused; names resolved by the proxy.
- No TLS interception: the tunnel is end-to-end; LiteLLM verifies the provider's
  certificate against the system CA store (verification never disabled; tested).
- The AI server's host firewall: inbound only the gateway's port from the Odoo VPS address
  and SSH from the owner; outbound from the host only what the proxy and updates need.
- Tests (§10, T-S20…T-S23): from each container, direct connection to an outside IP fails;
  from `ai_litellm` through the proxy, `example.com`, an IP literal, port 80 and an
  approved name on another port fail; an approved host works; the extractor reaches
  nothing; a certificate mismatch (test CA) is refused by LiteLLM.

## 8. Extractor hardening (D14)

ClamAV postponed only with all of the following, and synthetic data in IA-1:
- one **disposable child process per document**, started by the extractor service, killed
  at the end or on any limit; files on a per-job `tmpfs` wiped after the job; **no shared
  volume** with any container;
- limits per child: CPU time (e.g. 30 s text, 120 s OCR), address space (e.g. 512 MB),
  max output file size, no new processes beyond OCR helpers, open files;
- container: non-root, read-only root fs, `cap_drop: ALL`, `no-new-privileges`, Docker's
  seccomp profile tightened (no `ptrace`, no `mount`…), an AppArmor profile limiting file
  access to the job directory, `pids_limit`, memory and CPU limits, no egress;
- decompression-bomb and parser limits: file size before parsing, page count read before
  full parsing, max decompressed stream size, image pixel limit (e.g. Pillow's
  `MAX_IMAGE_PIXELS`), OCR resolution cap, overall wall-clock timeout;
- accepted types by magic bytes only (PDF, PNG, JPEG); encrypted PDFs, embedded files,
  JavaScript and forms ignored or refused.

## 9. Supply chain and runtime

Images by digest; own images built from pinned base digests; Python dependencies
`--require-hashes`; LiteLLM version at least two weeks old, signature / hash checked,
release notes and advisories read; no automatic update; `.pth` files of site-packages
listed at build and compared. All containers non-root, read-only, `cap_drop: ALL`,
`no-new-privileges`, limits, no Docker socket. LiteLLM: no UI, no admin routes reachable,
no database (H-AI-1 to verify on the pinned version).

## 10. Odoo-side controls

No new HTTP route; investors refused (default deny, tested); own-requests and company
rules; candidate searches as the requester; drafts only through existing business methods
as the user after `check_access('create')`; fingerprints frozen on the proposal and
re-checked at « Prepare draft ».

## 11. Logging and retention (D5)

Logged: job id, opaque user ref, function, profile, route, exact model as returned,
versions, timestamps, duration, tokens, cost (provider currency, rate, EUR), document
sha256, pre-check categories, validation result, error, fallback. Not logged: keys,
certificates, signatures, document text, prompts, raw model output, bank or personal
values. Log formatter by allow-list of fields. Retention: gateway logs 90 days; job
results until ack (≤ 7 days); ledger 13 months; Odoo records follow the company's
retention. Debug logging of prompts: synthetic data only, ≤ 24 h, refused in production.

## 12. Security tests (fake provider unless stated; none consumes a paid API except T-S01b, capped)

| # | Test | Expected |
|---|---|---|
| T-S01a | PDF with injected instructions (fake answers that obey them) | blocked by schema / enums / evidence check; nothing forbidden reaches Odoo |
| T-S01b | same synthetic adversarial PDFs, **real models**, capped acceptance run | report: values and warnings vs the clean version; any influence documented and fed back into prompts |
| T-S02 | invalid JSON, extra or missing field | `invalid_output`, not cached as success |
| T-S03 | model returns an account or a tax | no such field exists → `invalid_output` |
| T-S04 | category ref outside the list | refused by gateway; forged answer refused by Odoo |
| T-S05 | provider 5xx / 429 | allowed fallback (policy rule) or `provider_unavailable` |
| T-S06 | provider slower than the worker timeout | job `failed: timeout`; Odoo cron never blocked |
| T-S07 | refusal, truncated answer | `refused` / `invalid_output`, never repaired |
| T-S08 | two concurrent POSTs with the same key | one job, one reservation (transaction) |
| T-S09 | replay same key same body / other body | same job / 409 |
| T-S09b | worker killed after `attempt_started` | `outcome_unknown`, not retried, reservation kept |
| T-S10 | estimate above request cap; month cap reached | 402 before any job; override only by AI Budget Manager |
| T-S11 | user without the AI group; investor | access error, no menu |
| T-S12 | other company's records | not in candidates; forged reference refused |
| T-S13 | canary string from a test PDF and the test keys in all logs | absent |
| T-S14 | config with a wider-policy fallback, OpenRouter, `latest` | service refuses to start |
| T-S15 | gateway down / disabled / all providers down | existing circuits' test suites pass; request `failed` / `disabled` |
| T-S16 | config, schema version or candidates changed before « Prepare draft » | refused, « re-run the assistant » |
| T-S17 | bad HMAC, old timestamp, reused nonce; no or wrong client certificate | 401 / TLS handshake refused |
| T-S18 | wrong magic bytes, 11 MB, 200 pages, zip-bomb-like PDF, huge image | refused before or during parsing within limits |
| T-S19 | excerpt absent from the cited page | value `unsupported` |
| T-S20–23 | egress tests of §7 | only approved hosts reachable; TLS verified |
| T-S24 | IBAN, NIR, payslip text in the request or document | `blocked_confidential` before any LiteLLM call (fake LiteLLM records zero calls) |
| T-S25 | user lowers the level below the detected one | refused in Odoo and in the gateway |
| T-S26 | unclassifiable document (OCR failure) | blocked |
| T-S27 | real (non-synthetic) data before D6 | refused |
| T-S28 | user without create right on `product.creation.request` / `equipment.operation` | « Prepare draft » hidden; forced call refused by the ORM; proposal kept |
| T-S29 | intent with no allowed category | `missing_configuration`, no AI call beyond interpretation |

## 13. Residual risks

Pre-check false negatives (unusual personal data sent externally); provider retention per
their policy; a wrong but schema-valid extraction (mitigated by evidence, contradiction
checks, human acceptance); a compromised LiteLLM exposes provider keys (mitigated by
egress allow-list, spend caps, rotation).

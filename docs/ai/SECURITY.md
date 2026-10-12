# AI assistant – security (IA-0, revision 3, 12/10/2026)

Threat model and controls for PLAN.md and ARCHITECTURE.md. Nothing implemented.
Revision 2: local pre-check, mTLS + HMAC, three isolated processes, egress proxy,
hardened extractor, data-policy rule for fallbacks, job atomicity. Revision 3: egress
filtering designed for Docker's own chains (§7), retention split between `jobs.db` and
`ledger.db` (§11), encrypted disk, fixed secrets path on the Odoo side (§3).

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
| HMAC key (Odoo ↔ gateway), two active for rotation | gateway; `odoo_web` (current one) as a file under the fixed path `/run/secrets/lartdubati_ai/` (D16) | Odoo database (`ir.config_parameter` is copied in every dump and readable by admins), Git, env vars, logs |
| TLS: private CA, gateway server cert, Odoo client cert | gateway (server key), `odoo_web` (client key and CA cert under `/run/secrets/lartdubati_ai/`, D16) | elsewhere; `odoo.conf` holds no secret (option b: fixed path, no entry; option a: a path only) |

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

## 7. Egress (D1; audit points 4 of ebe35ac and 3 of c9e5427)

A Docker network alone does not restrict destinations, name-based firewall rules break when
provider IPs change, and a container with a published port normally has an outbound route
(Docker NATs its traffic and its forwarding rules are evaluated before ordinary host
rules). Design, in layers:

**Layer 1 – Docker networks.** `ai_gateway`, `ai_litellm` and `ai_extractor` are on
`internal: true` networks, except the gateway's `net_front` that exists only to publish
its port. `ai_egress` is the only container on the external network `net_out`. Every
network has a fixed subnet (IPAM in the compose file) and `ai_egress` a fixed address, so
firewall rules can name them. IPv6 disabled on these networks (or the same rules in
`ip6tables` / the `ip6` family).

**Layer 2 – host firewall in the `DOCKER-USER` chain** (or its nftables equivalent, the
chain Docker evaluates before its own forwarding rules and never overwrites):

```
# illustrative, iptables syntax; subnets fixed in the compose file
-A DOCKER-USER -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
# inbound to the published gateway port: only the Odoo VPS
-A DOCKER-USER -i <ext_if> -p tcp -d <gateway_ip> --dport 8443 -s <odoo_vps_ip> -j RETURN
-A DOCKER-USER -i <ext_if> -d <ai_subnets> -j DROP
# outbound: only the proxy, only HTTPS and DNS to the configured resolvers
-A DOCKER-USER -s <ai_egress_ip> -o <ext_if> -p tcp --dport 443 -j RETURN
-A DOCKER-USER -s <ai_egress_ip> -o <ext_if> -p udp -d <resolvers> --dport 53 -j RETURN
-A DOCKER-USER -s <ai_egress_ip> -o <ext_if> -p tcp -d <resolvers> --dport 53 -j RETURN
-A DOCKER-USER -s <ai_subnets> -j DROP          # default deny for every AI container
```

The rules are installed by a systemd unit ordered after Docker, re-applied after every
Docker restart and checked by a daily script that compares them with the expected list
(alert on difference). The Docker daemon keeps `iptables: true` (its own NAT is needed for
the proxy) and `userland-proxy: false` so published ports go through the kernel rules
above. The host's own outbound (OS updates) is filtered in the host's `OUTPUT` chain,
separately.

**Layer 3 – the egress proxy** (Squid or equivalent, pinned digest):
- accepts clients only from `ai_litellm`'s fixed address (source ACL); the gateway and the
  extractor are not on `net_egress` at all;
- only `CONNECT` to the approved names on port 443 (`api.anthropic.com`, `api.openai.com`
  or the EU host decided by D6); plain HTTP, other ports, IP literals refused;
- DNS resolution done by the proxy only (its configured resolvers); after resolution,
  destinations in private, loopback, link-local and special ranges refused:
  `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `169.254.0.0/16`
  (cloud metadata `169.254.169.254` included), `100.64.0.0/10`, `0.0.0.0/8`, `::1`,
  `fc00::/7`, `fe80::/10`;
- no TLS interception: end-to-end tunnel, LiteLLM verifies the provider's certificate
  against the system CA store (never disabled);
- LiteLLM uses it through `HTTPS_PROXY=http://ai_egress:3128`, `NO_PROXY` limited to the
  internal names.

**DNS inside the AI containers.** They must not resolve Internet names (a DNS query is an
exfiltration channel). Docker's embedded resolver answers internal container names; whether
it forwards external queries for containers on internal networks depends on the Docker
version: to verify on the pinned version (H-AI-6). If it does, the containers get a `dns:`
setting pointing to a non-forwarding address and the `DOCKER-USER` rules drop their port-53
traffic (already covered by the default deny). Tested either way.

**Tests** (run on the AI server, recorded in IA-1):

| # | From | Attempt | Expected |
|---|---|---|---|
| T-S20 | gateway, LiteLLM, extractor | TCP 443 / 80 to a public IP; UDP 53 to 1.1.1.1; ICMP | fail (dropped) |
| T-S21 | gateway, LiteLLM, extractor | resolve `example.com` | fails (no external resolution) |
| T-S22 | LiteLLM through the proxy | `example.com:443`, an IP literal, `api.anthropic.com:80`, a name resolving to `169.254.169.254` or `127.0.0.1` (test DNS record) | refused by the proxy |
| T-S23 | LiteLLM through the proxy | approved host with the right CA / with a test CA presenting a wrong certificate | works / refused by LiteLLM |
| T-S23b | gateway, extractor | reach the proxy (`CONNECT` to an approved host) | impossible: not on `net_egress`; and the proxy's source ACL refuses any address but `ai_litellm`'s (tested from a test container on `net_egress`) |
| T-S23c | outside | connect to the gateway port from an address other than the Odoo VPS | dropped |
| T-S23d | host | restart Docker | rules present again; daily check passes |

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
values. Log formatter by allow-list of fields.

Retention (revision 3): gateway logs 90 days (metadata only); `jobs.db` inputs deleted at
the end of the job and results at `ack` or after 7 days, **never backed up**;
`ledger.db` (financial metadata and idempotency tombstones, no business content) 13 months,
backed up encrypted; Odoo records follow the company's retention. The AI server's data
disk and its backup target are encrypted (LUKS or the provider's encrypted volumes with a
key not held by the hosting provider, to decide with D1); swap disabled or encrypted, so
job contents never reach an unencrypted swap. Docker logs of the gateway hold no content
(allow-list formatter), so they need no special treatment beyond rotation. Debug logging of prompts: synthetic data only, ≤ 24 h, refused in production.

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
| T-S20–23d | egress tests of §7 | as listed in §7 |
| T-S24 | IBAN, NIR, payslip text in the request or document | `blocked_confidential` before any LiteLLM call (fake LiteLLM records zero calls) |
| T-S25 | user lowers the level below the detected one | refused in Odoo and in the gateway |
| T-S26 | unclassifiable document (OCR failure) | blocked |
| T-S27 | real (non-synthetic) data before D6 | refused |
| T-S28 | user without create right on `product.creation.request` / `equipment.operation` | « Prepare draft » hidden; forced call refused by the ORM; proposal kept |
| T-S29 | intent with no allowed category | `missing_configuration`; no draft; extraction still runs if a document was given (proposal for an authorised person) |
| T-S30 | after `ack` and after 7 days | result absent from `jobs.db` (including free pages after `VACUUM`); same key → `410 result_purged`, no new call |
| T-S31 | scan of `ledger.db` and its backup for the canary string and extracted values of the test documents | absent |
| T-S32 | kill the gateway during the commit of a job creation | both files consistent: job + reservation + tombstone, or none |
| T-S33 | Odoo crashes after `GET` before its commit; then after its commit before `ack` | first case: result fetched again; second: `ack` sent by the next run; `ack` twice → 204 |
| T-S34 | 10 jobs submitted at once | at most the configured number running, extractions and OCR within their semaphores |

## 13. Residual risks

Pre-check false negatives (unusual personal data sent externally); provider retention per
their policy; a wrong but schema-valid extraction (mitigated by evidence, contradiction
checks, human acceptance); a compromised LiteLLM exposes provider keys (mitigated by
egress allow-list, spend caps, rotation).

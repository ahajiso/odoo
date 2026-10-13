# IA-1 – development plan of the isolated AI server (revision 4, 13/10/2026, no code)

Green light of the audit of `400a3c0..95fdf3c`: **writing this plan only**. Not yet a
green light to code, install a server or call a real API. This plan is audited before any
implementation.

Revision 2 answers the audit of `2fab28d` (§11): an exhaustive matrix of the security
tests by phase, with an exit criterion limited to what IA-1 can really run (§8); the
topology, DNS and TLS of the fake providers, with an exception that exists only in the
IA-1 profile and a test that the production profile refuses the same destinations (§5);
container environments built from an allow-list (§6); an atomicity test combining
captures, rule snapshots and counters (§3, P1); synthetic personal data generated from
fictitious identities only (§7).

Revision 3 answers the audit of `d8ae4cf` (§13): a dedicated firewall chain
`LARTDUBATI-AI` reached by one idempotent jump, `DOCKER-USER` never flushed, only the
dedicated chain replaced atomically, and an atomicity test with per-generation counters
(§3, P1); a closed production profile with an empty provider list in IA-1 (§5); a test VM
of exactly 4 vCPU / 8 GB (§1, §12). Revision 4 answers the audit of `b6dac22` (§14): the
replacement of the chain's content uses an explicit `-F LARTDUBATI-AI` inside the
transaction, after a dry run with `--test`; T-S37 checks the rule count after each reload.

Basis: PLAN.md revision 4 and its companions. Test numbers refer to SECURITY.md §12.

## 0. Scope

**In IA-1**
- the gateway (FastAPI API + worker, `jobs.db` / `ledger.db`), the three functions with
  their schemas, the confidentiality pre-check, minimisation, validation, budget ledger,
  idempotency, `ack`, mTLS + HMAC;
- **fake providers** (two services imitating the Anthropic and OpenAI APIs, §5) and a
  **fake LiteLLM** for unit tests;
- the real LiteLLM proxy image (pinned), configured **only** with the fake providers'
  addresses, to observe what it sends (H-AI-1) without any real call;
- the extractor, the egress proxy, the firewall rules, the systemd units, the capture unit
  for the tests;
- the synthetic data set, the test suites, the load and isolation tests, the IA-1 report.

A small **test client** stands in for Odoo (it signs requests with HMAC and presents a test
client certificate); it is not Odoo and proves nothing about the Odoo module.

**Not in IA-1**: any real provider key or call (IA-1b, after D3, D4, D6 and the official
verification of providers); any Odoo module or change on `artdubati_test`; any change on
the Odoo VPS; any real document or real user text.

## 1. Decisions (confirmed by the owner after the audit of `bdb2548`)

| # | Decision | Proposal |
|---|---|---|
| IA1-D1 | Where the gateway code lives | **separate private repository `lartdubati-ai-gateway`**: this repository is the Odoo addons folder cloned at `/opt/odoo/addons/custom`, so the AI server's code must never live here. The owner creates it and gives this session access; `docs/ai/` stays here as the design record |
| IA1-D2 | Where container and isolation tests run | **dedicated disposable VM of exactly 4 vCPU and 8 GB RAM** (the target capacity, so that the load test can validate H-AI-3), Ubuntu 24.04, root access, reinstalled at the end of IA-1; the stand-in « Odoo » client of T-S23c can be a much smaller machine or a second address. This development session has the Docker client but no Docker daemon: it runs unit tests only |
| IA1-D3 | OS of the VM and of the future AI server | **Ubuntu 24.04 LTS** (audit of `2fab28d`: more proven than 26.04 for this security work); same on the VM and the server |
| IA1-D4 | Firewall backend | **`iptables-nft` first, with the dedicated chain `LARTDUBATI-AI` reached from `DOCKER-USER`** (never flushed); switch to a dedicated nftables table only if the atomicity test (P1) fails |

## 2. Repository layout (in `lartdubati-ai-gateway`)

```
gateway/            FastAPI app, worker, storage (ledger.db + jobs.db), budget, auth,
                    pre-check, minimisation, prompts, validation, routing
schemas/            JSON Schema files (contract 2.0) with their SHA-256 list
extractor/          service + sandboxed child, limits, chunking, OCR
fakes/              fake_litellm (unit tests); fake_provider (one program, two
                    personalities: anthropic, openai) for the stack tests (§5)
testclient/         the Odoo stand-in (HMAC, client certificate)
deploy/
  compose.yaml              production profile: no fake, no test CA, no exception
  compose.ia1.yaml          IA-1 overlay: net_fake, fakes, test CA, proxy exception (§5)
  proxy/                    proxy.base.conf + generator: production / ia1 outputs
  firewall/                 expected.rules (production), expected.ia1.rules, apply,
                            verify, change
  systemd/                  ai-firewall, ai-stack, check timer, ai-capture (tests only)
  env/                      allow-lists of environment variable names per container (§6)
  Dockerfiles, lock files with hashes
fixtures/           generator of the synthetic data set (§7) and its outputs' hash list
tests/unit/         anywhere (this session, CI): no Docker, no network
tests/stack/        on the VM: compose stack with fakes
tests/isolation/    on the VM as root: firewall, start order, crashes, captures
docs/               IA-1 report, measurements, pinned versions record
```

CI (if the owner enables it on that repository): unit tests only, no secret, no outbound
call except package download from the hash-locked lock file.

## 3. Precisions required by the audit of `400a3c0..95fdf3c`

**P1 – Atomic firewall reload, or the stack stopped first** (revision 3, audit of
`d8ae4cf`).
- `DOCKER-USER` is shared and is **never flushed or rewritten**. The project owns a
  dedicated chain `LARTDUBATI-AI` in the `filter` table (SECURITY.md §7, layer 2).
- **The chain.** `firewall-apply` first creates `LARTDUBATI-AI` on its own if
  `iptables -n -L LARTDUBATI-AI` does not find it (`iptables -N LARTDUBATI-AI`), so the
  chain exists before any jump or content.
- **The jump.** `firewall-apply` then installs
  `-I DOCKER-USER 1 -j LARTDUBATI-AI` only if `iptables -C DOCKER-USER -j LARTDUBATI-AI`
  does not find it. `firewall-verify` checks that the jump exists **exactly once** and in
  first position, and that the rest of `DOCKER-USER` is not this project's business (no
  rule mentioning the AI subnets outside our chain). The jump is never removed by a reload.
- **The content** (revision 4, audit of `b6dac22`). The plan does not rely on what a chain
  declaration line does under `--noflush` (its effect on an existing chain is not something
  to depend on), so the input declares nothing and flushes explicitly, only our chain:
  ```
  *filter
  -F LARTDUBATI-AI
  -A LARTDUBATI-AI -m comment --comment "lartdubati-ai generation <id>"
  -A LARTDUBATI-AI ...
  -A LARTDUBATI-AI -s <ai_subnets> -j DROP
  COMMIT
  ```
  1. dry run: `iptables-restore --test --noflush < generation.rules` (syntax and
     references checked, nothing applied); failure → nothing applied, unit fails;
  2. apply: `iptables-restore --noflush < generation.rules`: the flush of our chain and
     all its new rules are **one** transaction with `iptables-nft` (to be proven by T-S37);
     `DOCKER-USER` and every other chain stay untouched;
  3. `firewall-verify`: content equal to the generation's expected rules (same count, same
     order), jump exactly once in first position.
  The first rule counts packets with no target and carries the **generation id**, so each
  generation has its own counters.
- Any **change** of the rules goes through `firewall-change`: `systemctl stop ai-stack` →
  apply → verify → `systemctl start ai-stack`. Only the boot path (no container yet) and
  the 5-minute check (verify only) skip the stop.
- **Atomicity test T-S37.** A foreign test rule is first added to `DOCKER-USER` (outside
  our chain) and the checksum of `DOCKER-USER` without our jump's counters is recorded.
  Then 1 000 reloads alternate two generations A and B of `LARTDUBATI-AI` that differ only
  in their generation id and a harmless extra drop rule, while:
  1. a traffic generator in a test container on an AI subnet sends SYNs at a high rate to a
     non-allowed external address, and requests through the proxy to an allowed fake;
  2. captures run on `any` and on the external interface: **no** SYN to the non-allowed
     address may appear on the external interface;
  3. `nft monitor ruleset` records the changes: each reload must appear as **one**
     transaction touching only `LARTDUBATI-AI`;
  4. a reader takes snapshots of the chain (`nft -j list chain ip filter LARTDUBATI-AI`) in
     a tight loop: every snapshot equals A or B exactly (rules, order, generation id),
     never a partial or empty chain; and after **each** reload the number of rules in
     `LARTDUBATI-AI` is exactly that of A or of B (no accumulation across reloads);
  5. **counters per generation**, without assuming continuity across reloads (a replaced
     chain starts its counters at zero): within each generation, its counting rule and its
     final drop rule both count packets of the generator's forbidden traffic before the
     next reload (the generation was really traversed and really dropped), and no packet is
     counted on a rule that exists neither in A nor in B. The jump in `DOCKER-USER`, never
     replaced, keeps its own counter, which only increases (a cross-check, not a
     requirement on our chain);
  6. at the end, `DOCKER-USER` still contains the foreign test rule, its checksum is
     unchanged, and the jump exists exactly once.
  Pass: all six hold. If not: IA1-D4 switch to the dedicated nftables table
  (`inet lartdubati_ai`, base chain on `forward` before Docker's filter, `flush chain` and
  rules in one `nft -f` file), then the same test again, with snapshots of that chain.

**P2 – T-S23e capture before Docker.** `ai-capture.service` (VM only):
`Before=docker.service`, runs `tcpdump -i any -n -U -w …` (the `any` pseudo-interface sees
bridges and veths created later) and a second capture on the external interface; the
analysis combines both with `journalctl -u ai-firewall -u ai-stack -u docker`,
`docker events` (from dockerd's start) and each container's `State.StartedAt`. Pass: no AI
container started before `ai-firewall` succeeded, no packet from an AI subnet to a
non-allowed destination, on 10 reboots and 10 Docker restarts.

**P3 – Health probes of LiteLLM and of the proxy.** Docker `HEALTHCHECK` = internal check
without network (process alive, listening socket present in `/proc/net/tcp*`; the proxy's
own check command). LiteLLM's unauthenticated health routes, if they cannot be disabled or
authenticated in the pinned version, are reachable only from `net_llm` (gateway only).
**T-S35**: from the extractor, the proxy and throw-away containers on each other network,
LiteLLM's port and health routes are unreachable; from the gateway they answer liveness at
most (no configuration, key or model list).

**P4 – Brutal crash of `dockerd`.** **T-S36**: `kill -9` of `dockerd` (and separately of
`containerd`) while jobs run, capture active; observe containers during the outage and
after Docker's automatic restart, and the states of `ai-firewall` / `ai-stack`. Expected
design: `BindsTo=docker.service` (with `PartOf=`) on both units; after the automatic
restart the stack **stays stopped** until a controlled `systemctl start ai-stack`, with an
alert; interrupted jobs become `outcome_unknown`. Result and final settings in the report.

## 4. Work packages

| WP | Content | Where |
|---|---|---|
| WP1 | Contract: JSON Schemas, SHA-256 list, validators; fake LiteLLM with failure modes | unit |
| WP2 | Storage: `ledger.db` main + `jobs.db` attached, pragmas, same-filesystem check, single writer, states, leases, tombstones, purge, maintenance `VACUUM` | unit + VM |
| WP3 | API: jobs, `ack`, `/v1/health`, mTLS (test CA per run), HMAC, kill switch, `REAL_DATA_ALLOWED=false`, maintenance mode; test client | unit |
| WP5 | Pre-check and minimisation (gateway side): detectors fr / en / fa, levels, floor rule, unclassifiable → blocked, pseudonymisation | unit |
| WP6 | Extractor: magic bytes, limits before parsing, sandboxed child, tmpfs per job, OCR, chunking, evidence check, instruction-like flag, semaphore | unit + stack |
| WP4 | Worker: semaphores, pipeline, routes and data-policy check at load, fallbacks, budget reservation / settlement / manual correction, ledger currency and rate; LiteLLM client | unit + stack |
| WP8 | Synthetic data set (§7); canaries; scenario fixtures as recorded fake answers | unit + stack |
| WP7 | Infrastructure: compose (production + IA-1 overlay), fake providers (§5), proxy profiles, firewall apply / verify / change (P1), units with `BindsTo=` (P4), daemon settings, internal health checks (P3), environment allow-lists (§6) | VM |
| WP9 | Load and memory test at the configured concurrency; IA-1 report | VM |

Order: WP1 → WP2 → WP3 → WP5 → WP6 → WP4 → WP8 → WP7 → WP9. Small commits, unit tests
first.

## 5. Fake providers: topology, DNS, TLS and the IA-1-only exception (audit point 2)

**Topology (IA-1 overlay only).**
- Network `net_fake`: `internal: true`, fixed subnet `172.31.250.0/29`; members:
  `ai_egress` (`172.31.250.2`), `fake_anthropic` (`172.31.250.3`), `fake_openai`
  (`172.31.250.4`). No other container is on it.
- `fake_anthropic` and `fake_openai`: the same small program (`fakes/fake_provider`) in
  two personalities; it answers the provider-style API paths with recorded fixtures and
  failure modes, and records each request body for the H-AI-1 analysis.
- Names: `anthropic.fake.ia1.test` and `openai.fake.ia1.test` (the reserved `.test`
  top-level domain: they can never exist on the Internet). LiteLLM's IA-1 configuration
  points each fake route to these names with an explicit `api_base`; the real provider
  host names appear nowhere in the IA-1 configuration.

**DNS.** Only the proxy resolves them, through an IA-1-only hosts file mounted in the proxy
(`hosts_file` directive) mapping the two names to the two fixed addresses. The gateway,
LiteLLM and the extractor still have no external resolution (T-S21); LiteLLM sends
`CONNECT anthropic.fake.ia1.test:443` to the proxy, as it would for a real host.

**TLS.** A test CA generated per IA-1 environment issues the fakes' certificates for those
names. Only the IA-1 overlay adds this CA to LiteLLM's trust bundle; the production image
and profile trust the system CA store only.

**The exception, strictly IA-1.** The proxy configuration is generated from one base file
by a generator with two profiles:
- `production` (revision 3, audit of `d8ae4cf`): **closed** while D3 and D6 are not
  decided: an **empty** allow-list, **no** real API name and no placeholder name;
  `deny to_special` for every private, loopback, link-local, CGNAT and metadata range; no
  hosts file. The production `profiles.yaml` and LiteLLM configuration have **no external
  route**: `allowed_providers` is empty, and the gateway and LiteLLM refuse to start if a
  route names a provider while that list is empty (the list is filled only by IA-1b's plan,
  after D3 and D6);
- `ia1`: the same file, **plus** exactly one rule placed before the `to_special` denial:
  `http_access allow CONNECT ssl_port litellm fake_names fake_dst`, where `fake_names` =
  the two `.ia1.test` names and `fake_dst` = `172.31.250.3/32 172.31.250.4/32`; its
  allow-list holds nothing else; the hosts file is added.
  Both name **and** address must match; nothing else private is allowed.

**Proofs.**
- T-S38: the two generated profiles are compared:
  - IA-1 profile: exactly the two fake providers, nothing else;
  - production profile in IA-1: **no provider at all** (empty allow-list, no route in
    `profiles.yaml` nor in LiteLLM's configuration), and the gateway with a route added by
    hand refuses to start;
  - production artefacts (images, configuration files, compose file): no `.ia1.test` name,
    no `172.31.250.` address, no hosts file, no test CA, no exception rule;
  and the production-profile proxy, started on the VM attached to `net_fake`, refuses
  `CONNECT` to both fake names and to both addresses (`to_special`), while the `ia1`
  profile accepts them only with name and address together (a fake name resolved to another
  private address, and another name resolved to a fake address, are both refused).
- T-S39: the fakes cannot relay or reach anything: they are only on `net_fake` (internal),
  the `LARTDUBATI-AI` default deny covers `172.31.250.0/29` except the proxy's own address,
  their environment has no proxy variable (§6), the program has no outbound HTTP client
  dependency; tests: from inside each fake, connections to a public IP, to the proxy's
  port and to the other networks fail; requests to the fake in absolute-URI form or with
  `CONNECT` get a 4xx and produce no outbound packet (capture).
- At the end of IA-1, the compose overlay, the hosts file, the test CA and the fakes are
  removed with the VM; the AI server for IA-1b is installed from the production profile
  only (DEPLOYMENT.md §8 checklist line added in IA-1b's plan).

## 6. Environment allow-lists instead of scanning for secrets (complement)

- No scan or log of the VM's environment. Each container's environment is built
  explicitly in compose from `deploy/env/<container>.allow` (names only, with fixed
  values or secret-file paths); no `env_file` pass-through, no `${VAR}` substitution from
  the host shell except the documented profile selector.
- `deploy/check_env.py` reads the rendered configuration (`docker compose config`) and
  fails if a container has a variable not in its allow-list, or a variable whose **name**
  matches known provider-secret names (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
  `AZURE_*_KEY`, `*_API_KEY` except the allow-listed LiteLLM client key file path…). It
  prints names only, never values.
- At start, the gateway and LiteLLM compare their own environment **names** with the
  allow-list and refuse to start on a difference (names logged, values never).
- T-S40: a container started with an extra variable, or with `ANTHROPIC_API_KEY` set to a
  dummy value, is refused by the check and by the service itself; the dummy value appears
  in no output (canary).

## 7. Synthetic data set (complement on personal data)

- Generated by a deterministic script (fixed seed) from templates; no real document,
  and **no identifier copied from any real or published example** (including the sample
  IBANs or NIRs found in documentation).
- **Fictitious identities first**: a fixed list of invented persons and companies (names
  built from invented syllables, fictitious streets in fictitious towns, a postal code
  range marked fictitious in the fixtures); every personal identifier is then **derived
  from these identities** by the generator:
  - IBAN: country code + bank and branch codes from a fixture list of invented codes +
    account number derived from the identity's id; check digits computed (mod 97);
  - NIR: sex digit, year, month from the fictitious birth date, a department code, an
    invented commune code and order number, key computed (97 − n mod 97);
  - card numbers: prefix from the payment networks' documented test ranges, remaining
    digits derived from the identity's id, Luhn digit computed;
  - phone numbers and e-mail addresses: ranges and domains reserved for fiction or tests
    (e.g. `example.com`, `.test`).
- A test checks that every identifier in the fixtures is produced by the generator from a
  listed identity (re-generation gives the same file hashes) and that none appears in a
  denylist of published sample values.
- Documents: policies, subscriptions, quotes, bills, contracts, consignment,
  contradictory and incomplete variants, in fr / en / fa; scans rendered with noise;
  adversarial variants (injected instructions in text, white text, metadata, form fields,
  footnotes; bomb-like PDFs; huge images; wrong magic bytes). Each fixture carries a unique
  canary string and every job built from fixtures carries `synthetic: true`.

## 8. Test matrix (audit point 1) and exit criterion

The matrix lists **47 distinct test identifiers** (T-S01a … T-S40, with the lettered
variants T-S09b and T-S23b … T-S23f).

Legend: **IA-1** = fully run in IA-1; **IA-1 (gateway part)** = the gateway / server side
is run in IA-1, the Odoo side is carried to IA-2; **IA-2** = needs the Odoo module, carried
to IA-2's plan; **IA-1b** = needs real providers.

| Test | Subject | Phase | Part run in IA-1 |
|---|---|---|---|
| T-S01a | injected instructions, fake answers obeying them | IA-1 (gateway part) | gateway validation blocks every forbidden effect; Odoo's re-validation → IA-2 |
| T-S01b | adversarial documents on real models | IA-1b | – |
| T-S02 | invalid JSON, extra / missing field | IA-1 | all |
| T-S03 | account or tax in the answer | IA-1 | all |
| T-S04 | category ref outside the list | IA-1 (gateway part) | gateway refusal; forged answer refused by Odoo → IA-2 |
| T-S05 | provider 5xx / 429, fallback rules | IA-1 | all (fake routes with declared policies) |
| T-S06 | provider slower than the worker timeout | IA-1 (gateway part) | job `failed: timeout`; « Odoo cron never blocked » → IA-2 |
| T-S07 | refusal, truncation | IA-1 | all |
| T-S08 | concurrent POSTs, same key | IA-1 | all |
| T-S09 | replay same / other body | IA-1 | all |
| T-S09b | worker killed after `attempt_started` | IA-1 | all |
| T-S10 | request cap, month cap, override | IA-1 (gateway part) | 402s and the signed override field; « only an AI Budget Manager » (Odoo group) → IA-2 |
| T-S11 | user without AI group; investor | IA-2 | – |
| T-S12 | other company's records | IA-2 | – |
| T-S13 | canaries and keys absent from logs | IA-1 (gateway part) | gateway, LiteLLM, extractor, proxy and fake logs; Odoo logs → IA-2 |
| T-S14 | wider-policy fallback, OpenRouter, `latest` refused at load | IA-1 | all |
| T-S15 | gateway down / disabled, providers down: existing Odoo circuits | IA-2 | gateway's `disabled` / `provider_unavailable` answers are covered by T-S05 and WP3 tests |
| T-S16 | config / schema / candidates changed before « Prepare draft » | IA-2 | the gateway returns `config_version` and schema versions in `meta` (WP3 test) |
| T-S17 | HMAC and client certificate | IA-1 | all, with the test client |
| T-S18 | file limits and bombs | IA-1 | all |
| T-S19 | excerpt absent from the cited page | IA-1 (gateway part) | gateway evidence check; Odoo's re-check → IA-2 |
| T-S20 | direct outbound from AI containers | IA-1 | all (VM) |
| T-S21 | external DNS from AI containers | IA-1 | all (VM) |
| T-S22 | proxy refusals (other host, IP literal, port, private / metadata resolution) | IA-1 | all (VM), production and IA-1 profiles |
| T-S23 | approved host, right / wrong certificate | IA-1 (fakes) + IA-1b | with the fakes and the test CA in IA-1; the real hosts' certificates in IA-1b |
| T-S23b | gateway / extractor cannot use the proxy | IA-1 | all (VM) |
| T-S23c | gateway port from a non-allowed address | IA-1 | with a stand-in address for « Odoo VPS » (the test client's); repeated with the real Odoo VPS address at IA-2's deployment |
| T-S23d | Docker restart, reboot | IA-1 | all (VM) |
| T-S23e | capture before Docker (P2) | IA-1 | all (VM) |
| T-S23f | rule removed, corrupted expected file | IA-1 | all (VM) |
| T-S24 | bank / identity / payslip data blocked | IA-1 (gateway part) | gateway pre-check on inputs and extracted text, fake LiteLLM records zero calls; Odoo's pre-check before submission → IA-2 |
| T-S25 | declared level below detected | IA-1 (gateway part) | gateway refusal; Odoo refusal → IA-2 |
| T-S26 | unclassifiable document | IA-1 | all (gateway and extractor) |
| T-S27 | real data before D6 | IA-1 (gateway part) | `REAL_DATA_ALLOWED=false`, non-synthetic jobs refused; Odoo's marking → IA-2 |
| T-S28 | no create right on the target circuit | IA-2 | – |
| T-S29 | no allowed category (`missing_configuration`) | IA-2 | – |
| T-S30 | purge after `ack` / 7 days, `410` | IA-1 | all |
| T-S31 | canaries absent from `ledger.db` and its backup | IA-1 | all |
| T-S32 | exception, `SIGKILL`, hard reset during commits | IA-1 | all (hard reset on the VM) |
| T-S33 | crash order around `ack` | IA-1 (gateway part) | result available until `ack`, `ack` idempotent (204 twice), `410` after purge; Odoo's commit-then-ack and crash cases → IA-2 |
| T-S34 | concurrency semaphores | IA-1 | all |
| T-S35 | health probes not reachable (P3) | IA-1 | all (VM) |
| T-S36 | `dockerd` / `containerd` crash (P4) | IA-1 | all (VM) |
| T-S37 | atomic firewall reload (P1) | IA-1 | all (VM) |
| T-S38 | IA-1 exception absent from the production profile | IA-1 | all (VM) |
| T-S39 | fakes without egress, unable to relay | IA-1 | all (VM) |
| T-S40 | environment allow-lists | IA-1 | all |

**Exit criterion of IA-1**: every test marked **IA-1** passes, and the « part run in IA-1 »
of every test marked **IA-1 (gateway part)** passes, with logs kept; the load test passes
at the configured concurrency; H-AI-1, H-AI-6, H-IA1-1, H-IA1-2 and H-IA1-3 (§10) are
answered with evidence. The Odoo parts and the **IA-2** tests are copied, as open items,
into IA-2's plan; T-S01b and the real-host part of T-S23 into IA-1b's plan. The IA-1 report
lists the verified, the not verified, the open hypotheses, the pinned versions and digests,
and the final unit and firewall settings; it is audited.

## 9. Guards against real calls and real data

- No real key exists in IA-1; environment allow-lists and the name check (§6) refuse
  provider-secret names.
- The proxy's IA-1 profile allows **only** the two fake names at their two addresses; the
  real API names are absent from it, so even a misconfigured LiteLLM cannot reach them.
- `REAL_DATA_ALLOWED=false`; jobs without `synthetic: true` are refused (T-S27).

## 10. Open hypotheses settled by IA-1

| # | Hypothesis | Settled by |
|---|---|---|
| H-AI-1 | LiteLLM's requests to each provider format (structured outputs, region parameters) | WP4, request bodies recorded by the fakes |
| H-AI-3 | 4 vCPU / 8 GB at the configured concurrency | WP9 |
| H-AI-6 | no Internet DNS from internal networks | T-S21 |
| H-IA1-1 | `iptables-restore --noflush` with one `COMMIT` is atomic on Ubuntu 24.04 | T-S37 |
| H-IA1-2 | `BindsTo=` keeps the stack stopped after a `dockerd` crash until a controlled resume | T-S36 |
| H-IA1-3 | LiteLLM's unauthenticated health routes can be disabled or are reachable only from the gateway | T-S35 |

Not settled by IA-1: H-AI-2 (Odoo reachability), H-AI-4 (provider settings), H-AI-5 (real
token counts), H-AI-7 (provider request ids in usage data).

## 11. Answers to the audit of `2fab28d`

| # | Point | Answer | Where |
|---|---|---|---|
| 1 | « All of SECURITY §12 except T-S01b » impossible without the Odoo module | **Fixed**: exhaustive matrix (IA-1 / IA-1 gateway part / IA-2 / IA-1b); exit criterion limited to what IA-1 runs; the rest copied into IA-2's and IA-1b's plans | §8 |
| 2 | Fake providers' private addresses vs `to_special` | **Fixed**: `net_fake` with two fixed addresses, `.ia1.test` names resolved by the proxy's IA-1 hosts file, test CA only in the IA-1 overlay, one exception requiring name and address, generated only in the `ia1` profile; production profile proven to refuse the same destinations (T-S38); fakes without egress nor relay (T-S39) | §5 |
| c1 | Environment scan | **Fixed**: allow-lists per container, name checks only, values never printed (T-S40) | §6 |
| c2 | Atomicity proof | **Fixed**: captures + `nft monitor` + chain snapshots + rule counters (T-S37) | §3 P1 |
| c3 | Synthetic personal data | **Fixed**: fictitious identities first, identifiers derived and checksummed by the generator, nothing copied from real or published samples, regeneration and denylist tests | §7 |
| D | IA1-D1 to D4 | **Adopted as recommended**: separate private repository, dedicated disposable VM, Ubuntu 24.04 LTS, `iptables-nft` first | §1 |

## 12. What the owner provides or does

- confirmation of IA1-D1 to IA1-D4;
- the private repository and this session's access to it;
- the disposable Ubuntu 24.04 VM with **exactly 4 vCPU and 8 GB RAM** and root access,
  and a second, much smaller machine or address for the stand-in « Odoo » client of
  T-S23c; the owner runs the VM scripts prepared by the
  session, as for the Odoo server;
- nothing on the Odoo VPS, `artdubati_test` or the provider accounts in IA-1.

## 13. Answers to the audit of `d8ae4cf`

| # | Point | Answer | Where |
|---|---|---|---|
| 1 | `-F DOCKER-USER` would remove foreign rules; a monotone counter is impossible on a recreated chain | **Fixed**: dedicated chain `LARTDUBATI-AI`, one idempotent jump verified exactly once in first position, `DOCKER-USER` never flushed, only our chain replaced in one `iptables-restore --noflush` transaction; T-S37 with captures, `nft monitor`, A/B snapshots, counters per generation (no continuity assumed), and a foreign rule kept intact; nftables table if not atomic | §3 P1; SECURITY.md §7 |
| 2 | Production profile must be closed in IA-1 | **Fixed**: empty allow-list, no real nor placeholder API name, no external route; gateway and LiteLLM refuse to start with a route while the provider list is empty; T-S38 compares IA-1 profile (two fakes only) and production profile (none) | §5; SECURITY.md §7; DEPLOYMENT.md §3 |
| 3 | VM capacity | **Fixed**: exactly 4 vCPU / 8 GB for the VM; the T-S23c client may be much smaller | §1, §12 |
| 4 | « 50 tests » | **Corrected**: 47 distinct identifiers (the « 50 » was in the summary message, not in the documents); count stated in §8 | §8 |
| D | IA1-D1 to D4 | validated by the audit on substance; owner to confirm | §1 |

## 14. Answers to the audit of `b6dac22`

| # | Point | Answer | Where |
|---|---|---|---|
| 1 | Under `--noflush`, the declaration `:LARTDUBATI-AI - [0:0]` must not be relied on to empty an existing chain; rules could accumulate | **Fixed**: chain created on its own if absent; idempotent jump; dry run `iptables-restore --test --noflush`; one input `*filter`, `-F LARTDUBATI-AI`, all rules, `COMMIT`; no chain declaration line | §3 P1 |
| 2 | T-S37 must check that the rule count does not grow | **Added**: after each reload the count equals exactly that of A or B | §3 P1, T-S37 item 4 |

## 15. Green light (audit of `bdb2548`)

Revision 4 validated. IA-1 authorised, strictly within these limits: only in the separate
repository `lartdubati-ai-gateway`; WP1 to WP6 and WP8 start with unit tests; no real API
call, no provider key, no real data, no installation or change in Odoo; WP7 and WP9 wait
for the disposable VM and run the planned infrastructure tests. IA1-D1 to IA1-D4 confirmed:
separate private repository, disposable Ubuntu 24.04 LTS VM of 4 vCPU / 8 GB,
`iptables-nft` first and a dedicated nftables table if T-S37 fails.

## 16. Progress

- Repository: the owner chose **`ahajiso/odoo_ai_assistant`** (private) instead of the
  planned name `lartdubati-ai-gateway`; same role (IA1-D1). Work branch
  `claude/gallant-bohr-upcxyg`.
- WP1 (contract, validators, fake LiteLLM) done on 13/10/2026, commits `8019d27..de42fe9`:
  82 unit tests passing under Python 3.12.3 and 3.13, no call to an AI provider or model
  API (PyPI used only for the pinned packages), no secret; report
  `docs/WP1_REPORT.md` of that repository, to audit. Next: WP2 (storage).
- Audit of WP1 (`8019d27..de42fe9`, mutation testing): bounded currencies with explicit
  `unknown`, evidence pages checked, stricter value rules, calendar dates, network guard
  covering `connect_ex`, `send*`, DNS and helpers plus a static import test. Corrected in
  `dc46719`: 142 tests under Python 3.12.3 and 3.13, 11 mutations of the corrected controls,
  11 killed.
- Audit of `dc46719` / `3ca4f50`: amount alternatives typed and bounded like the amount,
  alternatives pairwise distinct, SCHEMAS.md precise on dates. Corrected in the gateway's
  commit `92e9a27` (`tools/mutation_check.py`): 161 tests (3.12.3, 3.13), 17 mutations, 17 killed.
  WP2 waits for the validation of WP1.
- WP1 validated by the audit of `92e9a27` / `2233754`. Its non-blocking point (the mutation
  tool runs the unmutated suite first and stops unless it is green) done in `e97bcc7`.
- WP2 (storage) done on 13/10/2026, commits `465c168..79bf319`: `ledger.db` main and
  `jobs.db` attached with the settings of ARCHITECTURE.md §5.1 checked at start, append-only
  ledger, tombstones, caps and reservation in the job's transaction, leases,
  `outcome_unknown`, idempotent `ack`, 7-day purge, maintenance `VACUUM`; 195 tests (34 for
  WP2, SIGKILL test of T-S32 included) under Python 3.12.3 and 3.13; 38 mutations, 38
  killed; report `docs/WP2_REPORT.md` of the gateway repository, to audit. Next: WP3 (API).
- Audit of WP2 (`465c168..79bf319`): negative amounts could lower the caps, month total
  wrong across a month change, shared store not serialised, free text in `ledger.db`.
  Corrected in `6f4eea2..c6c84d7`: non-negative money, budget period per row (inherited
  from the reservation), one `Store` per process under a lock, closed catalogue and hashes
  instead of free text, corrections as a target cost with author ref / reason code /
  evidence SHA-256, purged job rows deleted after 30 days; ARCHITECTURE.md §5.1 and
  COSTS.md §4 updated (`release`, periods, corrections). 234 tests (3.12.3, 3.13),
  59 mutations, 59 killed. WP3 waits for the validation of WP2.
- Second audit of WP2 (`f856266`): correction lines false when the rate changed, no
  correction after the 30-day purge, billable lines without provenance. Corrected in
  `0962ed5..b238189`: true cost and cancellation lines (`reverses_id`), corrections from
  the tombstone and the ledger, planned route on reservations and usage required for costs,
  frozen catalogue, identifiers matched in full; ARCHITECTURE.md §5.1 and COSTS.md §4
  updated. 264 tests (3.12.3, 3.13), 70 mutations, 70 killed. WP3 waits for the
  validation of WP2.
- Third audit of WP2 (`0962ed5..b238189`): EUR computed from the original amount instead of
  the stored one (sub-micro amounts), schema DDL run before the version check. Corrected in
  the following commits of the gateway repository: canonical stored amount, existing files
  checked before any statement and left untouched on refusal (tested on the real version-2
  schema), catalogue pairs of strings; 286 tests (3.12.3, 3.13), 76 mutations, 76 killed.
  WP3 waits for the validation of WP2.
- Owner's decision (13/10/2026): SQLite abandoned, WP2 rewritten on **PostgreSQL 16**
  (database `lartdubati_ai`, schemas `ledger` and `jobs`, no connection from Odoo,
  migrations by fingerprint, insert-only ledger, contents encrypted by the gateway with
  keys deleted at purge, ledger-only backup). Plan written without code for audit:
  gateway repository `docs/POSTGRES_PLAN.md` (`d76ca19`). The SQLite WP2 is not validated
  and is replaced; its invariants are kept. ARCHITECTURE.md §5.1, COSTS.md §4,
  DEPLOYMENT.md, SECURITY.md (T-S30 to T-S32) and SCHEMAS.md §2.3 still describe SQLite and
  are updated after the plan's audit. No code before the audit; WP3 waits.
- Audit of `POSTGRES_PLAN.md` (`d76ca19`): five blocking points (key / janitor race, clear
  `meta` and `error_message`, undefined comparison between backups, restore order with T1,
  retention through `ai_migrator`) and three complements. Revision 2 (`ba9cbc3`): `flock`
  on the key directory, typed and closed metadata (catalogue registered in the database,
  Odoo file references instead of document hashes), comparison and restore through a
  throw-away cluster, `ai_retention` role, insert-only `schema_history`, transition
  trigger, wider fingerprint; SQLite store kept until covered. O1–O8 decided by the audit;
  O9, O10 new. No code before the audit of revision 2.
- Audit of revision 2 (`ba9cbc3`): four blocking points (catalogue not closing
  `policy_ref`, checks running code from the backup, mutable comparison base, 30 days
  enforced only by the application). Revision 3 (`af45074`): immutable `catalogue_id`
  freezing the execution configuration, data-only exports loaded on trusted migrations,
  O9 mandatory (write-once target, verification on the owner's machine), closed purge
  function on the database clock, retained periods refused by the invariants. O9 and O10
  decided by the audit. No code before the audit of revision 3.
- Audit of revision 3 (`af45074`): circular backup format and accounting provenance
  not enforced in SQL; two tests asked (correction against period retention, owner-side
  chronology). Revision 4 (`53e200d`): inner manifest without archive digests, one
  encrypted object with its S3 checksum; provenance per line kind in T1, used entry kept
  in the outcome, `fallback_used` derived; period lock L3 and its race test; chronology
  from the store's own timestamps; real Object Lock test as an exit criterion before any
  real data. No code before the audit of revision 4.
- Audit of revision 4 (`53e200d`): one used entry per job incompatible with fallbacks
  after a first attempt; deterministic tar test and `VersionId` ordering to correct.
  Revision 5 (`b64cfd4`): several attempts per job (frozen chain `job_plan`, insert-only
  `job_attempts` / `attempt_outcomes`, one reservation per planned attempt, costs and
  corrections per attempt), tar test on identical inputs, chronology on `LastModified`
  only with the full-object checksum read back. No code before the audit of revision 5.
- Audit of revision 5 (`b64cfd4`): frozen plans not executable after a deployment, and
  reservations of never-started attempts kept at restore. Revision 6 (`55e2654`): versioned
  configuration registry in the image (bundles and prompts per `config_version`, kept
  while referenced, checked at start), single-generation plans (`plan_config_version`),
  exact releases of never-started attempts at restore, weekly verification up to the
  last day whose backup deadline has passed. No code before the audit of revision 6.
- Audit of revision 6 (`55e2654`): an answered attempt could be committed without the
  job's finalisation; composite foreign key to the catalogue not feasible. Revision 7
  (`8d739cd`): terminal attempts closed only with the job in one transaction (deferred
  trigger T7, crash tests around the commit, inconsistent archive refused);
  `primary_catalogue_id` in `job_index`. The audit announced the development green
  light after this documentary correction; it is awaited before any code.
- Audit of revision 7 (`8d739cd`): green light for the PostgreSQL code (§15), with the
  precision that T7 fires from both attempt_outcomes and job_outcomes. WP2 on PostgreSQL
  developed in the gateway repository (`3f4d9f0`..`d54e126`): schema V0001 (T1–T7, database
  clock, closed purge functions), PgStore with attempts and fallbacks, application
  encryption with the key-directory lock and janitor, check_database(), data-only
  archives with trusted load, comparison and restore, write-once target client (local
  stub) and owner-side verification, contract 2.0 changes, crash tests. 531 tests on
  Python 3.12.3 and 3.13; 64 PostgreSQL mutations: 58 killed, 6 declared equivalent.
  Report and SQLite → PostgreSQL coverage matrix: docs/WP2_REPORT.md of the gateway
  repository; deviations listed there for the audit. Waiting for the audit; WP3 waits.

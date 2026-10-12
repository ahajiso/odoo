# IA-1 – development plan of the isolated AI server (revision 1, 12/10/2026, no code)

Green light of the audit of `400a3c0..95fdf3c`: **writing this plan only**. Not yet a
green light to code, install a server or call a real API. This plan is audited before any
implementation.

Basis: PLAN.md revision 4 and its companions (ARCHITECTURE, SECURITY, SCHEMAS,
DEPLOYMENT, COSTS). Section and test numbers below refer to them.

## 0. Scope

**In IA-1**
- the gateway (FastAPI API + worker, `jobs.db` / `ledger.db`), the three functions with
  their schemas, the confidentiality pre-check, minimisation, validation, budget ledger,
  idempotency, `ack`, mTLS + HMAC;
- a **fake provider** (two services imitating the Anthropic and OpenAI APIs on a test
  network) and a **fake LiteLLM** for unit tests;
- the real LiteLLM proxy image (pinned), configured **only** with the fake providers'
  addresses, to observe what it sends (H-AI-1, without any real call);
- the extractor (text layer, OCR, sandboxed child per document);
- the egress proxy, the firewall rules, the systemd units (`ai-firewall`, `ai-stack`,
  check timer, capture unit for the tests);
- synthetic data set, test suites, load and isolation tests, the IA-1 report.

**Not in IA-1** (unchanged gates): any real provider key or call (IA-1b, after D3, D4, D6
and official verification), any Odoo module or change on `artdubati_test`, any change on
the Odoo VPS, any real document or real user text.

## 1. Decisions needed to start (owner)

| # | Decision | Options | Recommendation |
|---|---|---|---|
| IA1-D1 | Where the gateway code lives | (a) a new private repository `lartdubati-ai-gateway`; (b) a directory of this repository | **(a)**: this repository is the Odoo addons folder cloned at `/opt/odoo/addons/custom`; the AI server's code must never be deployed with Odoo's modules nor be readable from `odoo_web`. The owner creates it and gives this session access (`add_repo`); `docs/ai/` stays here as the design record |
| IA1-D2 | Where container and isolation tests run | (a) a disposable VM given by the owner (same OS family as the future AI server); (b) the future AI server itself, before it holds any secret | **(a)** for everything; (b) is acceptable as the « disposable » machine as long as it is reinstalled before IA-1b. This development session has the Docker client but **no Docker daemon**: it runs unit tests only |
| IA1-D3 | OS of the AI server and of the test VM | e.g. Debian 13 or Ubuntu 26.04 LTS | an LTS with nftables, AppArmor and systemd ≥ 252; same on VM and server |
| IA1-D4 | Firewall backend | (a) `iptables-restore` on `DOCKER-USER` (iptables-nft); (b) a separate nftables table hooked on `forward` | **(a)** first, because Docker's own chains are iptables-based; (b) if WP7 shows (a) is not atomic on the chosen OS (§3, P1) |

## 2. Repository layout (in `lartdubati-ai-gateway`, IA1-D1 a)

```
gateway/            FastAPI app, worker, storage (ledger.db + jobs.db), budget, auth,
                    pre-check, minimisation, prompts, validation, routing
schemas/            JSON Schema files (contract 2.0) with their SHA-256 list
extractor/          service + sandboxed child, limits, chunking, OCR
fakes/              fake_litellm (unit tests), fake_anthropic, fake_openai (stack tests),
                    with recorded answers and failure modes (SCHEMAS.md §7)
deploy/             compose.yaml (restart: "no", fixed subnets, hardening), Dockerfiles,
                    lock files with hashes, egress proxy config, firewall/expected.rules,
                    systemd units, scripts (firewall-apply, firewall-verify, capture)
fixtures/           synthetic data set (§5) and its generator
tests/unit/         run anywhere (this session, CI): no Docker, no network
tests/stack/        run on the test VM: compose stack with fakes
tests/isolation/    run on the test VM as root: firewall, start order, crash, capture
docs/               IA-1 report, measurements, pinned versions record
```

CI (if the owner enables GitHub Actions on that repository): unit tests only, no secret,
no outbound call except package download from the hash-locked lock file.

## 3. Precisions required by the audit of `400a3c0..95fdf3c`

**P1 – Atomic firewall reload, or the stack stopped first.**
- `firewall-apply` writes one `iptables-restore --noflush` input containing, for the
  `filter` table, `-F DOCKER-USER` followed by the full rule list and a single `COMMIT`;
  with the iptables-nft backend this is one netlink transaction. WP7 verifies it: a test
  floods connection attempts from an AI container during 1 000 reloads and counts any
  packet that left (expected 0).
- In addition (defence in depth), any **change** of the rules goes through
  `firewall-change`: `systemctl stop ai-stack` → apply → verify → `systemctl start
  ai-stack`. Only the boot path (no container running yet) and the 5-minute check
  (verify only, no apply) skip the stop.
- If WP7 shows the reload is not atomic on the chosen OS: IA1-D4 (b), a dedicated nftables
  table (`table inet ai_guard`, chain on `forward` hook with a priority before Docker's
  filter), loaded with `nft -f` (transactional by design), dropping AI-subnet traffic not
  explicitly allowed; `DOCKER-USER` then only mirrors it.

**P2 – T-S23e capture before Docker.** Bridges do not exist before Docker starts, so:
- `ai-capture.service` (tests only, enabled on the VM for T-S23e runs):
  `Before=docker.service`, `WantedBy=multi-user.target`, runs `tcpdump -i any -n -U -w
  /var/log/ai-test/any-%b.pcap` (the `any` pseudo-interface sees bridges and veths created
  later) and a second `tcpdump -i <ext_if>` (packets after NAT, as seen by the outside);
- evidence combined by the analysis script: packets whose source is in the AI subnets (on
  `any`) or whose destination is not an allowed one (on `<ext_if>`), versus
  `journalctl -u ai-firewall -u ai-stack -u docker` timestamps, `docker events` (from
  dockerd's start) and each container's `State.StartedAt`;
- pass: no AI container started before `ai-firewall` succeeded, no packet from an AI
  subnet to a non-allowed destination, on 10 consecutive reboots and 10 Docker restarts.

**P3 – Health probes of LiteLLM and of the egress proxy.**
- Docker `HEALTHCHECK` = internal check without network: for LiteLLM, the process is alive
  and its listening socket exists (read from `/proc/net/tcp*` inside the container); for
  the proxy, its own check command (`squid -k check` or the equivalent of the chosen
  proxy) plus the same socket check. No HTTP probe.
- LiteLLM's own unauthenticated health routes on its service port (if the pinned version
  has them and they cannot be disabled or put behind authentication) are reachable only
  from `net_llm`, whose sole other member is the gateway. WP4 checks whether they can be
  disabled or authenticated; otherwise the gateway is the only client by network design.
- Test T-S35: from the extractor, the egress proxy and a throw-away test container on
  each network (`net_doc`, `net_egress`, `net_front`), LiteLLM's port and any health
  route are unreachable; from a test container on `net_egress`, the proxy refuses it by
  its source ACL; from the gateway, LiteLLM's health routes answer at most liveness
  (no configuration, no key, no model list).

**P4 – Brutal crash of `dockerd`.**
- Test T-S36 on the VM: `kill -9 $(pidof dockerd)` while jobs run, with the capture unit
  active; then let systemd restart Docker (its unit's `Restart=`) and observe:
  containers during the outage (they may keep running under `containerd-shim`; the kernel
  rules stay in place), containers after dockerd's return (`live-restore: false`), state
  of `ai-firewall` and `ai-stack`.
- Expected design, confirmed or corrected by the test: `ai-firewall` and `ai-stack` get
  `BindsTo=docker.service` in addition to `PartOf=`, so that any transition of
  `docker.service` to inactive or failed stops them; after Docker's automatic restart, the
  stack **stays stopped** until a controlled resume (`systemctl start ai-stack`, which
  re-verifies the rules), with an alert. Jobs interrupted after `attempt_started` become
  `outcome_unknown` (not retried).
- The same test with `kill -9` of `containerd`, and with `systemctl restart docker`
  (T-S23d) for comparison. Results and the final unit settings go in the IA-1 report.

## 4. Work packages (each a few small commits, unit tests first)

| WP | Content | Tests (SECURITY.md §12 numbers where they exist) | Where |
|---|---|---|---|
| WP1 | Contract: JSON Schemas (envelope, job, three functions, errors), SHA-256 list, validators; fake LiteLLM with failure modes | schema tests; T-S02, T-S03, T-S04, T-S07 | unit |
| WP2 | Storage: `ledger.db` main + `jobs.db` attached, pragmas (`DELETE`, `FULL`), same-filesystem check, single writer, job states, leases, tombstones, purge, maintenance `VACUUM` | T-S08, T-S09, T-S09b, T-S30, T-S32 (exception and `SIGKILL` in unit; hard reset on the VM) | unit + VM |
| WP3 | API: `POST/GET /v1/jobs`, `ack`, `/v1/health`; mTLS (test CA generated per test run) and HMAC (two keys, nonce cache); kill switch; `REAL_DATA_ALLOWED=false`; maintenance mode | T-S17, T-S27, T-S33 (gateway side), ack idempotence, 410 | unit |
| WP4 | Worker: semaphores, pipeline, routes and data-policy check at load, fallbacks on availability only, budget reservation / settlement / manual correction, ledger in billing currency with rate; LiteLLM client (OpenAI-compatible call to the proxy) | T-S05, T-S06, T-S10, T-S14, T-S34; H-AI-1 observed through the fake providers behind the real LiteLLM (what it sends for structured outputs and region parameters) | unit + stack |
| WP5 | Pre-check and minimisation: detectors (bank, identity, HR, personal, legal) in fr / en / fa, levels, floor rule, unclassifiable → blocked, pseudonymisation | T-S24, T-S25, T-S26; per-detector true / false positive sets | unit |
| WP6 | Extractor: magic bytes, size / page limits read before parsing, sandboxed child with rlimits, tmpfs per job, OCR fra / eng / fas, chunking with page refs, evidence check, instruction-like text flag, own semaphore | T-S18, T-S19, T-S01a, bomb-like PDFs and images | unit + stack |
| WP7 | Infrastructure: compose (fixed subnets, `internal`, hardening, `restart: "no"`), egress proxy (source ACL, CONNECT 443, allow-list, `to_special`, own DNS), firewall apply / verify / change (P1), units (`ai-firewall`, `ai-stack` with `BindsTo=` per P4, check timer), Docker daemon settings, internal health checks (P3) | T-S20 … T-S23f, T-S35, T-S36, atomic reload test (P1) | VM |
| WP8 | Synthetic data set and generator (§5); canary strings; scenario fixtures S1–S17 as recorded fake answers | T-S13, T-S31 (canaries absent from logs, `ledger.db` and its backup) | unit + stack |
| WP9 | Load and memory test at the configured concurrency; IA-1 report | DEPLOYMENT.md §6; T-S34 | VM |

Order: WP1 → WP2 → WP3 → WP5 → WP6 → WP4 → WP8 → WP7 → WP9. WP1 to WP6 and WP8 need no
machine (unit tests in this session or CI); WP7 and WP9 need the VM (IA1-D2).

## 5. Synthetic data set

- Generated by a script from templates (no real document ever copied): insurance
  policies (RC Pro, décennale, warehouse), subscriptions (internet, phone, ChatGPT), quotes
  and bills (van, trailer, tiles, workwear, equipment), rental and loan contracts,
  consignment, contradictory and incomplete variants; French, English and Persian.
- Fictitious companies and persons from a fixed list; IBAN, NIR, card numbers generated
  with valid checksums only for the pre-check tests, from reserved test ranges where they
  exist.
- Scans: the same documents rendered to images with noise, rotation and low resolution
  for OCR.
- Adversarial: injected instructions in visible text, white text, metadata, form fields,
  footnotes; decompression-bomb-like PDFs; oversized images; wrong magic bytes.
- Every fixture carries a unique canary string, searched for in logs, `ledger.db` and its
  backup (T-S13, T-S31); every request built from fixtures carries `synthetic: true`.

## 6. Guards against real calls and real data

- No real key exists in IA-1. The test suites fail if an environment variable or secret
  file looks like a provider key (`sk-…`, `sk-ant-…`) or if a route points to a host that
  is not a fake provider.
- The egress proxy's allow-list on the VM contains **only the fake providers' names**
  (served on a test network with a test CA); the real API hosts are absent, so even a
  misconfigured LiteLLM cannot reach them.
- `REAL_DATA_ALLOWED=false`; jobs without `synthetic: true` are refused (T-S27).

## 7. Pinned versions

At implementation time, each component version (Python, FastAPI, LiteLLM image, base
images, proxy, Tesseract) is chosen at least two weeks after its release, recorded with
its digest or hash and its source in `docs/pinned_versions.md` of the gateway repository;
LiteLLM's image signature and `.pth` list checked (SECURITY.md §9). Versions are not chosen
in this plan.

## 8. Exit criteria and report

IA-1 is done when, on the test VM and in unit tests:
- every test of SECURITY.md §12 except T-S01b, plus P1's atomic reload test, T-S35 and
  T-S36, passes, with logs kept;
- the load test passes at the configured concurrency (memory figures recorded);
- H-AI-1 (what LiteLLM sends to each provider format), H-AI-6 (DNS on internal networks)
  and the P4 behaviour are answered with evidence;
- the IA-1 report lists what was verified, what was not, the open hypotheses, the pinned
  versions and digests, and the final unit and firewall settings.

The report is audited. Only then can IA-1b (real calls with synthetic data, after D3, D4,
D6 and the official verification of providers) or the AI server's installation for real be
planned.

## 9. What the owner provides or does

- IA1-D1 to IA1-D4;
- the private repository and this session's access to it;
- the disposable test VM (IA1-D2), with root access for the isolation tests, and the
  commands to run there (the session prepares scripts; the owner runs them, as for the
  Odoo server);
- nothing on the Odoo VPS, `artdubati_test` or the provider accounts in IA-1.

## 10. Open hypotheses settled by IA-1

| # | Hypothesis | Settled by |
|---|---|---|
| H-AI-1 | LiteLLM passes structured outputs and region parameters to each provider format | WP4, fake providers behind the real LiteLLM |
| H-AI-3 | 4 vCPU / 8 GB holds the stack at the configured concurrency | WP9 |
| H-AI-6 | no Internet DNS resolution from internal networks | WP7, T-S21 |
| H-IA1-1 | `iptables-restore --noflush` with one `COMMIT` is atomic on the chosen OS | WP7, P1 |
| H-IA1-2 | after a `dockerd` crash, `BindsTo=` keeps the stack stopped until a controlled resume | WP7, P4 |
| H-IA1-3 | LiteLLM's unauthenticated health routes can be disabled or are only reachable from the gateway | WP4 / WP7, P3 |

H-AI-2 (Odoo reachability), H-AI-4 (provider settings), H-AI-5 (real token counts) and
H-AI-7 (provider request ids in usage data) are **not** settled by IA-1.

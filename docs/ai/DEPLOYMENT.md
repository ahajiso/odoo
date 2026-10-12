# AI assistant – deployment and operations (IA-0, revision 1, 12/10/2026)

Nothing here is to run before the audit and the owner's go, except the **read-only**
characterisation of §1. No deployment before: plan audited, decisions answered, memory
load test (§6), backup, rehearsed rollback (§7).

## 1. Server characterisation (read-only, run by the owner)

Paste the output into `docs/ai/characterisation/server_<date>.txt` (masking secrets).
None of these commands changes anything.

```bash
# resources
uname -a; nproc; lscpu | head -20; free -m; df -h; uptime
vmstat 5 12                      # 1 minute of CPU / memory / IO
docker stats --no-stream         # memory and CPU per container now
# repeat « free -m » and « docker stats --no-stream » at a busy time of a working day

# containers and images
docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
docker inspect -f '{{.Name}} restart={{.HostConfig.RestartPolicy.Name}} mem={{.HostConfig.Memory}} cpus={{.HostConfig.NanoCpus}}' $(docker ps -q)
docker compose ls 2>/dev/null || true

# networks
docker network ls
docker network inspect $(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' odoo_web) \
  --format '{{.Name}} driver={{.Driver}} internal={{.Internal}} members={{range .Containers}}{{.Name}} {{end}}'

# how secrets are provided (names only, values masked)
docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' odoo_web | sed -E 's/=.*/=<masked>/'
docker inspect -f '{{range .Mounts}}{{.Source}} -> {{.Destination}} ({{.Mode}}){{println}}{{end}}' odoo_web
docker exec odoo_web sh -c 'ls -l /etc/odoo/ 2>/dev/null; grep -E "^(workers|max_cron_threads|limit_memory_soft|limit_memory_hard|limit_time_cpu|limit_time_real|limit_time_real_cron|proxy_mode)" /etc/odoo/odoo.conf 2>/dev/null'

# outbound network and firewall (read)
sudo iptables -S 2>/dev/null | head -50 || sudo nft list ruleset | head -80
getent hosts api.anthropic.com api.openai.com

# reverse proxy (to make sure a new container is never exposed by mistake)
docker ps --format '{{.Names}} {{.Ports}}' | grep -E '0\.0\.0\.0|:::' || true
```

Results expected in PLAN.md §1.1. Decision rule for D1: option (a) only if, at the busiest
measured moment, **available memory ≥ 2 GB** after Odoo and PostgreSQL, and load average
below the number of cores.

## 2. Hosting options (D1)

| | (a) Odoo VPS | (b) separate small VPS | (c) (a) now, (b) later |
|---|---|---|---|
| Cost | none | a small VPS (to quote; 2 vCPU / 4 GB class) | none, then (b) |
| Isolation | shared kernel and memory with Odoo; a runaway gateway can starve Odoo (mitigated by limits) | full: a compromise of the gateway does not reach the Odoo host | as (a), then (b) |
| Network | Docker networks; **`odoo_web` on two networks breaks `deploy_modules.sh`, `roadmap0/finish_window.sh` and `roadmap0/run_migration.sh`** (they require exactly one); adapting them is part of IA-2's deployment | WireGuard or TLS + HMAC (+ mTLS) between hosts; `odoo_web` keeps one network; outbound only | |
| Ollama (IA-5) | not realistic (5–8 GB, CPU) | possible with a larger machine | |
| Test / prod separation | test and prod gateways side by side, separate keys | one gateway per environment, or two containers on it | |

Recommendation: (a) for IA-1 / IA-2 on `artdubati_test` if §1 allows, with the network
plan of §3; (b) before production or before IA-5.

### 2.1 Alternative for (a) without a second network on `odoo_web`

Put the gateway on the existing network of `odoo_web` (no script change). Rejected as the
default: the gateway would then reach `odoo_db` on the network level (no credentials, but
« no PostgreSQL access » should also hold at the network level). Kept only if the owner
prefers not to touch the scripts; then PostgreSQL's `pg_hba.conf` must refuse the gateway's
address (to characterise).

## 3. Containers and networks (option a)

| Container | Image | Networks | Egress | Limits (initial, to tune after §6) |
|---|---|---|---|---|
| `ai_gateway` | own image, built from a pinned base **by digest**, LiteLLM and FastAPI hash-locked | `ai_front` (with `odoo_web`), `ai_back` (with the extractor) | providers' API hosts only | 1 CPU, 768 MB, pids 128 |
| `ai_extractor` | own image (pypdf, pdfminer, Tesseract fra/eng/fas), pinned digest | `ai_back` only, `internal: true` | **none** | 1 CPU, 1 GB, pids 64, timeout per file |

- `ai_front` and `ai_back` are user-defined networks; `ai_back` is `internal`; neither
  contains `odoo_db`.
- Nothing published on the host; not added to the reverse proxy.
- Both: non-root, read-only root fs, tmpfs `/tmp` (size-limited), `no-new-privileges`,
  `cap_drop: ALL`, `restart: unless-stopped`, logging driver with size rotation.
- Health checks: `GET /v1/health` (gateway), `GET /health` (extractor), every 30 s,
  3 failures → unhealthy; Odoo's cron checks health before a batch and leaves requests
  `queued` if unhealthy.
- Script changes in IA-2 (separate commit, own tests): `docs/deploy_modules.sh` (and the
  one-shot scripts of `docs/roadmap0/` if they are reused) select **the network shared
  with `odoo_db`** instead of requiring exactly one network. `backup_db.sh` and
  `restore_db.sh` do not read the networks (checked).

Illustrative compose fragment (for the audit, not to apply):

```yaml
services:
  ai_gateway:
    image: registry.local/lartdubati-ai-gateway@sha256:<digest>
    user: "10001:10001"
    read_only: true
    tmpfs: ["/tmp:size=64m"]
    security_opt: ["no-new-privileges:true"]
    cap_drop: [ALL]
    mem_limit: 768m
    cpus: 1.0
    pids_limit: 128
    secrets: [anthropic_api_key, openai_api_key, ai_hmac_keys]
    volumes: ["./profiles.yaml:/app/profiles.yaml:ro", "ai_ledger:/var/lib/ai"]
    environment: {ENV: test, ENABLED: "true"}
    networks: [ai_front, ai_back]
    healthcheck: {test: ["CMD", "python", "-c", "…/v1/health"], interval: 30s, retries: 3}
  ai_extractor:
    image: registry.local/lartdubati-ai-extractor@sha256:<digest>
    networks: [ai_back]
    # same hardening, mem_limit: 1g
networks:
  ai_front: {}
  ai_back: {internal: true}
secrets:
  anthropic_api_key: {file: /opt/ai/secrets/anthropic_api_key}   # 0400, root-owned dir
```

`odoo_web` gets `ai_front` and a read-only file mount of the current HMAC key.

## 4. Persistence and backup

| Data | Where | Backup |
|---|---|---|
| Requests, proposals, call logs | Odoo database | existing `backup_db.sh` |
| Attachments | Odoo filestore | existing `backup_db.sh` |
| Cost ledger (metadata), idempotency cache | `ai_ledger` volume (SQLite) | ledger: daily copy; cache: not backed up (24 h) |
| `profiles.yaml`, prompt templates, schemas | gateway repository (private) + mounted file | Git |
| Secrets | `/opt/ai/secrets` | **not** in backups of the repo; kept in the owner's password manager |

## 5. Operations

- **Restart**: `docker restart ai_gateway`; in-flight calls fail with `timeout` on the Odoo
  side and are retried idempotently.
- **Kill switch**: Odoo setting off (no call queued) and/or gateway `ENABLED=false`
  (answers `disabled`). Either alone keeps Odoo fully functional.
- **Secret rotation** (SECURITY.md §3.1): HMAC: add key B in the gateway file → restart →
  switch Odoo's mounted key to B → restart `odoo_web` at a quiet time → remove A. Provider
  keys: new key → file → restart gateway → revoke old one. Rehearsed in IA-1.
- **Model update** (ARCHITECTURE.md §10): config change with its own short plan, capped
  comparison run, then restart.
- **Software update** (LiteLLM, FastAPI, base image): plan, version older than two weeks,
  release notes and security advisories read, hashes / signature checked, rebuild, tests
  with fake provider, memory test, deploy with rollback image kept.
- **Metrics** (exposed only on `ai_front`, read by a cron in Odoo or by a script): calls,
  errors by code, validation failures, latency p50 / p95 per function, cost per day /
  function / profile / user, budget remaining.
- **Alerts** (mail to the owner through Odoo's outgoing mail): 80 % and 100 % of the
  monthly cap; error rate > 20 % over 1 h; gateway unhealthy > 10 min; any
  `invalid_output` rate rise after a model change.

## 6. Memory load test (before any deployment)

On a copy environment (local or the server with the gateway alone), with the fake
provider: 5 concurrent `extract_document` calls with a 50-page text PDF and a 10-page
scanned PDF, 30 minutes; record `docker stats` every 5 s; pass if peaks stay below the
limits of §3 and no OOM kill; result in `docs/ai/characterisation/load_<date>.txt`.
On the server, run it while Odoo is in normal use only after the owner's go, and watch
`free -m`.

## 7. Backup and rollback

Deployment order (IA-2 example): characterisation clean → PLATFORM OK (existing
`check_modules.sh`) → backup (`backup_db.sh`, manifest) → start gateway and extractor
(health OK, AI still disabled in Odoo) → install `lartdubati_ai_assistant`
(`deploy_modules.sh`) → tests → routes inventory compared → enable for one test user.

Rollback (rehearsed before the window, on a local copy):
1. Odoo setting off; `docker stop ai_gateway ai_extractor`.
2. Uninstall the module or restore the backup with `restore_db.sh` if the install changed
   anything else (it should not).
3. Remove `ai_front` from `odoo_web`; restore the previous versions of the deployment
   scripts if they were changed.
4. PLATFORM OK, post-check, test suites of the existing modules green.

## 8. Preconditions before any deployment (checklist)

- [ ] PLAN audited, decisions D1–D15 answered
- [ ] characterisation §1 done and within the rule of §1
- [ ] provider accounts: DPA accepted, retention / ZDR / residency settings as decided
      (D5, D6), spend limit set at the provider, project-scoped keys
- [ ] images built, digests recorded, dependency hashes and LiteLLM signature checked
- [ ] memory load test passed (§6)
- [ ] backup with manifest; rollback rehearsed
- [ ] test / production separation respected (`docs/deployment/investor_home.md` §0):
      this deployment is for `artdubati_test` only

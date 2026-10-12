# AI assistant – deployment and operations (IA-0, revision 3, 12/10/2026)

Revision 2: the AI runs on a **separate server**; the Odoo VPS gets **no new service and
no new network**, and its scripts are unchanged. Its only infrastructure change is the
delivery of the module's secrets (D16), which with option (b) recreates `odoo_web` with one
more read-only mount (§4.1, with its rollback). Revision 3: 4 vCPU / 8 GB with explicit
concurrency, encrypted disk, `jobs.db` not backed up and `ledger.db` backed up, Docker-aware
firewall. Nothing is to run before the audit and the owner's go, except the read-only
characterisation of §1.

## 1. Characterisation (read-only, run by the owner)

### 1.1 Odoo VPS — only what the AI needs from it

Output to paste into `docs/ai/characterisation/odoo_vps_<date>.txt` (secrets masked).

```bash
# resources (confirms the 4 GB of the audit; for information)
nproc; free -m; df -h; uptime; docker stats --no-stream

# how odoo_web gets its configuration and secrets (D16)
docker inspect -f '{{range .Mounts}}{{.Type}} {{.Source}} -> {{.Destination}} ({{.Mode}}){{println}}{{end}}' odoo_web
docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' odoo_web | sed -E 's/=.*/=<masked>/'
docker exec odoo_web sh -c 'ls -ld /etc/odoo /etc/odoo/* /run/secrets 2>/dev/null; id'
# what creates odoo_web (no script of this repository does): compose project or docker run
docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}} {{index .Config.Labels "com.docker.compose.project.config_files"}}' odoo_web
docker inspect -f '{{json .HostConfig.Binds}} {{json .HostConfig.RestartPolicy}}' odoo_web

# outbound from odoo_web (H-AI-2): public address of the VPS, HTTPS reachability
curl -s https://api.ipify.org; echo
docker exec odoo_web python3 -c "import socket; s=socket.create_connection(('example.com',443),5); print('outbound 443 OK')"
docker exec odoo_web python3 -c "import requests, ssl; print(requests.__version__, ssl.OPENSSL_VERSION)"
```

Expected use: the VPS public address (firewall of the AI server), whether `/etc/odoo` is a
host bind mount (D16 a), whether `odoo_web` can open outbound HTTPS, and that `requests`
supports client certificates (it does in every recent version; checked anyway).

### 1.2 AI server (after it is rented, before anything is installed)

```bash
uname -a; nproc; free -m; df -h; cat /etc/os-release
docker version; docker info | grep -iE 'seccomp|apparmor|cgroup'
sudo nft list ruleset 2>/dev/null || sudo iptables -S
```

## 2. AI server (D1)

| Item | Proposal |
|---|---|
| Size | **4 vCPU, 8 GB RAM**, 40 GB disk (recommended, keeps 5 concurrent jobs); fallback 2 vCPU / 4 GB only with the reduced concurrency of ARCHITECTURE.md §5.2 (1 extraction, 1 OCR); a distinct, larger machine if Ollama comes (IA-5) |
| Location | EU data centre of a provider chosen by the owner (the host is a processor too; its DPA in the processing records) |
| OS | a supported LTS distribution, automatic security updates of the OS only (not of the containers), AppArmor enabled |
| Disk | data volume (`/opt/ai`: `jobs.db`, `ledger.db`, secrets) **encrypted** (LUKS, key not held by the hosting provider, unlocked by the owner at boot or by a key file on a separate volume, to decide); swap off or encrypted; backup target encrypted |
| Access | SSH by key only, from the owner's addresses; no password login |
| Inbound | the gateway's HTTPS port from the Odoo VPS address only (mTLS); nothing else |
| Outbound | through `ai_egress` for the containers; OS updates for the host |
| Test / production | one gateway per environment (separate ports, keys, CA-issued client certs, budgets, `jobs.db` and `ledger.db`); production only after the separation of `docs/deployment/investor_home.md` §0 |

Memory budget on 8 GB at the concurrency of ARCHITECTURE.md §5.2 (to confirm by §6):
gateway 400 MB, LiteLLM proxy 1 GB, extractor 2.5 GB (3 text extractions of ~300 MB and
2 OCR children of ~700 MB at peak), egress proxy 150 MB, OS and Docker 1 GB → about 5 GB,
leaving about 3 GB of margin. On 4 GB with 1 extraction and 1 OCR: about 3.2 GB, margin
0.8 GB, acceptable only with that reduced concurrency.

## 3. Containers and networks

| Container | Image | Networks | Inbound | Egress | Limits (initial) |
|---|---|---|---|---|---|
| `ai_gateway` | own image, pinned base digest, hash-locked deps | `net_front` (published port), `net_llm`, `net_doc` | Odoo VPS only, mTLS (`DOCKER-USER` rule) | **none**: dropped by the `DOCKER-USER` default deny (SECURITY.md §7) | 1 CPU, 512 MB, pids 128 |
| `ai_litellm` | LiteLLM image **by digest**, signature checked | `net_llm`, `net_egress` (both internal) | gateway only | through `ai_egress` only | 1 CPU, 1.5 GB, pids 256 |
| `ai_extractor` | own image (pypdf / pdfminer, Tesseract fra/eng/fas), pinned | `net_doc` (internal) | gateway only | none | 2 CPU, 3 GB, pids 64; children capped by its own semaphore |
| `ai_egress` | forward proxy, pinned digest | `net_egress` (internal), `net_out` (external) | `ai_litellm` only | allow-listed hosts, port 443, CONNECT only | 0.5 CPU, 128 MB |

`net_llm`, `net_doc`, `net_egress` are `internal: true`; every network has a fixed
subnet and `ai_egress` a fixed address. Filtering is done in Docker's `DOCKER-USER` chain
(default deny for the AI subnets, outbound only for `ai_egress` on 443 and DNS to the
configured resolvers, inbound to the gateway's port only from the Odoo VPS), installed by a
systemd unit after Docker and checked daily; `userland-proxy: false`. Full rules and tests:
SECURITY.md §7 (T-S20 … T-S23d).

Hardening for all: non-root user, read-only root fs, size-limited `tmpfs`,
`no-new-privileges`, `cap_drop: ALL`, seccomp (default or tighter), AppArmor profile,
logging driver with rotation, `restart: unless-stopped`, health checks
(`/v1/health` for the gateway; LiteLLM's liveness endpoint on `net_llm`; extractor's own).

Egress proxy allow-list (illustrative; final names from D3 / D6):

```
acl litellm src <ai_litellm_ip>/32
acl api_hosts dstdomain api.anthropic.com api.openai.com
acl ssl_port port 443
acl to_special dst 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 127.0.0.0/8 169.254.0.0/16 100.64.0.0/10 0.0.0.0/8 ::1 fc00::/7 fe80::/10
http_access deny !litellm
http_access deny !CONNECT
http_access deny CONNECT !ssl_port
http_access deny to_special
http_access allow CONNECT api_hosts
http_access deny all
dns_nameservers <resolvers>
```

IP-literal requests are refused by the `dstdomain` list (no IP entry); `to_special` is
checked on the resolved address, so an approved-looking name resolving to a private or
metadata address is refused too.

## 4. Secrets on each side

| Side | Files | Note |
|---|---|---|
| AI server | `/opt/ai/secrets/{anthropic,openai}_key` → `ai_litellm` only; `litellm_client_key` → gateway and LiteLLM; `hmac_keys`, TLS server key and cert, CA cert → gateway | directory 0700 root; mounted as Docker secrets (files, 0400) |
| Odoo VPS | Odoo client key and cert, CA cert, current HMAC key | fixed path inside `odoo_web`: **`/run/secrets/lartdubati_ai/`** (D16); `odoo.conf` holds no secret and, by default, nothing at all for the AI |

The owner keeps a copy in a password manager; secrets never in Git, in the Odoo database,
in environment variables, in `odoo.conf`, or in backups of this repository.

### 4.1 D16 on the Odoo VPS (revision 3)

- **(b) recommended**: host directory `/opt/odoo/secrets/lartdubati_ai/` (0700, files 0400,
  owned by the uid of the `odoo` user of the image) bind-mounted **read-only** at
  `/run/secrets/lartdubati_ai/`. This recreates `odoo_web` once:
  1. backup with `backup_db.sh` (manifest);
  2. record the current definition: `docker inspect odoo_web > odoo_web_before_<stamp>.json`
     and, if it is a compose project (§1.1), a copy of the compose file;
  3. add the mount to whatever creates `odoo_web` (compose file or the owner's
     `docker run` command: **no script of this repository creates `odoo_web`**, they only
     start one-shot containers from it);
  4. recreate, then check: same image id, same networks, same environment variable
     names, same other mounts, same restart policy as in step 2 (diff of the two
     `docker inspect` outputs limited to the new mount); `docker exec odoo_web ls
     /run/secrets/lartdubati_ai/`; Odoo answers; PLATFORM OK.
  Rollback: recreate from the recorded definition without the mount (step 2 file), same
  checks; the module, if installed, runs in « disabled: secrets missing » mode.
- **(a)** if §1.1 shows that `/etc/odoo` is already a host directory mounted read-only:
  files placed in `/etc/odoo/lartdubati_ai/`, no recreation; the module then needs one
  non-sensitive line in `odoo.conf`, `lartdubati_ai_secrets_dir = /etc/odoo/lartdubati_ai`
  (a path, not a secret). Rollback: remove the files and the line, restart.
- Persistence of the mount: the definition that creates `odoo_web` (compose file or
  documented `docker run`) is the only place that must carry it; it is added to the
  deployment checklist and checked by the module's post-check (`/run/secrets/lartdubati_ai/`
  present and readable by the `odoo` user, files not world-readable). The one-shot
  containers of `deploy_modules.sh`, `backup_db.sh`, `restore_db.sh` and the roadmap0
  scripts use `--volumes-from odoo_web` and therefore **inherit** the mount read-only;
  `backup_db.sh` archives only the filestore directory (`tar -C "$FS" "$DB"`), so the
  secrets never enter a backup archive (checked in the IA-2 rehearsal by listing the
  archive).

## 5. Operations

- **Kill switch**: Odoo setting (default off) and gateway `ENABLED=false`; either keeps
  Odoo fully functional.
- **Restart**: `docker restart ai_gateway`; jobs `received` resume; `running` jobs whose
  worker died after `attempt_started` become `outcome_unknown` (not retried).
- **Rotation**: SECURITY.md §3; rehearsed in IA-1.
- **Model change**: configuration change with a short plan and a capped comparison run.
- **Software update**: plan, versions ≥ 2 weeks old, advisories read, hashes / signatures
  checked, rebuild, full test suite with the fake provider, memory test, deployment with
  the previous images kept for rollback.
- **Metrics** (gateway, readable by Odoo's cron through the same mTLS channel, or by a
  script on the AI server): jobs by state and code, validation failures, latency p50 / p95
  per function, cost per day / function / profile / user, budget remaining, blocked
  pre-checks by category (counts only).
- **Alerts** (mail through Odoo, or the AI server's own mail relay): 80 % and 100 % of the
  month cap; error rate > 20 % over 1 h; gateway unhealthy > 10 min; any
  `outcome_unknown`; reconciliation difference > 5 %.
- **Daily reconciliation**: ledger vs provider usage. `outcome_unknown` jobs: settled
  exactly only when the provider's usage identifies the request; otherwise the
  reservation stays and only a traced `manual_correction` by an « AI Budget Manager » can
  change it (COSTS.md §4).
- **Firewall check**: daily comparison of the `DOCKER-USER` rules with the expected list;
  alert on difference (SECURITY.md §7).
- **Purge**: hourly job deleting acknowledged results and results older than 7 days from
  `jobs.db`; weekly `VACUUM`; the purge count is a metric.

## 6. Load and memory test (IA-1, before any deployment)

On the AI server, fake provider, synthetic documents, **at the configured concurrency**
(ARCHITECTURE.md §5.2): 20 jobs submitted at once (mix of 50-page text PDFs and 10-page
scans), repeated for 30 minutes; `docker stats` every 5 s. Pass if: running jobs,
extractions and OCR never exceed their semaphores (T-S34); no container exceeds its limit;
no OOM kill; host available memory ≥ 2 GB on 8 GB (≥ 0.8 GB on the 4 GB fallback);
queued jobs all finish. Result in `docs/ai/characterisation/load_<date>.txt`. The Odoo
VPS is not involved.

## 7. Backup and rollback

| Data | Where | Backup |
|---|---|---|
| Requests, proposals, jobs (Odoo side), attachments | Odoo database and filestore | existing `backup_db.sh` before installing or updating the module |
| `jobs.db` (job inputs and results, temporary) | AI server, encrypted volume | **never backed up**; purged at `ack` or after 7 days |
| `ledger.db` (financial metadata, idempotency tombstones) | AI server, encrypted volume | daily online backup to an encrypted target, kept 13 months |
| Configuration, prompts, schemas | private Git repository | Git |
| Secrets | AI server and owner's password manager | not in any backup archive of the repo |

IA-2 installation order: AI server healthy with the AI disabled in Odoo → Odoo backup
(manifest) → PLATFORM OK → module installed with `deploy_modules.sh` (unchanged) → tests →
routes inventory compared → enabled for one test user with the fake gateway, then (after
D6) with the real one.

Rollback (rehearsed locally): Odoo setting off → module uninstalled (or `restore_db.sh` if
anything else changed) → AI server stopped → D16 rollback (§4.1). No network, script or
service to undo on the Odoo VPS.

## 8. Preconditions before any deployment

- [ ] plan audited; D1–D16 answered; D6 answered before any real data
- [ ] §1.1 characterisation done (including what creates `odoo_web`); D16 chosen; mount procedure and its rollback rehearsed on a copy
- [ ] PLAN.md §1.3 facts verified on official pages and accounts; placeholders filled
- [ ] provider accounts: DPA, retention / ZDR / region settings, spend limits, scoped keys
- [ ] AI server built and hardened (§2–§4), data disk encrypted; `DOCKER-USER` rules installed; egress tests T-S20–T-S23d passed; `REAL_DATA_ALLOWED=false` until D6
- [ ] images by digest, hashes and LiteLLM signature checked
- [ ] load test (§6) passed
- [ ] Odoo backup with manifest; rollback rehearsed
- [ ] `artdubati_test` only

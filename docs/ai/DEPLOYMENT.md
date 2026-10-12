# AI assistant – deployment and operations (IA-0, revision 2, 12/10/2026)

Revision 2: the AI runs on a **separate server**; the Odoo VPS keeps its networks, scripts
and services unchanged. Nothing is to run before the audit and the owner's go, except the
read-only characterisation of §1.

## 1. Characterisation (read-only, run by the owner)

### 1.1 Odoo VPS — only what the AI needs from it

Output to paste into `docs/ai/characterisation/odoo_vps_<date>.txt` (secrets masked).

```bash
# resources (confirms the 4 GB of the audit; for information)
nproc; free -m; df -h; uptime; docker stats --no-stream

# how odoo_web gets its configuration and secrets (D16)
docker inspect -f '{{range .Mounts}}{{.Type}} {{.Source}} -> {{.Destination}} ({{.Mode}}){{println}}{{end}}' odoo_web
docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' odoo_web | sed -E 's/=.*/=<masked>/'
docker exec odoo_web sh -c 'ls -ld /etc/odoo /etc/odoo/* 2>/dev/null; id'

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
| Size | 2 vCPU, 4 GB RAM, 40 GB disk (API version); a distinct, larger machine if Ollama comes (IA-5) |
| Location | EU data centre of a provider chosen by the owner (the host is a processor too; its DPA in the processing records) |
| OS | a supported LTS distribution, automatic security updates of the OS only (not of the containers), AppArmor enabled |
| Access | SSH by key only, from the owner's addresses; no password login |
| Inbound | the gateway's HTTPS port from the Odoo VPS address only (mTLS); nothing else |
| Outbound | through `ai_egress` for the containers; OS updates for the host |
| Test / production | one gateway per environment (separate ports, keys, CA-issued client certs, budgets, job stores); production only after the separation of `docs/deployment/investor_home.md` §0 |

Initial memory budget on the AI server (to confirm by §6): gateway 300 MB, LiteLLM proxy
1 GB, extractor 1 GB (OCR peaks), egress proxy 100 MB, OS and Docker 0.8 GB → about
3.2 GB of 4 GB.

## 3. Containers and networks

| Container | Image | Networks | Inbound | Egress | Limits (initial) |
|---|---|---|---|---|---|
| `ai_gateway` | own image, pinned base digest, hash-locked deps | `net_front` (published port), `net_llm`, `net_doc` | Odoo VPS only, mTLS | **none** (all networks except `net_front` internal; `net_front` publishes the port only, the container has no outbound rule through the host firewall) | 1 CPU, 384 MB, pids 128 |
| `ai_litellm` | LiteLLM image **by digest**, signature checked | `net_llm`, `net_egress` (both internal) | gateway only | through `ai_egress` only | 1 CPU, 1 GB, pids 256 |
| `ai_extractor` | own image (pypdf / pdfminer, Tesseract fra/eng/fas), pinned | `net_doc` (internal) | gateway only | none | 1 CPU, 1 GB, pids 64 |
| `ai_egress` | forward proxy, pinned digest | `net_egress` (internal), `net_out` (external) | `ai_litellm` only | allow-listed hosts, port 443, CONNECT only | 0.5 CPU, 128 MB |

`net_llm`, `net_doc`, `net_egress` are `internal: true` (no gateway to the outside).
The gateway's published port is the only inbound path; the host firewall drops every
outbound packet from the gateway's bridge except established replies (tested, T-S20).

Hardening for all: non-root user, read-only root fs, size-limited `tmpfs`,
`no-new-privileges`, `cap_drop: ALL`, seccomp (default or tighter), AppArmor profile,
logging driver with rotation, `restart: unless-stopped`, health checks
(`/v1/health` for the gateway; LiteLLM's liveness endpoint on `net_llm`; extractor's own).

Egress proxy allow-list (illustrative; final names from D3 / D6):

```
acl api_hosts dstdomain api.anthropic.com api.openai.com
acl ssl_port port 443
http_access deny !CONNECT
http_access deny CONNECT !ssl_port
http_access allow CONNECT api_hosts
http_access deny all
```

IP-literal requests are refused by the `dstdomain` list (no IP entry).

## 4. Secrets on each side

| Side | Files | Note |
|---|---|---|
| AI server | `/opt/ai/secrets/{anthropic,openai}_key` → `ai_litellm` only; `litellm_client_key` → gateway and LiteLLM; `hmac_keys`, TLS server key and cert, CA cert → gateway | directory 0700 root; mounted as Docker secrets (files, 0400) |
| Odoo VPS | Odoo client key and cert, CA cert, current HMAC key | D16: (a) in the host directory already mounted as `/etc/odoo` if §1.1 shows one (restart only); (b) a new read-only bind mount (container recreated in a planned window with the usual backup). Path given in `odoo.conf` (`ai_gateway_secrets_dir`), never the content |

The owner keeps a copy in a password manager; secrets never in Git, in the Odoo database,
in environment variables, or in backups of this repository.

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
- **Daily reconciliation**: ledger vs provider usage; reservations of `outcome_unknown`
  jobs settled from the provider's usage report.

## 6. Load and memory test (IA-1, before any deployment)

On the AI server, fake provider, synthetic documents: 5 concurrent `extract_document` jobs
with a 50-page text PDF and a 10-page scan, 30 minutes; `docker stats` every 5 s; pass if
no container exceeds its limit, no OOM kill, host available memory ≥ 500 MB. Result in
`docs/ai/characterisation/load_<date>.txt`. The Odoo VPS is not involved.

## 7. Backup and rollback

| Data | Where | Backup |
|---|---|---|
| Requests, proposals, jobs (Odoo side), attachments | Odoo database and filestore | existing `backup_db.sh` before installing or updating the module |
| Job store and ledger | AI server, SQLite volume | daily copy (online backup API), 13 months for the ledger |
| Configuration, prompts, schemas | private Git repository | Git |
| Secrets | AI server and owner's password manager | not in any backup archive of the repo |

IA-2 installation order: AI server healthy with the AI disabled in Odoo → Odoo backup
(manifest) → PLATFORM OK → module installed with `deploy_modules.sh` (unchanged) → tests →
routes inventory compared → enabled for one test user with the fake gateway, then (after
D6) with the real one.

Rollback (rehearsed locally): Odoo setting off → module uninstalled (or `restore_db.sh` if
anything else changed) → AI server stopped; the Odoo VPS has nothing else to undo (no
network, script or service change), except removing the secret files of D16.

## 8. Preconditions before any deployment

- [ ] plan audited; D1–D16 answered; D6 answered before any real data
- [ ] §1.1 characterisation done; D16 chosen
- [ ] PLAN.md §1.3 facts verified on official pages and accounts; placeholders filled
- [ ] provider accounts: DPA, retention / ZDR / region settings, spend limits, scoped keys
- [ ] AI server built and hardened (§2–§4); egress tests T-S20–T-S23 passed
- [ ] images by digest, hashes and LiteLLM signature checked
- [ ] load test (§6) passed
- [ ] Odoo backup with manifest; rollback rehearsed
- [ ] `artdubati_test` only

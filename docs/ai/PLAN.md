# AI assistant – plan IA-0 (revision 3, 12/10/2026, no code, nothing installed)

Owner's mission of 12/10/2026: an assistant that understands a business need written in
natural language and **prepares** what Odoo needs (supplier, item or service, contract,
receipt, bill, supporting documents), hiding the Odoo model, **without** letting the AI
take accounting decisions or write freely to the database.

Revision 2 answers the audit of ebe35ac (§9): asynchronous jobs instead of a cron waiting
on the AI; two calls per normal request instead of six or seven; a separate server;
a designed egress proxy; a local confidentiality pre-check before any call; IA-3 limited
to the circuits that exist; models, prices and provider policies kept as placeholders
until verified on the official pages and accounts; LiteLLM in its own process, apart from
the gateway's secrets; a hardened extractor.

Revision 3 answers the audit of c9e5427, limited to its four blocking points and its
complements (§10): `jobs.db` (temporary, never backed up) separated from `ledger.db`
(financial metadata, backed up) on an encrypted disk; 4 vCPU / 8 GB with explicit worker
concurrency; egress filtering in Docker's `DOCKER-USER` chain with a proxy that resolves
names and refuses private and metadata addresses; `ack` only after Odoo's commit.

This is still a plan for audit. No module, container, key or API call is created by it.
Development starts only after the owner's answers to §6 and the auditor's green light.

| Document | Content |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | components, job API, Odoo module, deterministic steps vs AI calls, document chain, routing |
| [SECURITY.md](SECURITY.md) | trust boundaries, confidentiality pre-check, mTLS + HMAC, egress proxy, isolation, logging, tests |
| [SCHEMAS.md](SCHEMAS.md) | the stable contract: jobs, three AI functions, limits, uncertainty, idempotency |
| [DEPLOYMENT.md](DEPLOYMENT.md) | characterisation (read-only), separate server, containers, secrets, operations, rollback |
| [COSTS.md](COSTS.md) | token estimates, cost formula, illustrative ranges (not a budget basis), caps and ledger |

## 0. Rules carried by every AI phase

1. **Independence.** Module `lartdubati_ai_assistant`, not mixed into
   `maintenance_shareholder_equipment` nor `lartdubati_investor_home`; no existing module
   depends on it. Every existing circuit works unchanged when the AI is disabled,
   unreachable, out of budget or uninstalled.
2. **No new service and no new network on the Odoo VPS**, no change to
   `docs/deploy_modules.sh` or the other window scripts (D1). Besides the module, the only
   change there is the delivery of its secrets (D16): with option (b), `odoo_web` is
   recreated once with one more read-only mount, with a recorded definition, checks and a
   rollback (DEPLOYMENT.md §4.1).
3. **The AI proposes, Odoo decides.** The model never chooses an account, a tax, a partner,
   a product, a category, a periodicity or a date absent from the inputs, nor a
   capitalisation decision. It answers « unknown » or picks among a list Odoo sent.
4. **AI only where determinism cannot do the job**: understanding the free text,
   extracting a document, settling a real ambiguity among Odoo's candidates. Searches,
   duplicate checks, missing-information questions and the mapping to drafts are Odoo code
   (ARCHITECTURE.md §3).
5. **No final write by the AI.** Odoo creates drafts only in circuits that exist and only
   as a user who has the right to create them; never `sudo()` to bypass rights; nothing
   submitted, approved, executed, posted or paid by the assistant.
6. **Confidentiality decided locally before any external call** (SECURITY.md §4); until D6
   is answered, external profiles receive **synthetic data only**.
7. Odoo knows only functional profiles (`fast`, `document`, `reasoning`, `local`,
   `fallback`), never a provider or model name.
8. Strict contract: a gateway answer that fails its JSON schema is refused, never repaired.
9. Documents are untrusted data; nothing in them can change instructions or rules.
10. No paid API in automated tests; real calls only in capped acceptance runs.
11. Project rules unchanged: standard first, inheritance, no raw SQL writes,
    `artdubati_test` only, « (excl. tax) » on cost labels, `.po` from `--i18n-export`,
    routes inventory (`docs/phase4/routes.py`): the module adds **no** HTTP route;
    investors refused by the phase 4 default deny (tested).
12. Each phase IA-1 … IA-5 has its own plan, audit and deployment; test and production
    use separate gateways, keys and budgets (`docs/deployment/investor_home.md` §0).

## 1. Characterisation (state on 12/10/2026)

**Verified** = read in this repository or in an official page actually opened;
**secondary** = search results, to confirm; **to verify** = on the owner's accounts or
the official pages (refused by this session's network: `platform.openai.com`,
`docs.litellm.ai`, `privacy.claude.com`, `docs.ollama.com`); **to run** = read-only
commands of DEPLOYMENT.md §1, by the owner.

### 1.1 Odoo server (what matters now that the AI runs elsewhere)

| Item | Known | To run |
|---|---|---|
| Image, modules | `sha256:706e891a…` (18.0-20260908), 122 modules (verified, `docs/phase4/platform_expected.txt`) | – |
| Resources | 4 GB according to the audit; not measured | `free -m`, `nproc`, `df -h`, load over a working day |
| Docker network | `odoo_web` on **exactly one** network, required by `docs/deploy_modules.sh` (verified); **unchanged by this plan** | – |
| Secrets today | database credentials are container environment variables (verified: `deploy_modules.sh` copies `docker inspect … .Config.Env`) | how they are set; whether `/etc/odoo` is a host bind mount (D16) |
| Outbound from `odoo_web` | likely (mail through `google_gmail`), not measured | reachability of the AI server's address and port |

The memory figures of revision 1 no longer apply to the Odoo VPS. They size the AI
server (DEPLOYMENT.md §2).

### 1.2 Software

| Item | State |
|---|---|
| LiteLLM licence | **verified**: MIT except `enterprise/` (not used) |
| LiteLLM versions | secondary: releases about twice a week (v1.104–1.105 in October 2026). Version, image digest and signature **to verify** in IA-1 |
| LiteLLM supply chain | secondary, concordant: malicious 1.82.7 and 1.82.8 on PyPI (24/03/2026); images cosign-signed since about v1.83.14 |
| LiteLLM proxy admin UI and database | to verify: the proxy can run from a config file without database; how to disable its UI / admin routes in the pinned version |
| FastAPI | secondary: 0.136.x, MIT, pre-1.0 (exact pin) |
| Provider structured outputs | OpenAI: `json_schema` with `strict`, refusals and truncations not schema-valid (OpenAI guide). Anthropic: `output_config.format`, `stop_reason: "refusal"` (Anthropic API reference). Through LiteLLM: **to verify** (H-AI-1) |
| Ollama | secondary: OpenAI-compatible `/v1`, JSON-schema outputs since 0.5; licence to verify |

### 1.3 Providers: models, prices, data policies — **placeholders**

Revision 1 quoted Anthropic model identifiers and prices from a price table bundled with
the development tooling (dated 06/10/2026), not from a page opened in the session, and
OpenAI figures from third-party lists. The audit is right: none of it may support a
decision. They become placeholders `<MODEL_FAST>`, `<PRICE_IN_FAST>`… filled only from:

| Fact | Source required | Who |
|---|---|---|
| model identifiers, availability, deprecation dates | provider's official models page **and** the models list of the owner's own account | owner, before IA-1 acceptance |
| prices per token, region uplifts | official pricing pages, captured with date | owner / Claude from the captured pages |
| retention, ZDR, training, sub-processors | DPA and data-usage pages; the organisation's settings in each console | owner (legal) |
| processing regions | official data-residency pages; account settings | owner (legal) |

Secondary indications kept only to frame D6 (to confirm): Anthropic's first-party API
offers `inference_geo` = `us` or `global`, no EU-only option; OpenAI offers EU residency
for new projects after approval, with a price uplift; both state that API data is not used
for training by default and offer zero retention on approval.

### 1.4 What could not be verified

The server rows above, the official provider pages, the owner's accounts, and LiteLLM's
behaviour with each provider (H-AI-1). Nothing is assumed from them.

## 2. Target experience (RC Pro at AXA) with the calls actually made

« Je veux enregistrer une assurance RC professionnelle chez AXA, 1 800 € par an, à partir
du 1er janvier. Voici le contrat. »

| Step | Who | What | AI call |
|---|---|---|---|
| 1 | Odoo, locally | confidentiality pre-check of the text and of the file's type; refused or local-only if sensitive data is detected | – |
| 2 | gateway | `interpret_request`: intent among Odoo's list (recurring service), nature (insurance), search keys (« AXA », « RC professionnelle »), amount and date terms with their position in the text | **1** |
| 3 | Odoo | searches partners, products, categories and running contracts with the user's rights; duplicate checks with the existing canonical keys | – |
| 4 | Odoo | configuration check: is there an allowed product category for insurance services? Today: **no** (nomenclature waits for C25) → status `missing_configuration`, reason shown; the flow stops there for the creation part, extraction still possible for information | – |
| 5 | AI server | extractor (own server, no external call) + second pre-check on the extracted text | – |
| 6 | gateway | `extract_document` with the fields Odoo asks for this intent and document kind (insurer, policy, cover, premium, tax basis, periodicity, dates, notice) with page and excerpt | **2** |
| 7 | Odoo | missing fields and contradictions computed from the circuit's required fields (e.g. « 1 650 € excl. tax in the document, 1 800 € in your message ») → questions from translated templates | – |
| 8 | gateway, only if needed | `resolve_ambiguity` when Odoo's matching leaves two or more plausible candidates (e.g. « AXA France IARD » and « AXA Assistance ») | (3) |
| 9 | Odoo | summary with evidence; proposal stored on the request | – |
| 10 | user | accepts, corrects or refuses; for an existing circuit and with the right to create in it, Odoo creates the **draft**; otherwise the structured proposal stays on the request (§3) | – |

Normal request: **2 calls** (1 without a document), 3 with a real ambiguity.

## 3. Circuits that exist and those that do not

| Need | Circuit in Odoo today | What the assistant does (IA-3) |
|---|---|---|
| new item or service | `product.creation.request` (draft creatable by Equipment Operator, Purchase / User, Inventory / User, Product Catalogue Manager: `security/ir.model.access.csv`) | draft request, if the user is in one of these groups **and** an allowed category exists; else structured proposal, reason shown |
| receipt of equipment or consumables | `equipment.operation` (Equipment Operator) | draft operation for an existing product and partner, if the user is an Equipment Operator; else structured proposal |
| new supplier | **none** (no controlled partner creation circuit) | structured proposal only (« supplier to create by an authorised person »); no `res.partner` created |
| recurring contract (insurance, subscriptions) | **none** (ROADMAP A not developed) | structured proposal only; no OCA `contract` created |
| bill | standard supplier bill, outside the assistant's scope | none: the assistant never creates a bill |
| no valid category for the need | – | `missing_configuration` with what is missing (e.g. insurance categories, C25) |

A structured proposal is a record of the AI request (lines with values, evidence and
status), readable and exportable; it becomes a draft only when its circuit exists, after
that circuit's own audited development. Rights are checked with the target model's
`check_access('create')` as the user before showing « Prepare draft »; never `sudo()`.

## 4. Phases

| Phase | Content | Writes in Odoo | Real API | Exit criteria |
|---|---|---|---|---|
| **IA-0** | this plan, decisions §6 | none | none | audit passed, decisions answered |
| **IA-1** | AI server alone: gateway (API + worker, `jobs.db` / `ledger.db`), LiteLLM proxy, extractor, egress proxy, **fake provider and synthetic data only**; memory and egress tests | none (no Odoo) | **none** | SECURITY.md §12 tests green (except T-S01b); egress proof; memory measured at the configured concurrency; digests recorded |
| **IA-1b** | capped acceptance run on real models with synthetic documents (adversarial ones included, T-S01b), token measurement | none | yes, capped, synthetic only | only after D3, D4 (identifiers and prices verified, §1.3) and D6 |
| **IA-2** | module, read-only assistant: pre-check, interpretation, Odoo searches, extraction, questions, proposal; kill switch; cost display | only its own models | yes, **only after D6**; before D6 the module is tested with the fake gateway only | no other model written (test); investor refused; disabled / down modes tested |
| **IA-3** | drafts in `product.creation.request` and `equipment.operation` only, as the user, with their checks; structured proposals for the rest | drafts only | yes | each draft passes the same checks as a manual one; user without rights gets the proposal, not a draft; config change between proposal and draft refused |
| **IA-4** | after the circuits' own approvals, Odoo tracks and links the executions; new circuits (supplier, ROADMAP A) are plugged in only after their own development | through existing methods | yes | no execution without the circuit's approval |
| **IA-5** | `local` profile (Ollama) on a separate, larger machine | unchanged | local | no Odoo module change needed |

## 5. Reference scenarios and tests

Reference scenarios S1–S17 of the mission, each with a synthetic input, a recorded fake
answer and the expected Odoo outcome; expected calls in brackets.

| # | Scenario | Expected outcome |
|---|---|---|
| S1 | RC professionnelle [2] | partner and contract search; `missing_configuration` (no insurance category yet); proposal with extracted values |
| S2 | Décennale tied to an installation [2] | question « which worksite / installation? » (template); company cover, never linked to an equipment; proposal only |
| S3 | Internet + phone [1–2] | « Abonnement téléphonique » found by search; internet product: draft creation request if a category is allowed |
| S4 | ChatGPT subscription [1] | category « to confirm with the accountant » (C25): `missing_configuration` or proposal; no contract (ROADMAP A) |
| S5 | Warehouse insurance [2] | stock location chosen by the user from Odoo's list; proposal only |
| S6, S7 | Van, trailer [2] | category's configured treatment shown, no capitalisation decision; Fleet out of scope |
| S8 | Tiles and consumables [1–2] | creation requests or receipt draft (consumables branch) |
| S9 | Workwear [1] | allowed category or `missing_configuration` |
| S10, S11 | Equipment capitalised / expensed [2] | treatment from the category; draft receipt for an existing product |
| S12 | Rented or borrowed [2] | ownership status and owner asked if absent; receipt draft in the matching branch |
| S13 | Supplier consignment [1] | « not supported yet » (ROADMAP 0 item 7) |
| S14 | Product exists [1] | existing product first; no creation request (duplicate guard) |
| S15 | Supplier absent [1–2] | structured proposal « supplier to create »; nothing created |
| S16 | Bill before contract [2] | no bill created; missing contract flagged (proposal) |
| S17 | Contradictory / incomplete document [2–3] | contradictions with both excerpts; `needs_information`; no value chosen |

Security tests: SECURITY.md §12 (pre-check, jobs, egress, injection, schema, budget,
rights, company, logs, fallback, config change). Automated ones never call a paid API;
the adversarial acceptance run is capped and uses synthetic documents only.

## 6. Decisions (audit recommendation → owner to confirm)

| # | Decision | Proposal of revision 2 |
|---|---|---|
| D1 | Hosting | **separate server, 4 vCPU / 8 GB** (audit of c9e5427) for gateway, LiteLLM, extractor and egress proxy, data disk encrypted; worker concurrency 5 jobs, 3 extractions, 2 OCR; 2 vCPU / 4 GB only with 1 extraction and 1 OCR at a time; nothing installed on the Odoo VPS; a distinct, larger machine if Ollama comes (IA-5) |
| D2 | Odoo ↔ gateway | **mTLS** (client certificate for Odoo, server certificate of a private CA, firewall allowing only the Odoo VPS address) **+ HMAC + idempotency**. Preferred to WireGuard because it needs no interface or firewall change on the Odoo host; WireGuard remains the alternative if the owner prefers a tunnel |
| D3 | Providers | direct contracts (Anthropic, OpenAI), no OpenRouter |
| D4 | Models per profile | **none chosen** before official verification (§1.3); then one pinned identifier per profile |
| D5 | Retention | metadata and validated proposals (short excerpts); never full prompts |
| D6 | Region / legal basis | **owner / legal decision before any real data leaves the company**; until then synthetic data only |
| D7 | OCR | local (Tesseract fra, eng, fas) in the extractor; provider vision refused |
| D8 | Odoo model | request + child models |
| D9 | Acceptance | the user prepares; the existing circuits' approvers approve; draft only if the user may create in that circuit |
| D10 | Fallbacks | only routes whose **data policy** is equal or stricter on each attribute (SECURITY.md §6), listed explicitly by the owner; none across providers until both routes' policies are approved |
| D11 | Cost limits | 50 € / month, 0.50 € / request, override after confirmation (AI Budget Manager), hard stop |
| D12 | Local pre-check | mandatory, deterministic, before any external call (SECURITY.md §4) |
| D13 | LiteLLM | **separate process and container**, holding provider keys only, reachable only by the gateway, no UI, no database |
| D14 | Antivirus | ClamAV postponed **only** with the hardened extractor (SECURITY.md §8) and synthetic data in IA-1 |
| D15 | Call mode | **asynchronous jobs**: `POST /v1/jobs` → 202, gateway worker, `GET /v1/jobs/{id}` |
| D16 | Delivery of Odoo's client certificate and HMAC key to `odoo_web` | **(b)** read-only bind mount at the fixed path `/run/secrets/lartdubati_ai/`, `odoo_web` recreated once with recorded definition, checks and rollback (DEPLOYMENT.md §4.1); (a) only if `/etc/odoo` is already a host directory (then one non-sensitive path line in `odoo.conf`). Never a secret in `odoo.conf`, the database, Git or environment variables |

## 7. Open hypotheses

- H-AI-1: LiteLLM proxy passes each provider's structured-output and region parameters
  unchanged, and can run without UI, database, retries or fallbacks (IA-1).
- H-AI-2: `odoo_web` can reach the AI server's port without a change on the Odoo host
  (characterisation).
- H-AI-3: a 4 vCPU / 8 GB server holds the four containers at the configured concurrency
  under the load test (DEPLOYMENT.md §6).
- H-AI-4: provider settings (retention, ZDR, region) available on the owner's accounts.
- H-AI-5: token estimates of COSTS.md §2, measured in the acceptance run.
- H-AI-6: on the pinned Docker version, the embedded DNS of containers on internal
  networks does not resolve Internet names; otherwise containers get a non-forwarding
  `dns:` setting (SECURITY.md §7, T-S21).
- H-AI-7: each provider's usage data can be matched to an individual request (request
  id), which decides whether `outcome_unknown` can be settled exactly (COSTS.md §4).

## 8. Accounting

The assistant takes no accounting decision and creates no accounting question by itself:
it shows the treatment Odoo's configuration gives (categories, profiles, C1–C25) or
`missing_configuration`. Provider bills go through the existing supplier bill circuit
(software / SaaS, C25).

## 9. Answers to the audit of ebe35ac

| # | Point | Answer | Where |
|---|---|---|---|
| 1 | Cron waiting on the AI; timeout may cause a second paid call | **Fixed**: job API (202, worker, polling), atomic job + reservation + idempotency in one transaction; a timeout no longer exists on the Odoo side; a lost or interrupted provider call is `outcome_unknown`, never retried automatically | ARCHITECTURE.md §2, §5; SCHEMAS.md §2 |
| 2 | Too many AI calls | **Fixed**: three functions left (`interpret_request`, `extract_document`, `resolve_ambiguity`); searches, duplicates, missing information and draft mapping are Odoo code; 2 calls per normal request | ARCHITECTURE.md §3; SCHEMAS.md §3 |
| 3 | Do not use the Odoo VPS | **Fixed**: separate server, no network or script change on the Odoo VPS; the revision 1 network finding stays as a fact, no longer as a plan | §0.2, D1; DEPLOYMENT.md §2 |
| 4 | Egress not designed | **Fixed**: egress proxy (CONNECT allow-list, no TLS interception), containers without a route to the Internet, tests that any other host or IP fails | SECURITY.md §7; DEPLOYMENT.md §3 |
| 5 | Confidentiality decided too late | **Fixed**: deterministic pre-check in Odoo before submission and again in the gateway on extracted text; level can be raised, never lowered; unclassifiable → blocked; D6 before real data | SECURITY.md §4 |
| 6 | Circuits that do not exist | **Fixed**: drafts only in `product.creation.request` and `equipment.operation`; structured proposals for supplier and contract; `missing_configuration` | §3 |
| 7 | Models, prices, policies not verified | **Agreed**: identifiers and prices are placeholders; COSTS.md gives token estimates and a formula, not a budget | §1.3; COSTS.md |
| 8 | LiteLLM inside the gateway widens a compromise | **Agreed**: three processes (gateway with the HMAC key, LiteLLM with provider keys only, extractor without secret nor egress) | ARCHITECTURE.md §1; SECURITY.md §3 |
| s1 | ClamAV vs isolation | **Fixed**: per-document disposable child process, seccomp + AppArmor, rlimits, decompression-bomb limits, no shared volume | SECURITY.md §8 |
| s2 | Injection test with a fake provider proves only validation | **Agreed**: capped acceptance run with synthetic adversarial documents on the real models; both results reported | SECURITY.md §12, T-S01b |
| s3 | Jurisdiction compatibility of fallbacks | **Fixed**: data-policy attributes per route, « equal or stricter » rule, owner's explicit list | SECURITY.md §6 |
| s4 | Rights to create each draft | **Fixed**: `check_access('create')` as the user; no rights → proposal only | §3; ARCHITECTURE.md §4 |
| s5 | Reservation, idempotency, job state atomic | **Fixed**: one SQLite transaction (`BEGIN IMMEDIATE`) | ARCHITECTURE.md §5 |
| s6 | Budget in the billing currency | **Fixed**: ledger keeps provider currency amount, rate and its date, EUR equivalent | COSTS.md §4 |


## 10. Answers to the audit of c9e5427

| # | Point | Answer | Where |
|---|---|---|---|
| 1 | One SQLite file both purged (results) and backed up 13 months (ledger) | **Fixed**: `jobs.db` (inputs and results, never backed up, purged at `ack` or 7 days, `secure_delete`, `VACUUM`) and `ledger.db` (financial metadata and idempotency tombstones only, backed up 13 months); atomic transactions across both through `ATTACH` in rollback-journal mode; AI server's data disk, swap and backup target encrypted | ARCHITECTURE.md §5.1; SECURITY.md §11; DEPLOYMENT.md §2, §7; T-S30–T-S32 |
| 2 | 4 GB too tight for 5 concurrent jobs with OCR | **Fixed**: 4 vCPU / 8 GB recommended; explicit semaphores (5 jobs, 3 extractions, 2 OCR, 5 LLM calls) in the worker and in the extractor; 4 GB only with 1 extraction and 1 OCR; load test at the configured concurrency | ARCHITECTURE.md §5.2; DEPLOYMENT.md §2, §6; T-S34 |
| 3 | Filtering must cover Docker's own chains | **Fixed**: `DOCKER-USER` default deny for the AI subnets, outbound only from the proxy (443, DNS to fixed resolvers), inbound only from the Odoo VPS, `userland-proxy: false`, rules re-applied and checked daily; proxy with source ACL, DNS by the proxy, refusal of private, loopback, link-local, CGNAT and metadata addresses after resolution; tests that gateway and LiteLLM cannot bypass it | SECURITY.md §7; DEPLOYMENT.md §3; T-S20–T-S23d |
| 4 | `ack` before Odoo's commit loses results | **Fixed**: GET → validate → store → commit → `ack`; `ack` idempotent (204); purged key answers `410` without a new call | ARCHITECTURE.md §2; SCHEMAS.md §1; T-S33 |
| c1 | « Infrastructure unchanged » too absolute | **Fixed**: « no new service nor network »; D16 (b) recreation documented with recorded definition, checks and rollback | §0.2; DEPLOYMENT.md §4.1 |
| c2 | Fixed path, no secret in `odoo.conf` | **Fixed**: `/run/secrets/lartdubati_ai/`; `odoo.conf` holds nothing (b) or only a path (a) | SECURITY.md §3; DEPLOYMENT.md §4 |
| c3 | Scripts recreating the container keep the mount | **Checked**: no script of this repository recreates `odoo_web`; the one-shot containers (`--volumes-from`) inherit the mount read-only and `backup_db.sh` archives only the filestore; what creates `odoo_web` is characterised (§1.1 of DEPLOYMENT.md) and is the only place to carry the mount; post-check of the module verifies it | DEPLOYMENT.md §1.1, §4.1 |
| c4 | Calls with `missing_configuration` inconsistent | **Fixed**: 1 call without document, 2 with (extraction kept for the structured proposal, S1) | COSTS.md §1; T-S29 |
| c5 | Exact reconciliation of `outcome_unknown` | **Fixed**: exact only if the provider's usage identifies the request (H-AI-7); otherwise reservation kept and traced manual correction | COSTS.md §4 |
| c6 | No real data before D6 | **Confirmed**: `REAL_DATA_ALLOWED=false` on the AI server until D6, checked at job creation (T-S27); IA-1 with fake provider and synthetic data only; real calls (IA-1b) after D3, D4, D6 | §4; ARCHITECTURE.md §5.1 |

## Sources

- LiteLLM licence: [LICENSE](https://github.com/BerriAI/litellm/blob/main/LICENSE); releases: [release notes](https://docs.litellm.ai/release_notes/); incident: [LiteLLM](https://docs.litellm.ai/blog/security-update-march-2026), [Bitsight](https://www.bitsight.com/blog/litellm-versions-1-82-7-1-82-8-supply-chain-compromise), [NetSPI](https://www.netspi.com/blog/executive-blog/ai-ml-pentesting/litellm-supply-chain-compromise/); signed images: [v1.83.14-stable](https://newreleases.io/project/github/BerriAI/litellm/release/v1.83.14-stable)
- FastAPI: [pepy.tech](https://pepy.tech/projects/fastapi)
- OpenAI: [EU data residency](https://openai.com/index/introducing-data-residency-in-europe/), [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs.md)
- Anthropic: [data residency](https://platform.claude.com/docs/en/manage-claude/data-residency), [ZDR scope](https://privacy.claude.com/en/articles/8956058-i-have-a-zero-data-retention-agreement-with-anthropic-what-products-does-it-apply-to)
- Ollama: [structured outputs](https://registry.ollama.ai/blog/structured-outputs)

# AI assistant – plan IA-0 (revision 1, 12/10/2026, no code, nothing installed)

Owner's mission of 12/10/2026: an assistant that understands a business need written in
natural language and **prepares** the Odoo objects it needs (supplier, item or service,
contract, receipt, bill, supporting documents), hiding the Odoo model, **without** letting
the AI take accounting decisions or write freely to the database.

This revision is the IA-0 deliverable: plan, architecture, threat model, schemas,
deployment and costs. It is to be audited (GPT) and the decisions of §6 answered by the
owner before any development. No module, container, key or API call is created by it.

Companion documents:

| Document | Content |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | components, flows, Odoo module, gateway pipeline, routing, document chain, AI / Odoo split |
| [SECURITY.md](SECURITY.md) | assets, trust boundaries, threat model, controls, logging, retention, security tests |
| [SCHEMAS.md](SCHEMAS.md) | the stable Odoo ↔ gateway contract: envelope, seven functions, limits, uncertainty |
| [DEPLOYMENT.md](DEPLOYMENT.md) | server characterisation (commands), hosting options, containers, secrets, rollback, kill switch |
| [COSTS.md](COSTS.md) | prices, estimates per function, monthly scenarios, caps and measurement |

## 0. Rules carried by every AI phase

1. **Independence.** New module `lartdubati_ai_assistant`, not mixed into
   `maintenance_shareholder_equipment` (catalogue, operations) nor into
   `lartdubati_investor_home`. Every existing circuit works unchanged when the AI is
   disabled, unreachable, out of budget or uninstalled; no existing module depends on it
   (ARCHITECTURE.md §2).
2. **The AI proposes, Odoo decides.** The model never chooses an account, a tax, a
   partner, a product, a category, a periodicity or date absent from the document, nor a
   capitalisation decision. It may only pick from a list Odoo sends, with a justification
   and a confidence, or answer « unknown » (ARCHITECTURE.md §7, SCHEMAS.md §3).
3. **No final write by the AI.** Only Odoo creates records, through the existing business
   methods and approval circuits (`product.creation.request`, `equipment.operation`, the
   recurring-contract document of ROADMAP A when it exists), as the user, never with
   `sudo()` to bypass rights. Nothing is posted, paid, approved or executed automatically.
4. **Odoo only knows functional profiles** (`fast`, `document`, `reasoning`, `local`,
   `fallback`), never a provider or model name.
5. **Strict contract.** Every gateway answer is validated against a versioned JSON schema;
   a non-conforming answer is refused, never repaired or interpreted.
6. **Documents are untrusted data.** No text from a document can change instructions,
   call a tool or bypass a rule (SECURITY.md §4).
7. **No paid API in automated tests.** Fake provider and recorded answers only; real calls
   only in an explicit, capped acceptance run (SECURITY.md §9, COSTS.md §6).
8. Project rules unchanged: standard Odoo / OCA first, inheritance, no raw SQL writes,
   `artdubati_test` only, `« (excl. tax) »` on every cost label, translations from
   `--i18n-export`, inventory of HTTP routes for each module installed
   (`docs/phase4/routes.py`); the new module adds **no** HTTP route (SECURITY.md §6).
   Investor accounts never see the assistant (default deny of phase 4, tested).
9. Each phase IA-1 … IA-5 has its own plan, audit and deployment.
10. The test / production separation of `docs/deployment/investor_home.md` §0 applies to
    the gateway too: separate instances, keys and budgets for test and production.

## 1. Characterisation (state on 12/10/2026)

What follows distinguishes **verified** (read in the repository or in an official source),
**secondary** (third-party sources, to confirm on the official page before a decision) and
**to run on the server** (read-only commands of DEPLOYMENT.md §1, run by the owner; no
access to the VPS from this session).

### 1.1 Server (to run on the server)

| Item | Known | To measure (DEPLOYMENT.md §1) |
|---|---|---|
| Odoo image | `sha256:706e891a…` (Odoo Server 18.0-20260908), 122 modules (docs/phase4/platform_expected.txt) | – |
| Containers | `odoo_web`, `odoo_db` (CLAUDE.md, deployment scripts) | full list, restart policies, compose project if any |
| RAM, CPU, disk, load | **unknown** | `free -m`, `nproc`, `lscpu`, `df -h`, `uptime`, `vmstat 5 12`, `docker stats --no-stream`, peak over a working day |
| Odoo workers | **unknown** | `workers`, `limit_memory_*`, `limit_time_real_cron`, `max_cron_threads` in the configuration |
| Docker network | `odoo_web` is on **exactly one** network: `docs/deploy_modules.sh` refuses to run otherwise and uses that network to reach `odoo_db` | network name, driver, `internal` flag, other members, published ports |
| Secrets | the database credentials of `odoo_web` are **environment variables of the container** (`deploy_modules.sh` copies `docker inspect … .Config.Env` into a temporary env-file) | how they are set (compose `.env`, `docker run -e`), who can read them, presence of an `odoo.conf` with `admin_passwd` |
| Outbound network | unknown | firewall egress rules, DNS |
| Reverse proxy / TLS | `https://erp.lartdubati.com` | proxy software, whether it could expose a new service by mistake |

Consequence already established: **joining `odoo_web` to a second Docker network breaks
`docs/deploy_modules.sh`** (and the one-shot `docs/roadmap0/finish_window.sh`,
`run_migration.sh`), which require exactly one network to reach `odoo_db`;
`backup_db.sh` and `restore_db.sh` do not read the networks.
Every hosting option of DEPLOYMENT.md §2 states how it handles this (script change in
the IA-2 deployment, or no second network).

### 1.2 Memory impact (estimates, to measure in IA-1)

| Component | Estimate at rest | Peak | Basis |
|---|---|---|---|
| Gateway (FastAPI, uvicorn, 1 worker, LiteLLM as a library) | 150–400 MB | +100 MB per concurrent call | LiteLLM imports many SDKs; to measure |
| LiteLLM proxy as its own container (option) | 0.5–1 GB | secondary guides recommend 4 GB per worker / 8 GB node for production volumes | secondary, conflicting |
| Document extractor (pypdf / pdfminer) | 50–150 MB | 300 MB on large PDFs | to measure |
| OCR (Tesseract / OCRmyPDF) | 0 at rest (one-shot) | 300–800 MB per page batch | to measure |
| Antivirus (ClamAV, optional) | 1–1.5 GB (signatures in memory) | +200 MB | known order of magnitude, to measure |
| Ollama with a 7–8 B quantised model (IA-5) | 5–8 GB | CPU-only inference: tens of seconds per answer | out of scope until IA-5 |

IA-1 includes a memory load test (DEPLOYMENT.md §6); no deployment without it.

### 1.3 Software (verified / secondary)

| Item | State | Source |
|---|---|---|
| LiteLLM licence | **verified**: MIT, except the `enterprise/` directory (own licence; not used) | repository LICENSE |
| LiteLLM version | secondary: stable releases about twice a week, around v1.104–1.105 in October 2026; exact version and image digest pinned in IA-1 from PyPI / GHCR | release notes, GHCR listing |
| LiteLLM supply chain | secondary, concordant: **versions 1.82.7 and 1.82.8 published on PyPI on 24/03/2026 were malicious** (credential theft, `.pth` file run at every Python start); removed since. Docker images are cosign-signed since about v1.83.14. Consequence: pinned digest, hash-locked dependencies, signature checked, never an automatic upgrade (SECURITY.md §7) | LiteLLM security blog, Bitsight, NetSPI |
| FastAPI | secondary: 0.136.x (May 2026), MIT; still pre-1.0, so minor versions may break: exact pin | PyPI mirrors |
| OpenAI API | structured outputs with `json_schema` and `strict: true`; a refusal or a truncated answer is **not** schema-valid even in strict mode, so the gateway validates anyway | OpenAI structured outputs guide |
| Anthropic API | structured outputs through `output_config.format`; `stop_reason: "refusal"` to handle; `inference_geo` (`"us"` or `"global"`) on first-party API, US-only at ×1.1 | Anthropic platform docs (data residency), Claude API reference |
| Ollama | secondary: OpenAI-compatible `/v1` endpoint, JSON-schema structured outputs since 0.5; licence MIT to confirm | Ollama blog |
| LiteLLM ↔ providers | LiteLLM speaks the native OpenAI, Anthropic and Ollama APIs. **Hypothesis H-AI-1** (IA-1, fake provider then one capped real call): LiteLLM passes the JSON schema to each provider in its native form and passes `inference_geo` through; otherwise the gateway calls with provider-specific parameters | to verify |

### 1.4 Provider data policies (secondary unless stated, to confirm on the DPA / data pages before D3 and D6)

| | OpenAI API | Anthropic API (first party) | Ollama (local) |
|---|---|---|---|
| Training on API data | not by default | not by default (commercial terms) | none (local) |
| Default retention | abuse-monitoring logs up to 30 days; `store` must be `false` on Responses / Chat Completions | 7 days since 14/09/2025 per several secondary sources; older pages say 30 days; some models (e.g. Claude Fable 5.1) **require** 30-day retention | none |
| Zero data retention | on approval (sales); some endpoints not eligible (files, batches, vector stores, assistants…) | on approval (sales); safety classifier results still kept | n/a |
| Location | EU data residency (`eu.api.openai.com`) only for **new** projects, after approval of modified abuse monitoring, with a price uplift (~10 % on recent models) | **no EU-only processing on the first-party API**: `inference_geo` = `us` or `global`; EU processing only through cloud resellers (Bedrock, Vertex), excluded by the mission (« called directly ») | the server's |
| DPA | yes (with SCCs) | yes, in the commercial terms (with SCCs) | n/a |

Consequence for D6: with direct calls, **no provider gives EU-only processing without an
approval process** (OpenAI) or at all (Anthropic). This is an owner decision, not a
technical detail.

### 1.5 What could not be verified from this session

- the whole server column of §1.1 (no VPS access; commands in DEPLOYMENT.md §1);
- official provider pages (the session's network refused `platform.openai.com`,
  `docs.litellm.ai`, `privacy.claude.com`, `docs.ollama.com`); figures above come from
  search results, the official Anthropic data-residency page and the LiteLLM repository;
- current OpenAI model identifiers and prices (secondary sources disagree; COSTS.md §1);
- whether the owner already holds API accounts, their organisation settings (ZDR,
  residency, retention) and billing currency.

## 2. Target user experience (reference: RC Pro at AXA)

« Je veux enregistrer une assurance RC professionnelle chez AXA, 1 800 € par an, à partir
du 1er janvier. Voici le contrat. »

| Step | Who | What |
|---|---|---|
| 1 | gateway `classify_request` (`fast`) | recurring service, nature « insurance », candidate circuits among those Odoo sent |
| 2 | **Odoo** (ORM, user's rights) | searches partners « AXA », service products of insurance categories, running contracts with that partner |
| 3 | gateway `find_existing_records` (`fast`) | ranks **only** the candidates Odoo sent; flags likely duplicates |
| 4 | gateway `extract_document` (`document`) | policy number, insured party, cover, premium, periodicity, dates, notice, each with page and excerpt; « absent » when absent |
| 5 | gateway `identify_missing_information` (`fast`) | only the blocking questions (e.g. « the document says 1 650 € excl. tax, the message says 1 800 €: which one? ») |
| 6 | user | answers in the request's thread |
| 7 | gateway `propose_catalogue_objects` / `prepare_operation` (`reasoning` if ambiguous) | a structured proposal: objects to reuse, objects to request, values with evidence |
| 8 | **Odoo** | re-checks everything (rights, allowed lists, duplicates, taxes and accounts from configuration) and shows the summary |
| 9 | user with the right group | accepts, corrects or refuses; on accept, Odoo creates **drafts** in the existing circuits (IA-3): a product creation request, a contract proposal when ROADMAP A exists |
| 10 | existing approvers | approve and execute as today; nothing is posted or paid by the assistant |

Until ROADMAP A (recurring contracts) exists, step 9 stops at the product creation request
and a structured note: the assistant never creates an OCA `contract` itself.

## 3. Phases

Each phase: plan → audit → owner's go → development → audit → deployment on
`artdubati_test` with backup and rehearsed rollback.

| Phase | Content | Writes in Odoo | Real API | Exit criteria |
|---|---|---|---|---|
| **IA-0** | this plan, decisions of §6 | none | none | audit passed, decisions answered |
| **IA-1** | gateway alone (FastAPI + LiteLLM library), synthetic data, fake provider, the seven functions, schema validation, budget ledger, HMAC, document extractor, security tests of SECURITY.md §9 at gateway level; memory load test; one capped acceptance run of real calls | none (no Odoo access at all) | acceptance only, capped (COSTS.md §6) | all tests green with fake provider; memory measured; acceptance report; image digests recorded |
| **IA-2** | module `lartdubati_ai_assistant`, read-only assistant: free text + documents, classification, list of existing records found **by Odoo**, questions, proposal shown; kill switch; cost ledger; logs | only its own models (requests, messages, logs) | through the gateway, test keys | no record of other models created or changed (test); investor refused; disabled mode tested |
| **IA-3** | preparation mode: on acceptance, drafts in existing circuits (product creation request, supplier proposal as a request, contract proposal once ROADMAP A exists); no approval, no execution | drafts only, through business methods, as the user | yes | each draft passes the same checks as a manual one; config-change-between-proposal-and-execution refused |
| **IA-4** | controlled orchestration: after the human approvals of the existing circuits, Odoo runs the existing execution methods in sequence; the assistant only tracks and links | through existing execute methods, after approval | yes | no execution without the circuit's approval; idempotent replay |
| **IA-5** | Ollama `local` profile, after measuring volumes, costs and confidentiality needs; probably a separate machine | unchanged | local | no Odoo module change needed (proved by test) |

## 4. Reference scenarios (functional tests, IA-2 onwards)

Each scenario has a synthetic input (text + fabricated document, never a real one in
tests), a recorded fake-provider answer, and an expected **Odoo** outcome. « Circuit » =
what the assistant prepares in IA-3.

| # | Scenario | Expected classification | Expected behaviour |
|---|---|---|---|
| S1 | RC professionnelle | recurring service / insurance | partner search, duplicate contract check, extraction with evidence, product request if no insurance service product; no contract until ROADMAP A |
| S2 | Décennale tied to an installation | insurance / company cover (ROADMAP D) | question « which worksite or installation? »; never linked to an equipment; certificate as document |
| S3 | Internet and phone subscription | recurring service / telecom | reuses « Abonnement téléphonique » (626000) if found; internet product to request |
| S4 | ChatGPT subscription | recurring service / software-SaaS | product and account « to confirm with the accountant » (ROADMAP A, C25): category proposed only among allowed ones, flagged pending |
| S5 | Warehouse insurance | insurance / site | insured object = stock location chosen from Odoo's list |
| S6 | Van acquisition | equipment purchase, vehicle | capitalisation **not decided**: shows the category's configured treatment; Fleet out of scope until ROADMAP F |
| S7 | Trailer acquisition | same as S6 | same |
| S8 | Tiles and site consumables | consumables purchase | product creation request(s) in consumable categories; receipt through an equipment operation (consumables branch) |
| S9 | Workwear | consumables / workwear (« VT ») | category from the allowed list or « none fits » |
| S10 | Equipment to capitalise | equipment purchase | category's configured treatment shown; no capitalisation decision |
| S11 | Equipment expensed | equipment purchase | same, other category |
| S12 | Rented or borrowed item | equipment receipt, rented / borrowed branch | ownership status and owner asked if absent; rent from the contract line (DEFINITIONS.md) |
| S13 | Supplier consignment | consignment (ROADMAP 0 item 7) | **refused as « not supported yet »** with an explanation, until that phase exists |
| S14 | Product already exists | any | existing product proposed first; no creation request |
| S15 | Supplier absent | any | supplier proposal as a request; no `res.partner` created by the assistant |
| S16 | Bill received before the contract | bill / recurring | bill not created by the assistant; flags the missing contract |
| S17 | Contradictory or incomplete document | any | each contradiction listed with both excerpts; status `needs_information`; no proposal value chosen |

## 5. Security tests (summary; detail in SECURITY.md §9)

Prompt injection in a PDF, invalid JSON, invented account, forbidden category, provider
down, timeout, partial answer, concurrent double call, idempotent replay, budget exceeded,
user without rights, other company, document leaking into logs, fallback to an unallowed
provider, all APIs down, configuration changed between proposal and execution. All run
with the fake provider; none consumes a paid API.

## 6. Decisions expected from the owner

Each with options and a recommendation. Numbering kept for the audit.

| # | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | Hosting | (a) gateway on the Odoo VPS; (b) separate small VPS; (c) on the VPS now, separate later | **(a) for IA-1 / IA-2 if §1.1 shows ≥ 2 GB free at peak**, else (b). Gateway stays small with LiteLLM as a library and no ClamAV. (b) becomes mandatory with Ollama (IA-5) and with the test / production separation. DEPLOYMENT.md §2 |
| D2 | Odoo ↔ gateway authentication | bearer token; HMAC-signed requests; mTLS | **private network + HMAC-SHA256** (key id, timestamp, nonce, body digest), two active keys for rotation; mTLS if the gateway moves to another machine (with WireGuard). SECURITY.md §3 |
| D3 | Initial providers | Anthropic only; OpenAI only; both | **Anthropic primary, OpenAI fallback**, both direct, each with its DPA accepted, after confirming retention settings; no OpenRouter |
| D4 | Initial models per profile | COSTS.md §2 | `fast` = Claude Haiku 5.5; `document` = Claude Sonnet 5.5; `reasoning` = Claude Opus 5.5; `fallback` = an OpenAI model of comparable tier, **identifier pinned in IA-1** from OpenAI's official list (not verifiable from this session). Pinned identifiers only, never an alias to « latest » |
| D5 | Retention | (a) metadata only; (b) + validated proposals; (c) + full prompts | **(b)**: in Odoo, metadata and validated proposals with short excerpts (≤ 300 characters each); gateway keeps nothing beyond the idempotency cache (24 h, proposals only) and cost ledger; logs 90 days; request records follow Odoo's document retention. Full prompts never by default; a time-limited debug switch (≤ 24 h, synthetic data only) |
| D6 | Processing region | accept US / global processing under DPA + SCC; EU-only through OpenAI EU project (approval, +~10 %); EU through a cloud reseller (contradicts « direct ») | **Owner / legal decision.** Technical recommendation: v1 limited to documents of confidentiality ≤ `internal` (SECURITY.md §5) until D6 is answered; `inference_geo` pinned per profile, never changed by a fallback |
| D7 | Local OCR | none (text PDFs only); Tesseract / OCRmyPDF in the extractor; provider vision | **Tesseract (fra, eng, fas) in the extractor container from IA-1**, provider vision refused by default (it sends the whole page image) |
| D8 | Odoo request model | one model with JSON fields; request + child models | **request + children** (messages, documents, proposal lines, call log). ARCHITECTURE.md §4 |
| D9 | Who may accept a proposal | requester; separate group; approver of the target circuit | **group « AI Assistant User »** submits and accepts its own proposals **into drafts only**; the existing approvers of each circuit stay the only ones to approve; the requester never approves the created request (same rule as ROADMAP 0) |
| D10 | Fallback rules | none; same provider other model; other provider | **explicit list per profile**, same jurisdiction / `inference_geo` only, on availability errors only (timeout, 5xx, 429 after retries), never on a schema failure or refusal; the fallback used is shown and logged |
| D11 | Cost limits | as given: 50 € / month, 0.50 € / request, override after confirmation | **as given**, configurable in the gateway; Odoo shows the estimate; override only by a « AI Budget Manager » group, per request, logged; hard stop at the monthly cap. COSTS.md §5 |
| D12 | Data to anonymise or remove | SECURITY.md §5 | **removed before any call**: IBAN / BIC / card numbers, social-security numbers, personal phone and e-mail of natural persons, signatures and handwritten areas, Odoo internal ids; **pseudonymised**: names of natural persons (employees, individual customers). Company names, amounts, dates and policy numbers are kept (needed) |
| D13 | LiteLLM placement (raised by this plan) | library inside the gateway; separate LiteLLM proxy container | **library**: one container less, no admin UI, no master key, no LiteLLM database, smaller memory; the logical layer of the mission's diagram is kept. Proxy only if several applications share it later |
| D14 | Antivirus (raised by this plan) | none; ClamAV container; host scanner | **none in IA-1/IA-2** (only PDF / PNG / JPEG accepted, parsed in a container without network and without secrets); ClamAV considered with D1 (b) |
| D15 | Synchronous call or job polling (raised by this plan) | Odoo cron calls and waits (bounded); submit then poll | **cron calls and waits**, timeout below `limit_time_real_cron`, idempotent so a retry is free; polling if measured latency of `reasoning` exceeds it |

## 7. Open hypotheses

- H-AI-1: LiteLLM's mapping of structured outputs and `inference_geo` (§1.3).
- H-AI-2: the Odoo cron can commit before the HTTP call and hold no transaction during it
  (ARCHITECTURE.md §4.3); to prove by a test that locks the request row from another
  cursor during a slow fake call.
- H-AI-3: the VPS has room for the gateway (§1.1, §1.2).
- H-AI-4: provider retention settings available to the owner's accounts (§1.4).
- H-AI-5: the cost estimates of COSTS.md §3 hold (measured in the acceptance run).

## 8. Accounting

The assistant takes no accounting decision and adds no accounting question by itself: it
shows the treatment that Odoo's configuration (categories, profiles, C1–C25) gives. The
providers' own bills (API usage, prepaid credits) follow the existing supplier bill circuit
under the software / SaaS category of C25.

## Sources

- LiteLLM licence: [github.com/BerriAI/litellm/LICENSE](https://github.com/BerriAI/litellm/blob/main/LICENSE)
- LiteLLM releases: [docs.litellm.ai/release_notes](https://docs.litellm.ai/release_notes/), [GHCR versions](https://github.com/orgs/berriai/packages/container/litellm/versions)
- LiteLLM incident: [LiteLLM security update](https://docs.litellm.ai/blog/security-update-march-2026), [Bitsight](https://www.bitsight.com/blog/litellm-versions-1-82-7-1-82-8-supply-chain-compromise), [NetSPI](https://www.netspi.com/blog/executive-blog/ai-ml-pentesting/litellm-supply-chain-compromise/)
- LiteLLM signed images: [v1.83.14-stable notes](https://newreleases.io/project/github/BerriAI/litellm/release/v1.83.14-stable)
- FastAPI: [pepy.tech](https://pepy.tech/projects/fastapi), [CERN mirror](https://simple-repository.app.cern.ch/project/fastapi)
- OpenAI data: [EU data residency announcement](https://openai.com/index/introducing-data-residency-in-europe/), [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs.md), secondary: [wavect.io](https://wavect.io/blog/eu-data-residency-ai-apps-2026/), [compound.law](https://compound.law/en-DE/tools/openai-api/)
- Anthropic data: [data residency](https://platform.claude.com/docs/en/manage-claude/data-residency), [ZDR scope](https://privacy.claude.com/en/articles/8956058-i-have-a-zero-data-retention-agreement-with-anthropic-what-products-does-it-apply-to), secondary: [compound.law](https://compound.law/en-DE/tools/anthropic-api/), [char.com](https://char.com/blog/anthropic-data-retention-policy)
- Ollama: [structured outputs](https://registry.ollama.ai/blog/structured-outputs)

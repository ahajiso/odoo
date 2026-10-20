# Audit request — read-only server characterisation, revision 2

Status: **corrected after the audit of `2d5041e`; never executed on either real
server database**. This package does not authorise any server command:

- `characterize_readonly.sh` — proposed foreground command set;
- `characterize_helpers.py` — standard-library-only output sanitisation;
- `check_characterization.py` — exact-file pins and semantic allowlist;
- `test_characterization.py` — negative mutation and secret-canary tests.

The owner must obtain a new audit and then separately approve the exact one-time
execution procedure. No profile, campaign, account or isolated environment is created
by these files.

## Corrections after the audit of `2d5041e`

1. The module fingerprint uses the deployed-module expression already used by the
   backup procedure: `name || ' ' || coalesce(latest_version, '')`, ordered by name.
   It no longer substitutes `installed_version`.
2. Docker inspection is parsed as JSON by `characterize_helpers.py`. Environment
   values, including multiline values, are never emitted. Only variable names appear.
3. No secret value, length or unsalted value hash is printed. Secret files expose only
   path category, type, owner, group and mode. Environment and volume options
   expose names only.
4. Container command, entrypoint, label, proxy-header and volume-option output is
   sanitised. Shell payloads and the values of secret-like arguments are replaced by a
   presence marker.
5. `PGOPTIONS=default_transaction_read_only=on` is passed into each `docker exec`, and
   every fixed SQL block begins with `BEGIN TRANSACTION READ ONLY` and ends with
   `COMMIT`. SQL is pinned and allowlisted; `SET`, writes, `COPY`, dangerous functions
   and unreviewed statements are rejected.
6. The probes now include API-key metadata without key values, effective `ODOO_RC`,
   SMTP fallbacks, fetchmail/webhook counts, `archive_library`, replication slots and
   replication status, server version, root cron sources, and sanitised proxy-container
   configuration.
7. Each section reports `SECTION_OK` or `SECTION_FAILED` and later sections continue.
   The final summary lists all failures and returns non-zero when any section failed.
8. Git commands use per-command `core.fsmonitor=false` and
   `safe.directory=<exact checkout>`; they do not change repository or global Git
   configuration. Dirty/untracked paths are not printed.
9. Listener addresses are categorised as local, private or external. Actual effective
   base-URL values are reported only through the fixed Odoo parameter query, not by
   scanning arbitrary business text.
10. The one-off supplier refund probe in the plan is correctly identified as
    `in_refund`.

## Checker and tests

The checker first pins the complete SHA-256 of the shell script and helper. It then
independently parses the two SQL heredocs, shell commands, Docker/Git/systemctl/find
subcommands and the helper's Python AST against positive allowlists. Exact-file pins
prevent an unreviewed change from inheriting approval; the semantic layer makes the
intended read-only boundary reviewable.

The tests require rejection of 18 dangerous shell/SQL changes (including Docker
stop/pause/kill, Odoo shell, Git cleanup/reset-like operations, file writes, command
substitution, `COPY TO PROGRAM`, transaction changes and backend/config mutations) and
four Python process/file-write changes. Sanitisation tests use multiline environment,
command-line and volume-option canaries and assert that no value reaches output.

Current pinned hashes:

- `characterize_readonly.sh`:
  `bd6bc707683a585b2f58b172124c6a3909019e212cf9c765f6b3e8704001fb74`;
- `characterize_helpers.py`:
  `0d4020ee143f984e74f16bd53dd0e2496e8c23744eae6b9709dd3a9bc7965615`.

## Intended execution contract

The future operator obtains all four files from one audited commit, verifies their
hashes and runs the checker and tests before the shell script. The shell script is run
once in the foreground and emits only to stdout/stderr. Capturing its output, choosing
the host and scheduling the window remain separate owner decisions.

It must not restart, stop, create or mutate a container or service; create a database,
table, file or directory; run Odoo shell or initialise a registry; display credentials
or business-document content; or take the future source snapshot (which requires a
separately authorised real-service stop).

## Logical read-only guarantee and unavoidable physical effects

The PostgreSQL role may be superuser, so `default_transaction_read_only` is not treated
as an unbreakable privilege boundary. The guarantee is the conjunction of the exact
pinned SQL, semantic allowlist, session setting and explicit read-only transactions.
Changing any SQL invalidates the pin and requires another audit.

Even read-only observation can have physical effects. `docker exec` creates an exec
event/metadata; reads may update filesystem atime; PostgreSQL reads can set hint bits or
affect statistics/caches; `find`/`du` create I/O load; firewall inspection can load a
compatibility module on some hosts. These are declared observation effects, not
business/configuration writes. The auditor must decide whether any is unacceptable.

## Local disposable validation

The corrected package was exercised against disposable containers using real
PostgreSQL 16 and the official Odoo 18.0 image (Odoo 18.0-20261015). A real Odoo
database with `mail` was initialised and cloned as the second database. Both database
SQL sections, container/config sanitisation, secret metadata and filestore probes
completed successfully. Deliberate secret canaries from multiline environment values,
commands and option values did not appear.

Three host-specific sections failed as expected in that cloud sandbox (firewall access,
the absent production checkout path, and systemd/cron on a non-systemd host); subsequent
sections still ran and the script returned non-zero. This proves failure continuation,
not production-platform parity. All disposable containers, volumes and network were
then removed. No test has run against `artdubati_test`, `artdubati` or the real host.

## Coverage and external evidence

The output covers host sizing; Docker identities, topology and logging; listeners,
routes and firewall fingerprints; PostgreSQL databases/roles/connections/sizes,
archiving, replication and logging; effective Odoo database/cron/proxy/mail settings;
safe API-key/fetchmail/webhook metadata; module/count fingerprints; checkout and
filestore fingerprints; proxy and cron configuration; and retained-backup sizes.

Provider snapshots, external volume-backup policy, public DNS, Certificate Transparency
and provider-side API-key policy cannot be proven from the host. They remain explicit
external evidence requirements.

## Questions for the auditor

1. Do the fixed commands have an unacceptable direct or indirect write effect?
2. Can any branch of either sanitiser expose a credential, personal data or business
   content?
3. Is the pinned-SQL/read-only-transaction design sufficient for a superuser session?
4. Is the semantic allowlist complete enough that every executable path is constrained?
5. Are the local disposable evidence and its stated limitations represented accurately?
6. Are any probes missing for PLAN section 5.1, or should any probe be removed?

Requested decision: green light for a separately approved one-time execution, or a
severity-ranked correction list with precise file/line evidence. Nothing else is in
scope.

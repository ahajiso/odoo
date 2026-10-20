# Audit request — read-only server characterisation, revision 3

Status: **corrected after the audits of `2d5041e` and `3f682e6`; never executed on either real
server database**. This package does not authorise any server command:

- `characterize_readonly.sh` — proposed foreground command set;
- `characterize_helpers.py` — standard-library-only output sanitisation;
- `check_characterization.py` — exact-file pins and semantic allowlist;
- `test_characterization.py` — negative mutation and secret-canary tests.

The owner must obtain a new audit and then separately approve the exact one-time
execution procedure. No profile, campaign, account or isolated environment is created
by these files.

## Corrections after the audits

1. The module fingerprint uses the deployed-module expression already used by the
   backup procedure: `name || ' ' || coalesce(latest_version, '')`, ordered by name.
   It no longer substitutes `installed_version`.
2. Docker inspection is parsed as JSON by `characterize_helpers.py`. Environment
   values, including multiline values, are never emitted. Only variable names appear.
3. No secret value, length or unsalted value hash is printed. Secret files expose their
   full names under `/run/secrets`, type, owner, group and mode. Environment and volume
   options expose names only.
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
9. PostgreSQL client addresses are categorised as local, private or external. Listener
   addresses remain visible in `ss`; actual effective base-URL values are reported only
   through the fixed Odoo parameter query, not by scanning arbitrary business text.
10. The one-off supplier refund probe in the plan is correctly identified as
    `in_refund`.
11. Cron macros (`@reboot`, `@daily`, etc.) are parsed as one schedule field; schedule
    syntax is strictly validated and command environment assignments are discarded.
12. Inspected container commands retain the executable and option names only. Attached
    short password options, positional arguments and URL credentials/paths are masked.
13. Every command in a multi-command section propagates failure. A failed early probe
    can no longer be overwritten by the status of a later successful command.
14. CIFS-style mount credentials are removed by a JSON parser. All user crontabs and
    names in periodic cron directories are covered. API-key metadata now states whether
    the owning user is internal or an administrator, without exposing the login.
15. Mounted proxy configuration below the three known configuration roots is inspected
    safely. Embedded-image and effective proxy topology/authentication remain external
    evidence requirements because sanitised labels cannot prove D10.

## Checker and tests

The checker first pins the complete SHA-256 of the shell script and helper. This exact
pin plus human review is the security boundary. The semantic checks are defence in
depth: they reject selected dangerous SQL, shell and Python classes, but are not a
complete shell/SQL parser and do **not** constrain every executable path. Any change to
any of the four files invalidates the published hashes and requires another review.

The supplied tests require rejection of 18 dangerous shell/SQL changes (including Docker
stop/pause/kill, Odoo shell, Git cleanup/reset-like operations, file writes, command
substitution, `COPY TO PROGRAM`, transaction changes and backend/config mutations) and
four Python process/file-write changes. Sanitisation tests use multiline environment,
command-line, volume-option, proxy, cron and mount canaries and assert that no value
reaches output. The auditor is expected to add adversarial mutations rather than treat
this finite set as a proof of completeness.

The four independent file hashes are published below. The execution procedure must
compare them directly before running the checker; it must not trust hashes embedded in
the checker itself.

Current pinned hashes:

- `characterize_readonly.sh`:
  `70488b7249cd25f95c1f3b0079ecb601a0417f5a06697b6ee199e6046a92f0ce`;
- `characterize_helpers.py`:
  `55b3bddf77dcf61ec99a84eb334732d1947c6827c6b2014db0901e458c7595a4`;
- `check_characterization.py`:
  `fb04e0f7d5709f0e40fcb310a22130dee24d147578b171f75bb18a1a97deee5e`;
- `test_characterization.py`:
  `7aa1d04fee5702fe3aed20aea3de0804826816cda14cc28d704360c6c96ccf90`.

## Intended execution contract

The future operator obtains all four files from one audited commit, verifies their
hashes and runs the checker and tests before the shell script. The shell script is run
once in the foreground and emits only to stdout/stderr. Capturing its output, choosing
the host and scheduling the window remain separate owner decisions.

The future procedure must state that root access is required for process-aware listener
inspection, firewall inspection and root cron sources. It must first keep output in the
terminal, review it locally for unexpected content, and only then define any controlled
capture or sharing step; this document does not authorise either.

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

The revision-6 base was exercised against disposable containers using real
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

Revision 7 changes only output sanitisation, failure propagation and the additional
API-key classification query. Its new cron/command/mount canaries and final non-zero
aggregation pass locally; the full disposable Odoo/PostgreSQL exercise has not been
repeated. The second auditor independently checked the added Odoo columns and relation
names in Odoo 18 sources. Production-platform parity is still not claimed.

## Coverage and external evidence

The output covers host sizing; Docker identities, topology and logging; listeners,
routes and firewall fingerprints; PostgreSQL databases/roles/connections/sizes,
archiving, replication and logging; effective Odoo database/cron/proxy/mail settings;
safe API-key/fetchmail/webhook metadata; module/count fingerprints; checkout and
filestore fingerprints; proxy and cron configuration; and retained-backup sizes.

Provider snapshots, external volume-backup policy, public DNS, Certificate Transparency
and provider-side API-key policy cannot be proven from the host. Effective reverse-proxy
topology/authentication also remains external evidence when configuration is embedded
in an image or masked labels. They remain explicit external evidence requirements.

## Questions for the auditor

1. Do the fixed commands have an unacceptable direct or indirect write effect?
2. Can any branch of either sanitiser expose a credential, personal data or business
   content?
3. Is the pinned-SQL/read-only-transaction design sufficient for a superuser session?
4. Are the documented limits of the semantic checks accurate, with exact pins and
   human review correctly identified as the boundary?
5. Are the local disposable evidence and its stated limitations represented accurately?
6. Are any probes missing for PLAN section 5.1, or should any probe be removed?

Requested decision: green light for a separately approved one-time execution, or a
severity-ranked correction list with precise file/line evidence. Nothing else is in
scope.

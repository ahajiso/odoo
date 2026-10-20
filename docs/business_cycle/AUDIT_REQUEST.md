# Audit request — business-cycle acceptance plan revision 7

Scope: `docs/business_cycle/PLAN.md` revision 7 and the four-file, unexecuted-on-server
characterisation package described in `CHARACTERIZATION_AUDIT.md`.

No account, profile, business record, database, container or server configuration is
authorised. The only new execution was a disposable local validation with official
Odoo 18.0 and PostgreSQL 16; its resources were removed afterwards.

## State carried from the validated plan reviews

- The business campaign requires its own PostgreSQL/Odoo pair and filestore, with no
  network path to the real services.
- Role separation is tested by both UI and RPC; menus are not security controls.
- Catalogue, purchasing, warehouse, accounting, shareholder and no-profile investor
  identities remain individually attributable and removable with the isolated pair.
- The reference cycle uses an existing PO. Generic purchase request and controlled
  worksite consumption remain explicit gaps pending D6/D7.
- D8–D10 are confirmed: site manager requests/acknowledges but does not move stock;
  bounded tmpfs is preferred; browser access uses a stable neutral hostname with proxy
  authentication and Odoo login.
- The refund probe for a one-off supplier rental is an `in_refund`; its expected result
  remains unknown until tested.

## Corrections requested by the audits of `2d5041e` and `3f682e6`

The module fingerprint now uses `latest_version`. Multiline environment values,
commands, entrypoints, labels, volume options, proxy headers and secret metadata are
sanitised without exposing values, lengths or unsalted value hashes. PostgreSQL's
read-only setting is actually passed through `docker exec`, and fixed SQL is protected
by full-file hashes plus a semantic positive allowlist.

Coverage was extended to API-key metadata, effective `ODOO_RC`, SMTP fallbacks,
fetchmail/webhooks, PostgreSQL archiving/replication/version, root cron sources and
proxy containers. Sections continue after failure and return a final non-zero status.
Git uses per-command `core.fsmonitor=false` and `safe.directory`, without changing
configuration. Network addresses are categorised. External provider evidence remains
explicitly outside host proof.

The checker now rejects the dangerous shell, SQL and Python mutations listed in
`CHARACTERIZATION_AUDIT.md`; secret-canary tests cover multiline and embedded values.
Local disposable execution of the revision-6 base proved both real Odoo database SQL
sections, sanitisation and continuation after expected sandbox-specific section
failures. Revision 7's targeted sanitisation/failure tests pass, but its full disposable
Odoo/PostgreSQL exercise was not repeated. Neither run touched or reproduced the
production host.

After the second audit, cron macros have a strict dedicated parser; command output is
reduced to executable and option names; attached password options, URL credentials and
mount credentials are masked; and every command in a multi-command section propagates
failure. Cron coverage includes every user spool and periodic filenames. API-key owners
are classified as internal/administrator without login disclosure. Effective proxy
topology is now explicitly external evidence when it cannot be safely derived.

The documentation no longer presents the semantic checker as a formal boundary. The
security boundary is the exact commit plus independently compared hashes of all four
files and human review. The semantic checks and mutations are defence in depth.

The final two low findings are also closed: cron alphabetic tokens are restricted to
month/day names and supported markers, and DAV/SSHFS mount sources discard userinfo.

## Important qualification

“Read-only” is logical, not physically side-effect-free. `docker exec`, filesystem
reads, PostgreSQL reads, disk scans and firewall inspection can create metadata, atime,
hint-bit/statistics/cache, I/O or compatibility-module effects. The PostgreSQL role may
be superuser; safety therefore depends on the exact pinned SQL, its semantic allowlist,
the session default and explicit read-only transactions together. Any file change
invalidates the pin and requires another audit.

## Requested audit

1. Review all four characterisation files line by line, including every executable and
   error path.
2. Verify that the output cannot reveal a credential, personal data or business
   content.
3. Decide whether the declared indirect physical effects are acceptable for one
   separately approved run.
4. Verify the superuser/read-only reasoning and the full-file plus semantic allowlist.
5. Verify that the local disposable evidence is neither overstated nor missing a
   required production-specific check.
6. Review revision 7 for consistency with the prior plan findings and owner decisions.

Return exactly one outcome: green light for drafting a separately approved one-time
server execution procedure; corrections required, ranked by severity with precise
file/line evidence; or owner prerequisites. A green light does not itself authorise the
server command, campaign environment or audit users.

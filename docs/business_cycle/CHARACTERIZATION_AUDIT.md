# Audit request — read-only server characterisation commands

Status: **written, never executed**. These files do not authorise any server command:

- `characterize_readonly.sh` — proposed command set;
- `check_characterization.py` — local static checker, also not claimed as an independent
  security proof.

## Intended execution contract

The future operator would obtain the files from an audited commit, inspect their exact
SHA-256, and run the shell script once as a foreground command. The script emits only to
stdout/stderr. Log capture, the exact host and the execution window require a separate
owner approval after this audit.

It must not:

- restart, stop, create or mutate any container or service;
- create a database, temporary table, file or directory;
- run an Odoo shell or initialise an Odoo registry;
- display a password, key or environment value;
- query business data beyond aggregate counts and named configuration/cron/mail rows;
- perform the future source snapshot, which requires stopping real `odoo_web`.

Every PostgreSQL session sets `default_transaction_read_only=on` and starts an explicit
read-only transaction. Docker environment values and secret files are represented only
by presence, length/metadata and SHA-256. The Odoo config parser prints an allowlist of
non-secret fields and hashes password fields.

## Coverage

The output covers:

- host OS, memory, swap, mounts and capacity for D9 sizing;
- Docker version/root/log driver/security, every container, mount, network and volume;
- exact Odoo/PostgreSQL image identities;
- listeners, routes and firewall fingerprints;
- PostgreSQL DBs, owners, roles/superuser status, active connections, sizes, archive/WAL
  and logging settings;
- actual Odoo DB selection/filter/list/cron/proxy configuration without secrets;
- `database.uuid`, `database.secret`, base URL/freeze as fingerprints, mail-server safe
  fields, crons, module/count fingerprints for both real databases;
- secret mount names/permissions/sizes/hashes and container environment names/hashes;
- frozen code identity and dirty/untracked count/fingerprint without exposing filenames,
  and without optional Git locks;
- filestore and retained-backup sizes;
- reverse-proxy and scheduler configuration file hashes, relevant units/timers;
- explicit external evidence still required for provider snapshots, volume backups,
  public DNS and Certificate Transparency.

## Questions for the auditor

1. Does any command have a direct or indirect write side effect on the host, Docker,
   PostgreSQL, Odoo, Git checkout or filestore?
2. Could any output reveal a credential or personal/business content rather than a safe
   identifier, aggregate or fingerprint?
3. Are the SQL transactions provably read-only even if the database role is superuser?
4. Is the Odoo configuration allowlist adequate, and are any printed non-secret values
   nevertheless sensitive?
5. Does executing `docker exec` for `psql`, Python config parsing, `find`, `du` or `stat`
   create container or filesystem state on this platform?
6. Is the coverage sufficient for PLAN §5.1 and the audit of `f79f839`?
7. Identify missing probes, commands to remove, or output requiring additional
   sanitisation, with severity and exact line references.

Requested decision: green light to execute once under a separately approved procedure,
or corrections required. No other action is in scope.

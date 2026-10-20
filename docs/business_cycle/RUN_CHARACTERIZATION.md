# Single-run server characterisation procedure — draft 1

Status: **draft for audit; execution forbidden**. This procedure does not authorise a
server command. A new audit and a separate explicit owner instruction are required.

It extracts the four audited files from immutable code commit
`b5566cc5f3ff9c5bb6bb1b01d7253eb4401e47d6`. It never executes files from the live
checkout and never writes command output to a server file.

## 1. Preconditions and stop rules

The owner confirms all of the following before opening the window:

- operator is `root`; `python3`, Git, tar, Docker and SHA-256 tools are available;
- the audited commit already exists in `/opt/odoo/addons/custom/.git`; no fetch, pull,
  deployment or checkout occurs in the window;
- `odoo_web` and `odoo_db` have exactly those names and remain running normally;
- no deployment, backup, restore, database maintenance or provider snapshot operation
  is started during the window;
- the command runs interactively in the foreground from one stable root SSH session;
- `/dev/shm` is a mounted `tmpfs`; the fresh code copy lives there, outside the live
  checkout;
- raw output is visible only to the owner in that terminal. It is not redirected,
  piped, copied or shared during the run.

Any failed prerequisite stops the procedure. A `SECTION_FAILED`, non-zero final code,
unexpected output or lost SSH session also stops it. Nothing is corrected or rerun in
place. There is no improvised diagnostic command.

## 2. Prepare the fresh in-memory copy

Run this block only after the procedure itself has been audited. It prepares code in
`tmpfs`; it does not run the characterisation.

```bash
set -euo pipefail

SOURCE_REPO=/opt/odoo/addons/custom
AUDITED_COMMIT=b5566cc5f3ff9c5bb6bb1b01d7253eb4401e47d6
WORKDIR=/dev/shm/lartdubati-characterization-b5566cc

test "$(id -u)" = 0
test "$(findmnt -n -o FSTYPE --target /dev/shm)" = tmpfs
test ! -e "$WORKDIR"
test "$(git -c safe.directory="$SOURCE_REPO" -C "$SOURCE_REPO" rev-parse "$AUDITED_COMMIT^{commit}")" = "$AUDITED_COMMIT"

install -d -m 0700 "$WORKDIR"
git -c safe.directory="$SOURCE_REPO" -C "$SOURCE_REPO" archive "$AUDITED_COMMIT" -- \
  docs/business_cycle/characterize_readonly.sh \
  docs/business_cycle/characterize_helpers.py \
  docs/business_cycle/check_characterization.py \
  docs/business_cycle/test_characterization.py \
  | tar -x -C "$WORKDIR"

cd "$WORKDIR/docs/business_cycle"

printf '%s  %s\n' \
  '70488b7249cd25f95c1f3b0079ecb601a0417f5a06697b6ee199e6046a92f0ce' characterize_readonly.sh \
  'f27d4f27a241056301b20f7e0427df7c561f5f18dbb3ce201f60a4ab07be5c38' characterize_helpers.py \
  'bb900cf762b1b620c6672cc8043f168723ea3d30d671eb06c3b032bf9d3233bb' check_characterization.py \
  '0217c0228bc492f7130031a2cbb056271925c2ecddee457e705bc732f4b5abb9' test_characterization.py \
  | sha256sum -c -

PYTHONDONTWRITEBYTECODE=1 python3 -B check_characterization.py
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest -v test_characterization.py

test "$(find . -maxdepth 1 -type f | wc -l)" = 4
printf '%s  %s\n' \
  '70488b7249cd25f95c1f3b0079ecb601a0417f5a06697b6ee199e6046a92f0ce' characterize_readonly.sh \
  'f27d4f27a241056301b20f7e0427df7c561f5f18dbb3ce201f60a4ab07be5c38' characterize_helpers.py \
  'bb900cf762b1b620c6672cc8043f168723ea3d30d671eb06c3b032bf9d3233bb' check_characterization.py \
  '0217c0228bc492f7130031a2cbb056271925c2ecddee457e705bc732f4b5abb9' test_characterization.py \
  | sha256sum -c -

printf '%s\n' 'PREPARATION OK — STOP HERE UNTIL THE OWNER EXPLICITLY AUTHORIZES EXECUTION'
```

Expected result: four `OK` hash lines twice, seven passing unit tests, the allowlist
message and the final preparation message. Any difference stops the procedure.

## 3. Execute once, without capture

This is a separate owner decision after successful preparation. Do not add `tee`, shell
redirection, terminal logging or a pipe.

```bash
cd /dev/shm/lartdubati-characterization-b5566cc/docs/business_cycle
set +e
PYTHONDONTWRITEBYTECODE=1 bash ./characterize_readonly.sh
CHARACTERIZATION_RC=$?
set -e
printf 'CHARACTERIZATION_EXIT=%s\n' "$CHARACTERIZATION_RC"
test "$CHARACTERIZATION_RC" = 0
```

The operator reads the terminal locally before doing anything else. A failed section or
non-zero exit ends the window. It is reported as-is; it is not repaired and the command
is not repeated.

## 4. Output handling

Default policy for this first run:

- raw output remains in the owner's terminal scrollback only;
- it is not saved on the server and is not pasted into chat or sent to another person;
- the owner may manually report only the section names, `SECTION_OK`/`SECTION_FAILED`,
  final exit code and whether an unexpected secret or business value appeared;
- if detailed values are needed, stop and write a separate redaction, recipient and
  retention decision before any capture or sharing.

The owner separately supplies the `EXTERNAL_REQUIRED` evidence: provider snapshots and
volume-backup scope, effective reverse-proxy topology/authentication, public DNS and
Certificate Transparency history. It is not gathered by ad-hoc server commands.

After local review, the in-memory code copy may be removed with the explicit path below.
It contains only public repository files, not output:

```bash
test "$WORKDIR" = /dev/shm/lartdubati-characterization-b5566cc
find "$WORKDIR" -depth -delete
test ! -e "$WORKDIR"
```

## 5. Declared observation effects

This one-time read can create Docker exec metadata/events, filesystem atime, PostgreSQL
hint-bit/statistics/cache effects and disk load. Firewall inspection may load a
compatibility module. The owner accepts these limited physical observation effects only
for this authorised passage; they are not business or configuration writes.

This procedure does not authorise audit accounts, an audit database, containers,
profiles or the business campaign. D1–D7 remain owner decisions.

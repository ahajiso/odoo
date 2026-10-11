#!/usr/bin/env bash
# ROADMAP section 0, item 3: LOCAL rehearsal of the deployment window, in its order
# (README.md): precheck, update to 18.0.5.0.0, tests, migration dry run, --apply,
# control dry run, post-check, tests again on the migrated data. Stops at the first
# failure. Never on the server.
#
# Usage: bash rehearse.sh <seeded database> <work database>
#   the seeded database: built on the server's code (main ae31573, pinned OCA, the 122
#   modules) then seed_server_state.py; it is copied, never changed.
# Environment: DEVENV (local Odoo and configs), OUT (logs).
set -euo pipefail
SEED=${1:?seeded database}
DB=${2:?work database}
DEVENV=${DEVENV:-/home/user/devenv}
HERE=$(cd "$(dirname "$0")/.." && pwd)
OUT=${OUT:?directory for the logs}
PSQL="psql -h /tmp -p 5433 -U root"
ODOO="$DEVENV/venv/bin/python $DEVENV/odoo/odoo-bin -c $DEVENV/odoo_srv2.conf"
MODULES=maintenance_shareholder_equipment,lartdubati_investor_home
TAGS=/maintenance_shareholder_equipment,/lartdubati_investor_home
step() { echo "== $*"; }
fail() { echo "REHEARSAL FAILED: $*"; exit 1; }
mkdir -p "$OUT"

step "copy $SEED to $DB"
dropdb -h /tmp -p 5433 -U root --if-exists "$DB"
rm -rf "$DEVENV/data/filestore/$DB"
createdb -h /tmp -p 5433 -U root -T "$SEED" "$DB"
cp -r "$DEVENV/data/filestore/$SEED" "$DEVENV/data/filestore/$DB"

step "precheck (read-only, no row expected)"
ROWS=$($PSQL -d "$DB" -At -F ' | ' < "$HERE/precheck_catalogue.sql")
echo "${ROWS:-no row}"

step "update $MODULES"
$ODOO -d "$DB" -u "$MODULES" --stop-after-init > "$OUT/update.log" 2>&1 || fail "update"
! grep -E " (ERROR|CRITICAL) " "$OUT/update.log" || fail "update logged errors"

tests() {
  $ODOO -d "$DB" -u "$MODULES" --test-enable --test-tags "$TAGS" --log-level=test \
    --workers 0 --http-port 8079 --stop-after-init > "$OUT/$1.log" 2>&1 || fail "tests $1 (exit code)"
  grep -E "odoo.tests.result: " "$OUT/$1.log" | tail -1
  grep -qE "odoo.tests.result: 0 failed, 0 error\(s\) of [0-9]+ tests" "$OUT/$1.log" || fail "tests $1"
}
step "tests before the migration"
tests tests_before

SHELL_CMD="$DEVENV/venv/bin/python $DEVENV/odoo/odoo-bin shell -c $DEVENV/odoo_srv2.conf -d $DB --no-http"
for mode in "" --apply ""; do
  step "migration ${mode:-dry run}"
  env ROADMAP0_REHEARSAL=1 LOGDIR="$OUT" ODOO_SHELL="$SHELL_CMD" bash "$HERE/run_migration.sh" $mode \
    || fail "migration ${mode:-dry run}"
done

step "post-check (no row expected)"
ROWS=$($PSQL -d "$DB" -At -F ' | ' < "$HERE/postcheck_catalogue.sql")
[ -z "$ROWS" ] || { echo "$ROWS"; fail "post-check rows"; }
echo "no row"

step "tests after the migration"
tests tests_after
echo "REHEARSAL OK"

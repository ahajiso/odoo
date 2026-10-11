#!/usr/bin/env bash
# ROADMAP section 0: end of the deployment window (audit of 9c407ae, point 3), after
# deploy_modules.sh (KEEP_STOPPED=1) and run_migration.sh (dry run, --apply).
# odoo_web must be STOPPED; it stays stopped until every check on the migrated data
# passed, and is stopped again at once if a check fails after its start.
#
#   1. control dry run of the migration: exactly 0 change (run_migration.sh);
#   2. post-check SQL: no row;
#   3. the module tests on the migrated data (one-shot container, as deploy_modules.sh):
#      exactly « 0 failed, 0 error(s) of <expected> tests »;
#   4. start odoo_web, which must answer /web/health;
#   5. platform after (check_modules.sh after) and the post-check again: PLATFORM OK,
#      no row; otherwise odoo_web is STOPPED again.
#
# Usage: bash finish_window.sh <expected number of tests>
# Any failure prints FAILED and exits 1; then the README's rollback.
set -euo pipefail
DB=artdubati_test
MODULES=maintenance_shareholder_equipment,lartdubati_investor_home
TAGS=/maintenance_shareholder_equipment,/lartdubati_investor_home
EXPECTED_TESTS=${1:-}
LOGDIR=${LOGDIR:-/opt/odoo/logs}
STAMP=$(date +%F_%H%M)
LOGT="$LOGDIR/roadmap0_tests_after_migration_$STAMP.log"
HERE=$(cd "$(dirname "$0")" && pwd)
ODOO_PORT=${ODOO_PORT:-8069}
STARTED=0

fail() {
  echo
  echo "FAILED: $1"
  if [ "$STARTED" = 1 ]; then
    docker stop odoo_web > /dev/null && echo "odoo_web STOPPED again." \
      || echo "docker stop odoo_web FAILED: stop it by hand at once."
  else
    echo "odoo_web is left STOPPED."
  fi
  echo "Next: the README's rollback, then send the outputs to Claude."
  exit 1
}

[[ "$EXPECTED_TESTS" =~ ^[0-9]+$ ]] || { echo "Give the expected number of tests."; exit 1; }
[ "$(docker inspect -f '{{.State.Running}}' odoo_web)" = false ] || {
  echo "odoo_web is running: this script expects it stopped (KEEP_STOPPED=1). Nothing done."; exit 1; }
mkdir -p "$LOGDIR"

postcheck() {
  local rows
  rows=$(docker exec -i odoo_db psql -U odoo -d "$DB" -At -F ' | ' -v ON_ERROR_STOP=1 \
         < "$HERE/postcheck_catalogue.sql") || fail "post-check could not run"
  [ -z "$rows" ] || { echo "$rows"; fail "post-check rows ($1)"; }
  echo "POSTCHECK OK ($1): no row"
}

echo "1. control dry run (odoo_web stopped)"
bash "$HERE/run_migration.sh" || fail "control dry run"
grep -q '^STATE | already migrated' "$(ls -t "$LOGDIR"/roadmap0_migration_dryrun_2*.txt | head -1)" \
  || fail "the control dry run did not find a migrated database"

echo "2. post-check (odoo_web stopped)"
postcheck "stopped"

echo "3. tests on the migrated data (odoo_web stopped)"
IMG=$(docker inspect -f '{{.Config.Image}}' odoo_web)
NETS=$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' odoo_web)
read -r -a NETA <<< "$NETS"
[ "${#NETA[@]}" -eq 1 ] || fail "odoo_web must be on exactly one Docker network: '$NETS'"
ENVF=$(mktemp)
trap 'rm -f "$ENVF"' EXIT
chmod 600 "$ENVF"
docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' odoo_web > "$ENVF"
if ! docker run --rm --network "${NETA[0]}" --volumes-from odoo_web --env-file "$ENVF" "$IMG" \
     odoo -d "$DB" -u "$MODULES" --test-enable --test-tags "$TAGS" --log-level=test \
     --workers 0 --stop-after-init > "$LOGT" 2>&1; then
  grep -E "tests when|FAIL:|ERROR:" "$LOGT" || true
  fail "tests (exit code), see $LOGT"
fi
grep -q "0 failed, 0 error(s) of $EXPECTED_TESTS tests" "$LOGT" || {
  grep -E "tests when|FAIL:|ERROR:" "$LOGT" || true
  fail "tests: expected « 0 failed, 0 error(s) of $EXPECTED_TESTS tests », see $LOGT"; }
echo "TESTS OK: 0 failed, 0 error(s) of $EXPECTED_TESTS tests (migrated data)"

echo "4. start odoo_web"
docker start odoo_web > /dev/null || fail "docker start odoo_web"
STARTED=1
ready=0
for _ in $(seq 1 30); do
  if docker exec odoo_web python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:$ODOO_PORT/web/health', timeout=3)" \
       > /dev/null 2>&1; then ready=1; break; fi
  sleep 3
done
[ "$ready" = 1 ] || fail "odoo_web does not answer /web/health"
echo "HEALTH OK"

echo "5. platform after and post-check (odoo_web running)"
bash "$HERE/../phase4/check_modules.sh" after || fail "platform after"
postcheck "running"
echo "WINDOW OK: migrated, checked, tested, odoo_web serving."

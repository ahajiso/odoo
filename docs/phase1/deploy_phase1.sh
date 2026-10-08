#!/usr/bin/env bash
# Phase 1: update the two modules on artdubati_test and run their tests, with odoo_web
# STOPPED (it also serves production: plan a maintenance window).
#
# Usage: bash deploy_phase1.sh /opt/odoo/backups/artdubati_test_<date>_phase1.dump
#
# Stops at the first failure and leaves odoo_web STOPPED: Odoo commits after each
# module, so a failure can leave the database partly updated. Then follow
# « 6b. Rollback » of docs/phase1/README.md (restore the backup, previous code).
# The file holding odoo_web's environment (database credentials) is always removed.
set -euo pipefail

DB=artdubati_test
MODULES=maintenance_shareholder_equipment,lartdubati_investor_home
TAGS=/maintenance_shareholder_equipment,/lartdubati_investor_home
EXPECTED_TESTS=47
LOGDIR=/opt/odoo/logs
STAMP=$(date +%F_%H%M)
LOG="$LOGDIR/phase1_update_$STAMP.log"
LOGT="$LOGDIR/phase1_tests_$STAMP.log"
BACKUP=${1:-}

fail() {
  echo
  echo "FAILED: $1"
  echo "odoo_web is left STOPPED. Logs: $LOG $LOGT"
  echo "Next: docs/phase1/README.md, « 6b. Rollback », then send the logs to Claude."
  exit 1
}

[ -n "$BACKUP" ] && [ -s "$BACKUP" ] || {
  echo "Give the backup of step 1 as argument (non-empty file)."; exit 1; }
mkdir -p "$LOGDIR"

IMG=$(docker inspect -f '{{.Config.Image}}' odoo_web)
NET=$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' odoo_web | awk '{print $1}')
[ -n "$IMG" ] && [ -n "$NET" ] || { echo "Cannot read image or network of odoo_web."; exit 1; }
ENVF=$(mktemp)
trap 'rm -f "$ENVF"' EXIT
chmod 600 "$ENVF"
docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' odoo_web > "$ENVF"

run_odoo() {
  docker run --rm --network "$NET" --volumes-from odoo_web --env-file "$ENVF" "$IMG" odoo "$@"
}

echo "Backup: $BACKUP"
echo "Image: $IMG, network: $NET"
echo "Stopping odoo_web (production unavailable until the end)..."
docker stop odoo_web

echo "Updating $MODULES on $DB..."
if ! run_odoo -d "$DB" -u "$MODULES" --stop-after-init > "$LOG" 2>&1; then
  fail "module update (exit code), see $LOG"
fi
if grep -E " (ERROR|CRITICAL) " "$LOG"; then
  fail "module update logged errors"
fi
echo "UPDATE OK"

echo "Running the tests..."
if ! run_odoo -d "$DB" -u "$MODULES" --test-enable --test-tags "$TAGS" \
     --log-level=test --workers 0 --stop-after-init > "$LOGT" 2>&1; then
  grep -E "tests when|FAIL:|ERROR:" "$LOGT" || true
  fail "tests (exit code)"
fi
if ! grep -q "0 failed, 0 error(s) of $EXPECTED_TESTS tests" "$LOGT"; then
  grep -E "tests when|FAIL:|ERROR:" "$LOGT" || true
  fail "tests: expected « 0 failed, 0 error(s) of $EXPECTED_TESTS tests »"
fi
echo "TESTS OK: 0 failed, 0 error(s) of $EXPECTED_TESTS tests"

docker start odoo_web
echo "odoo_web started. Phase 1 update done."

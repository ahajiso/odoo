#!/usr/bin/env bash
# Stop odoo_web, move the code to the announced commit, then update the two modules on
# artdubati_test and run their tests, with odoo_web STOPPED: the running server never
# sees the new files (audit of 643f95e, point 3). odoo_web serves every database of the server: acceptable only while there is
# no real production (see docs/deployment/investor_home.md, section 0).
#
# Usage: bash deploy_modules.sh <backup.dump> <expected number of tests> <label, e.g. phase3> \
#          <commit announced by Claude, fetched as origin/main>
#
# Stops at the first failure and leaves odoo_web STOPPED: Odoo commits after each
# module, so a failure can leave the database partly updated. Then follow
# the « Rollback » section of the phase README (restore the backup, previous code).
# The file holding odoo_web's environment (database credentials) is always removed.
set -euo pipefail

DB=artdubati_test
MODULES=maintenance_shareholder_equipment,lartdubati_investor_home
TAGS=/maintenance_shareholder_equipment,/lartdubati_investor_home
EXPECTED_TESTS=${2:-}
LOGDIR=${LOGDIR:-/opt/odoo/logs}
LABEL=${3:-update}
STAMP=$(date +%F_%H%M)
LOG="$LOGDIR/${LABEL}_update_$STAMP.log"
LOGT="$LOGDIR/${LABEL}_tests_$STAMP.log"
BACKUP=${1:-}
COMMIT=${4:-}
ADDONS=${ADDONS:-/opt/odoo/addons/custom}

fail() {
  echo
  echo "FAILED: $1"
  echo "odoo_web is left STOPPED. Logs: $LOG $LOGT"
  echo "Next: the « Rollback » section of the phase README, then send the logs to Claude."
  exit 1
}

[ -n "$BACKUP" ] && [ -s "$BACKUP" ] || {
  echo "Give the backup of step 1 as first argument (non-empty file)."; exit 1; }
[[ "$EXPECTED_TESTS" =~ ^[0-9]+$ ]] || {
  echo "Give the expected number of tests as second argument."; exit 1; }
[ -n "$COMMIT" ] || { echo "Give the commit announced by Claude as fourth argument."; exit 1; }
TARGET=$(git -C "$ADDONS" rev-parse --verify --quiet "$COMMIT^{commit}") || {
  echo "Commit $COMMIT not found: run the fetch step of the README first."; exit 1; }
[ "$(git -C "$ADDONS" rev-parse origin/main)" = "$TARGET" ] || {
  echo "origin/main is not $COMMIT: fetch again or check the commit with Claude."; exit 1; }
[ -z "$(git -C "$ADDONS" status --porcelain --untracked-files=no)" ] || {
  echo "The working tree of $ADDONS has local changes: nothing done, send them to Claude."; exit 1; }
git -C "$ADDONS" merge-base --is-ancestor HEAD "$TARGET" || {
  echo "$COMMIT does not follow the current commit (no fast-forward): send this to Claude."; exit 1; }
mkdir -p "$LOGDIR"

IMG=$(docker inspect -f '{{.Config.Image}}' odoo_web)
NETS=$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' odoo_web)
read -r -a NETA <<< "$NETS"
[ -n "$IMG" ] || { echo "Cannot read the image of odoo_web."; exit 1; }
[ "${#NETA[@]}" -eq 1 ] || {
  echo "odoo_web must be on exactly one Docker network, found: '${NETS}'. Send this to Claude."; exit 1; }
NET=${NETA[0]}
ENVF=$(mktemp)
trap 'rm -f "$ENVF"' EXIT
chmod 600 "$ENVF"
docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' odoo_web > "$ENVF"

run_odoo() {
  docker run --rm --network "$NET" --volumes-from odoo_web --env-file "$ENVF" "$IMG" odoo "$@"
}

echo "Backup: $BACKUP"
echo "Image: $IMG, network: $NET"
echo "Stopping odoo_web (every database unavailable until the end)..."
docker stop odoo_web > /dev/null || {
  echo "FAILED: docker stop odoo_web. Nothing was changed; check « docker ps -a »."; exit 1; }
[ "$(docker inspect -f '{{.State.Running}}' odoo_web)" = "false" ] || {
  echo "FAILED: odoo_web still running. Nothing was changed."; exit 1; }

echo "Moving the code to $COMMIT (odoo_web stopped)..."
git -C "$ADDONS" merge --ff-only "$TARGET" > /dev/null || fail "git merge --ff-only $COMMIT"
[ "$(git -C "$ADDONS" rev-parse HEAD)" = "$TARGET" ] || fail "the code is not at $COMMIT"
echo "CODE OK: $(git -C "$ADDONS" log -1 --oneline)"

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

docker start odoo_web > /dev/null || {
  echo "FAILED: docker start odoo_web, although update and tests passed."
  echo "Run « docker start odoo_web » and « docker logs --tail 50 odoo_web », send them to Claude."
  exit 1; }
echo "odoo_web started. Update $LABEL done."

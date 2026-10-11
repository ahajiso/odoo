#!/usr/bin/env bash
# ROADMAP section 0, item 3: runs migrate_catalogue.py on artdubati_test through the
# Odoo shell (superuser mode), after the update to 18.0.5.0.0 (docs/roadmap0/README.md).
#   bash run_migration.sh           dry run: changes made, checked, printed, rolled back
#   bash run_migration.sh --apply   the same, committed only when no ERROR line
# Odoo's exit code checked (pipefail), stderr kept, no Python error, no ERROR, KEPT or
# BLOCKED line, and the last line must be the expected END with 77 changes (first run)
# or 0 (migrated); otherwise MIGRATION FAILED and exit 1. The script itself refuses the
# commit on the same conditions (exact count per section), before committing.
# Local rehearsal only: ODOO_SHELL="python3 odoo-bin shell -c <conf> -d <db> --no-http"
# and ROADMAP0_REHEARSAL=1 replace the container.
set -euo pipefail
DB=${DB:-artdubati_test}
LOGDIR=${LOGDIR:-/opt/odoo/logs}
HERE=$(cd "$(dirname "$0")" && pwd)
SCRIPT="$HERE/migrate_catalogue.py"
MODE=dryrun
APPLY=0
case "${1:-}" in
  "") ;;
  --apply) MODE=apply; APPLY=1 ;;
  *) echo "usage: bash run_migration.sh [--apply]"; exit 2 ;;
esac
STAMP=$(date +%F_%H%M%S)
RAW="$LOGDIR/roadmap0_migration_${MODE}_raw_$STAMP.txt"
ERR="$LOGDIR/roadmap0_migration_${MODE}_stderr_$STAMP.txt"
OUT="$LOGDIR/roadmap0_migration_${MODE}_$STAMP.txt"
fail() { echo "MIGRATION FAILED: $*"; echo "output: $RAW"; echo "stderr: $ERR"; exit 1; }

[ -s "$SCRIPT" ] || fail "$SCRIPT missing"
mkdir -p "$LOGDIR"
if [ -n "${ODOO_SHELL:-}" ]; then
  RUN() { ROADMAP0_APPLY=$APPLY $ODOO_SHELL; }
elif [ "$(docker inspect -f '{{.State.Running}}' odoo_web)" = true ]; then
  RUN() { docker exec -i -e ROADMAP0_APPLY=$APPLY odoo_web odoo shell -d "$DB" --no-http; }
else
  # odoo_web stopped (deployment window, KEEP_STOPPED=1): a one-shot container of the
  # same image, network, volumes and environment, as deploy_modules.sh does
  IMG=$(docker inspect -f '{{.Config.Image}}' odoo_web)
  NET=$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' odoo_web)
  read -r -a NETA <<< "$NET"
  [ "${#NETA[@]}" -eq 1 ] || fail "odoo_web must be on exactly one Docker network: '$NET'"
  ENVF=$(mktemp)
  trap 'rm -f "$ENVF"' EXIT
  chmod 600 "$ENVF"
  docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' odoo_web > "$ENVF"
  RUN() { docker run --rm -i --network "${NETA[0]}" --volumes-from odoo_web --env-file "$ENVF" \
            -e ROADMAP0_APPLY=$APPLY "$IMG" odoo shell -d "$DB" --no-http; }
  echo "odoo_web is stopped: one-shot container $IMG on ${NETA[0]}"
fi
if ! RUN < "$SCRIPT" > "$RAW" 2> "$ERR"; then
  tail -20 "$ERR"; grep -E '^(ERROR|END|REFUSED)' "$RAW" | tail -20 || true
  fail "odoo shell exited with an error"
fi
grep -E '^[A-Z0-9]+ \|' "$RAW" > "$OUT" || true
if grep -qE '^Traceback|Error:|^REFUSED' "$RAW" "$ERR"; then
  grep -nE -A3 '^Traceback|Error:|^REFUSED' "$RAW" "$ERR" | tail -20; fail "a Python error or a refusal was printed"
fi
if grep -qE '^(ERROR|KEPT|BLOCKED) \|' "$OUT"; then
  grep -E '^(ERROR|KEPT|BLOCKED) \|' "$OUT"
  fail "ERROR, KEPT or BLOCKED lines: the script refused the commit, nothing was written"
fi
# second protection (audit of 9c407ae): the exact total, 77 on the inventory's data
# before the migration, 0 once migrated (the script already refuses any other count)
if grep -q '^STATE | already migrated' "$OUT"; then TOTAL=0; else TOTAL=77; fi
LAST=$(tail -1 "$OUT")
if [ "$APPLY" = 1 ]; then
  [ "$LAST" = "END | applied, $TOTAL change(s) committed" ] || fail "unexpected last line: $LAST (expected $TOTAL changes)"
else
  [ "$LAST" = "END | dry run, $TOTAL change(s) rolled back" ] || fail "unexpected last line: $LAST (expected $TOTAL changes)"
fi
echo "MIGRATION OK ($MODE): $OUT ($(wc -l < "$OUT") lines)"
echo "$LAST"
cut -d' ' -f1 "$OUT" | grep -v '^END$' | sort | uniq -c | awk '{printf "  %-8s %s\n", $2, $1}'

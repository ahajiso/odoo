#!/usr/bin/env bash
# ROADMAP section 0: runs inventory.py (read-only, rolled back) on artdubati_test through
# the Odoo shell (audit of d76e4cc): Odoo's exit code checked (pipefail), stderr kept,
# the last line must be END; any failure prints INVENTORY FAILED and exits 1.
#
# Usage: bash run_inventory.sh [script]   (default: inventory.py next to this file; a
#        bare name, e.g. complement.py, is looked up next to this file)
set -euo pipefail
DB=${DB:-artdubati_test}
LOGDIR=${LOGDIR:-/opt/odoo/logs}
HERE=$(cd "$(dirname "$0")" && pwd)
SCRIPT=${1:-inventory.py}
[ -e "$SCRIPT" ] || SCRIPT="$HERE/$SCRIPT"
NAME=$(basename "$SCRIPT" .py)
STAMP=$(date +%F_%H%M%S)
RAW="$LOGDIR/roadmap0_${NAME}_raw_$STAMP.txt"
ERR="$LOGDIR/roadmap0_${NAME}_stderr_$STAMP.txt"
OUT="$LOGDIR/roadmap0_${NAME}_$STAMP.txt"
fail() { echo "INVENTORY FAILED: $*"; echo "stderr: $ERR"; exit 1; }

[ -s "$SCRIPT" ] || fail "$SCRIPT missing"
if ! docker exec -i odoo_web odoo shell -d "$DB" --no-http < "$SCRIPT" > "$RAW" 2> "$ERR"; then
  tail -20 "$ERR"; fail "odoo shell exited with an error"
fi
grep -E '^[A-Z]+ \|' "$RAW" > "$OUT" || true
if grep -qE '^Traceback|Error:' "$RAW" "$ERR"; then
  grep -nE -A3 '^Traceback|Error:' "$RAW" "$ERR" | tail -20; fail "a Python error was printed"
fi
[ "$(tail -1 "$OUT")" = "END | read-only inventory complete" ] || fail "the END line is missing"
echo "INVENTORY OK: $OUT ($(wc -l < "$OUT") lines)"
cut -d' ' -f1 "$OUT" | grep -v '^END$' | sort | uniq -c | awk '{printf "  %-8s %s\n", $2, $1}'

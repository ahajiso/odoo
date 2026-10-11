#!/usr/bin/env bash
# ROADMAP section 0: runs inventory.py (read-only, rolled back) on artdubati_test through
# the Odoo shell (audit of d76e4cc): Odoo's exit code checked (pipefail), stderr kept,
# the last line must be END; any failure prints INVENTORY FAILED and exits 1.
#
# Usage: bash run_inventory.sh [script]   (default: inventory.py next to this file)
set -euo pipefail
DB=${DB:-artdubati_test}
LOGDIR=${LOGDIR:-/opt/odoo/logs}
SCRIPT=${1:-$(cd "$(dirname "$0")" && pwd)/inventory.py}
STAMP=$(date +%F_%H%M%S)
RAW="$LOGDIR/roadmap0_inventory_raw_$STAMP.txt"
ERR="$LOGDIR/roadmap0_inventory_stderr_$STAMP.txt"
OUT="$LOGDIR/roadmap0_inventory_$STAMP.txt"
fail() { echo "INVENTORY FAILED: $*"; echo "stderr: $ERR"; exit 1; }

[ -s "$SCRIPT" ] || fail "$SCRIPT missing"
if ! docker exec -i odoo_web odoo shell -d "$DB" --no-http < "$SCRIPT" > "$RAW" 2> "$ERR"; then
  tail -20 "$ERR"; fail "odoo shell exited with an error"
fi
grep -E '^(CATEG|PRODUCT|ECATEG|LABEL|MAC|OWNER|END) \|' "$RAW" > "$OUT" || true
if grep -qE '^Traceback|Error:' "$RAW" "$ERR"; then
  grep -nE -A3 '^Traceback|Error:' "$RAW" "$ERR" | tail -20; fail "a Python error was printed"
fi
[ "$(tail -1 "$OUT")" = "END | read-only inventory complete" ] || fail "the END line is missing"
echo "INVENTORY OK: $OUT ($(wc -l < "$OUT") lines)"
for section in CATEG PRODUCT ECATEG LABEL MAC OWNER; do
  printf '  %-8s %s\n' "$section" "$(grep -c "^$section |" "$OUT" || true)"
done

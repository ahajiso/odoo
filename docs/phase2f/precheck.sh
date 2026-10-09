#!/usr/bin/env bash
# Phase 2f precheck, read-only, BEFORE the update (docs/phase2f/README.md, step 4).
# Runs precheck.sql (next to this script) against the database through odoo_db.
# Exit 0: no blocking finding. Exit 1: findings printed, do not update.
# Usage: bash precheck.sh [database] [--keep-receipt NAME]...
#   default database: artdubati_test
#   --keep-receipt NAME: an open receipt the owner decided to keep (D4); it no longer
#   blocks and is listed as kept. It will be received later through an equipment
#   operation (purchase, existing order), which takes it over.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB="artdubati_test"
if [ $# -gt 0 ] && [ "${1#--}" = "$1" ]; then DB="$1"; shift; fi
KEEP=()
while [ $# -gt 0 ]; do
  case "$1" in
    --keep-receipt) [ $# -ge 2 ] || { echo "--keep-receipt needs a receipt name"; exit 2; }
                    KEEP+=("$2"); shift 2 ;;
    *) echo "unknown argument: $1"; exit 2 ;;
  esac
done
[ -f "$DIR/precheck.sql" ] || { echo "precheck.sql not found next to $0"; exit 2; }
OUT=$(docker exec -i odoo_db psql -U odoo -d "$DB" -At -F ' | ' -v ON_ERROR_STOP=1 < "$DIR/precheck.sql")
BLOCKING=""
KEPT=""
FOUND=()
while IFS= read -r line; do
  [ -n "$line" ] || continue
  check="${line%% | *}"
  detail="${line##* | }"
  kept=0
  if [ "$check" = "open_receipt" ]; then
    for name in "${KEEP[@]+"${KEEP[@]}"}"; do
      if [ "$detail" = "$name" ]; then kept=1; FOUND+=("$name"); fi
    done
  fi
  if [ "$kept" = 1 ]; then KEPT+="$line"$'\n'; else BLOCKING+="$line"$'\n'; fi
done <<< "$OUT"
# a name given to --keep-receipt must be an open receipt found by the precheck
for name in "${KEEP[@]+"${KEEP[@]}"}"; do
  ok=0
  for found in "${FOUND[@]+"${FOUND[@]}"}"; do [ "$found" = "$name" ] && ok=1; done
  [ "$ok" = 1 ] || BLOCKING+="keep_receipt | - | $name is not an open receipt found by the precheck"$'\n'
done
[ -z "$KEPT" ] || { echo "Open receipts kept by decision (D4):"; printf '%s' "$KEPT"; }
if [ -n "$BLOCKING" ]; then
  echo "PRECHECK FAILED on $DB (check | id | detail):"
  printf '%s' "$BLOCKING"
  echo "Fix these with setup_phase2f.py (dry run shows how), then run the precheck again."
  exit 1
fi
echo "PRECHECK OK: no blocking finding on $DB"

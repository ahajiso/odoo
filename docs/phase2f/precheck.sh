#!/usr/bin/env bash
# Phase 2f precheck, read-only, BEFORE the update (docs/phase2f/README.md, step 4).
# Runs precheck.sql (next to this script) against the database through odoo_db.
# Exit 0: no blocking finding. Exit 1: findings printed, do not update.
# Usage: bash precheck.sh [database]   (default artdubati_test)
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB="${1:-artdubati_test}"
[ -f "$DIR/precheck.sql" ] || { echo "precheck.sql not found next to $0"; exit 2; }
OUT=$(docker exec -i odoo_db psql -U odoo -d "$DB" -At -F ' | ' -v ON_ERROR_STOP=1 < "$DIR/precheck.sql")
if [ -n "$OUT" ]; then
  echo "PRECHECK FAILED on $DB (check | id | detail):"
  echo "$OUT"
  echo "Fix these with setup_phase2f.py (dry run shows how), then run the precheck again."
  exit 1
fi
echo "PRECHECK OK: no blocking finding on $DB"

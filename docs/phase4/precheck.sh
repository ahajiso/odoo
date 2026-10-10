#!/usr/bin/env bash
# Phase 4 precheck, read-only, BEFORE the update (docs/phase4/README.md).
# Prints the investor accounts and the hidden menus (information), then runs
# precheck.sql: exit 0 = no blocking finding; exit 1 = findings printed, do not update.
# Usage: bash precheck.sh [database]   (default artdubati_test)
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB="${1:-artdubati_test}"
PSQL=(docker exec -i odoo_db psql -U odoo -d "$DB" -At -F ' | ' -v ON_ERROR_STOP=1)
[ -f "$DIR/precheck.sql" ] || { echo "precheck.sql not found next to $0"; exit 2; }
echo "Investor accounts (login | home action | profile), information:"
"${PSQL[@]}" < "$DIR/info.sql"
if [ "$("${PSQL[@]}" -c "SELECT to_regclass('ir_ui_menu_excluded_group_rel') IS NOT NULL")" = t ]; then
  echo "Menus hidden by base_menu_visibility_restriction (menu | group), information:"
  "${PSQL[@]}" < "$DIR/menus.sql"
fi
echo
OUT=$("${PSQL[@]}" < "$DIR/precheck.sql")
if [ -n "$OUT" ]; then
  echo "PRECHECK FAILED on $DB (check | id | detail):"
  echo "$OUT"
  echo "forbidden_group: remove those rights from the investor account (Settings → Users),"
  echo "nothing is removed automatically. home_record_duplicate: send it to Claude."
  exit 1
fi
echo "PRECHECK OK: no blocking finding on $DB"

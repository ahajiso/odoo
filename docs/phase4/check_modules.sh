#!/usr/bin/env bash
# Compares the modules installed on artdubati_test with docs/phase4/modules.txt, the
# modules (name and version) of the local database that ran the phase 4 tests. Any
# difference fails (audit of 86cf4ac..beacfeb: a count of 122 does not prove the same
# modules). Read-only.
#
# Usage: bash check_modules.sh <before|after> [modules.txt]
#   before: the two updated modules must still be at their deployed versions
#           (lartdubati_investor_home 18.0.2.0.0, maintenance_shareholder_equipment
#           18.0.4.0.0); every other module exactly as in modules.txt;
#   after:  every module exactly as in modules.txt.
# Also prints, for the record, the image of odoo_web and its Odoo version.
set -euo pipefail

MODE=${1:-}
EXPECTED_FILE=${2:-$(dirname "$0")/modules.txt}
DB=${DB:-artdubati_test}
[ "$MODE" = before ] || [ "$MODE" = after ] || { echo "Usage: check_modules.sh <before|after>"; exit 1; }
[ -s "$EXPECTED_FILE" ] || { echo "$EXPECTED_FILE missing"; exit 1; }

EXPECTED=$(mktemp)
ACTUAL=$(mktemp)
trap 'rm -f "$EXPECTED" "$ACTUAL"' EXIT
grep -v '^#' "$EXPECTED_FILE" | sed '/^$/d' | sort > "$EXPECTED"
if [ "$MODE" = before ]; then
  sed -i -e 's/^lartdubati_investor_home .*/lartdubati_investor_home 18.0.2.0.0/' \
         -e 's/^maintenance_shareholder_equipment .*/maintenance_shareholder_equipment 18.0.4.0.0/' \
         "$EXPECTED"
fi
docker exec -i odoo_db psql -U odoo -d "$DB" -At -F ' ' -v ON_ERROR_STOP=1 -c \
  "select name, latest_version from ir_module_module where state = 'installed' order by name" \
  | sort > "$ACTUAL"

echo "odoo_web image: $(docker inspect -f '{{.Image}}' odoo_web 2>/dev/null || echo '?')"
echo "Odoo: $(docker exec odoo_web odoo --version 2>/dev/null || echo '?')"
echo "installed on $DB: $(wc -l < "$ACTUAL"), expected: $(wc -l < "$EXPECTED")"
if diff -u --label expected --label "$DB" "$EXPECTED" "$ACTUAL"; then
  echo "MODULES OK ($MODE): $DB has exactly the tested modules and versions."
else
  echo "MODULES DIFFER ($MODE): lines « - » expected only, « + » on $DB only. Send this to Claude; do not deploy."
  exit 1
fi

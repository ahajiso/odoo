#!/usr/bin/env bash
# Checks that artdubati_test runs exactly the platform phase 4 was tested on
# (platform_expected.txt): the Docker image of odoo_web, the Odoo version, and the code
# of every installed module (SHA-256 of its files, platform.py), name and version
# included. Any difference fails (audits of 86cf4ac..beacfeb and d8d5b22..c3670fe: a
# count or a version does not prove the same code). Read-only; odoo_web must be running.
#
# Usage: bash check_modules.sh <before|after>
#   before: the two updated modules must still have their current code (MODULE lines);
#   after:  they must have the code of phase 4 (AFTER lines); every other module the same.
# What it cannot verify is said in the header of platform_expected.txt.
set -euo pipefail

MODE=${1:-}
HERE=$(cd "$(dirname "$0")" && pwd)
EXPECTED_FILE=${EXPECTED_FILE:-$HERE/platform_expected.txt}
DB=${DB:-artdubati_test}
[ "$MODE" = before ] || [ "$MODE" = after ] || { echo "Usage: check_modules.sh <before|after>"; exit 1; }
[ -s "$EXPECTED_FILE" ] || { echo "$EXPECTED_FILE missing"; exit 1; }
[ -s "$HERE/platform.py" ] || { echo "$HERE/platform.py missing"; exit 1; }

EXPECTED=$(mktemp)
ACTUAL=$(mktemp)
trap 'rm -f "$EXPECTED" "$ACTUAL"' EXIT
FAILED=0
expect() { sed -n "s/^$1=//p" "$EXPECTED_FILE"; }

IMAGE_EXPECTED=$(expect IMAGE_ID)
IMAGE_ACTUAL=$(docker inspect -f '{{.Image}}' odoo_web)
if [ "$IMAGE_ACTUAL" = "$IMAGE_EXPECTED" ]; then
  echo "image OK: $IMAGE_ACTUAL"
else
  echo "IMAGE DIFFERS: expected $IMAGE_EXPECTED, odoo_web runs $IMAGE_ACTUAL"; FAILED=1
fi
VERSION_EXPECTED=$(expect ODOO_VERSION)
VERSION_ACTUAL=$(docker exec odoo_web odoo --version)
if [ "$VERSION_ACTUAL" = "$VERSION_EXPECTED" ]; then
  echo "Odoo OK: $VERSION_ACTUAL"
else
  echo "ODOO VERSION DIFFERS: expected « $VERSION_EXPECTED », found « $VERSION_ACTUAL »"; FAILED=1
fi

# expected modules: the MODULE lines, the AFTER lines replacing them after the update
awk -v mode="$MODE" '
  $1 == "MODULE" { line[$2] = $2 " " $3 " " $4 }
  $1 == "AFTER" { after[$2] = $2 " " $3 " " $4 }
  END { for (m in line) print (mode == "after" && (m in after)) ? after[m] : line[m] }
' "$EXPECTED_FILE" | LC_ALL=C sort > "$EXPECTED"
docker exec -i odoo_web odoo shell -d "$DB" --no-http < "$HERE/platform.py" 2>/dev/null \
  | awk '$1 == "MODULE" { print $2, $3, $4 }' | LC_ALL=C sort > "$ACTUAL"
echo "modules installed on $DB: $(wc -l < "$ACTUAL"), expected: $(wc -l < "$EXPECTED")"
if diff -u --label expected --label "$DB" "$EXPECTED" "$ACTUAL"; then
  echo "modules OK: same names, versions and code"
else
  echo "MODULES DIFFER: lines « - » expected only, « + » on $DB only"; FAILED=1
fi

if [ "$FAILED" = 0 ]; then
  echo "PLATFORM OK ($MODE): $DB runs exactly the tested platform."
else
  echo "PLATFORM DIFFERS ($MODE): send this to Claude; do not deploy."
  exit 1
fi

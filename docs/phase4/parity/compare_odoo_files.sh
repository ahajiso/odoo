#!/usr/bin/env bash
# File-by-file comparison of 9 Odoo modules between the server's image and the Odoo
# source of the local tests (branch 18.0 at 6ba80ed1), audit of 7197751..b9979b9.
# The other 113 modules have the same code fingerprint on both sides
# (platform_server_20261010.txt and platform_local.txt, compared by check_parity.sh).
# Read-only. Run on the server:
#
#   bash compare_odoo_files.sh > /opt/odoo/logs/phase4_odoo_files_report.txt
#
# The report lists every file: identical, different (images apart from other files),
# missing on the server, present only on the server; it ends with the counts.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
EXPECTED="$HERE/odoo_6ba80ed1_9modules.sha256"
ADDONS=/usr/lib/python3/dist-packages/odoo/addons
MODULES="account barcodes base board mail payment product sale_management web"
IMAGE='\.(png|jpg|jpeg|gif|svg|ico|webp)$'
export LC_ALL=C
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# the server's files and checksums, same format as the expected list
docker exec odoo_web sh -c "cd $ADDONS && find $MODULES -type f ! -name '*.pyc' | LC_ALL=C sort \
  | while IFS= read -r f; do sha256sum \"\$f\"; done" > "$WORK/server.sha256"
sort -k2 "$EXPECTED" > "$WORK/local.sha256"
sort -k2 "$WORK/server.sha256" > "$WORK/server.sorted"
cut -c67- "$WORK/local.sha256" > "$WORK/local.files"
cut -c67- "$WORK/server.sorted" > "$WORK/server.files"

join -1 2 -2 2 -o 0,1.1,2.1 "$WORK/local.sha256" "$WORK/server.sorted" > "$WORK/both"
awk '$2 == $3 {print $1}' "$WORK/both" > "$WORK/identical"
awk '$2 != $3 {print $1}' "$WORK/both" > "$WORK/different"
grep -E "$IMAGE" "$WORK/different" > "$WORK/different_images" || true
grep -vE "$IMAGE" "$WORK/different" > "$WORK/different_other" || true
comm -23 "$WORK/local.files" "$WORK/server.files" > "$WORK/missing_on_server"
comm -13 "$WORK/local.files" "$WORK/server.files" > "$WORK/only_on_server"

echo "# Odoo files: server image $(docker inspect -f '{{.Image}}' odoo_web) ($(docker exec odoo_web odoo --version))"
echo "# compared with branch 18.0 at 6ba80ed1, modules: $MODULES"
for part in different_other missing_on_server only_on_server different_images; do
  echo "## $part ($(wc -l < "$WORK/$part"))"
  cat "$WORK/$part"
done
echo "## identical ($(wc -l < "$WORK/identical")): not listed"
echo "COUNTS identical=$(wc -l < "$WORK/identical") different_images=$(wc -l < "$WORK/different_images") different_other=$(wc -l < "$WORK/different_other") missing_on_server=$(wc -l < "$WORK/missing_on_server") only_on_server=$(wc -l < "$WORK/only_on_server")"

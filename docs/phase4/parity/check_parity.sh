#!/usr/bin/env bash
# Reproducible proof of the code parity between the server and the local tests (audits of
# 7197751..b9979b9 and 4c6d12e..aebe0aa), from the files of this folder only:
# - platform_server_20261010.txt: platform.py run on artdubati_test (10/10/2026, before
#   the phase 4 update);
# - platform_local.txt: platform.py run on the local test database (Odoo 6ba80ed1, the
#   server's OCA commits, phase 4 code);
# - odoo_files_report_20261010.txt: compare_odoo_files.sh run on the server.
# 1. the sets of modules (name and version) must be equal, except the versions of the
#    two phase 4 modules (before / after the update);
# 2. among them, the code fingerprints must be equal, except the two phase 4 modules
#    (new code) and the nine Odoo modules of the file report;
# 3. the file report must show no difference other than images, and only font files
#    with their licences missing from the image.
# Usage: bash check_parity.sh [folder]   (default: the folder of this script)
set -euo pipefail
cd "${1:-$(dirname "$0")}"
export LC_ALL=C
SERVER=platform_server_20261010.txt
LOCAL=platform_local.txt
REPORT=odoo_files_report_20261010.txt
fail() { echo "PARITY FAILED: $*"; exit 1; }
for f in "$SERVER" "$LOCAL" "$REPORT"; do [ -s "$f" ] || fail "$f missing"; done

# 1. same modules, same versions, the two expected version changes apart
EXPECTED_VERSION_DIFF="-lartdubati_investor_home 18.0.2.0.0
-maintenance_shareholder_equipment 18.0.4.0.0
+lartdubati_investor_home 18.0.3.0.0
+maintenance_shareholder_equipment 18.0.4.0.1"
VERSION_DIFF=$( { comm -23 <(awk '$1 == "MODULE" {print $2, $3}' "$SERVER" | sort) \
                           <(awk '$1 == "MODULE" {print $2, $3}' "$LOCAL" | sort) | sed 's/^/-/'
                  comm -13 <(awk '$1 == "MODULE" {print $2, $3}' "$SERVER" | sort) \
                           <(awk '$1 == "MODULE" {print $2, $3}' "$LOCAL" | sort) | sed 's/^/+/'; } )
echo "modules: $(grep -c '^MODULE ' "$SERVER") on the server, $(grep -c '^MODULE ' "$LOCAL") locally"
[ "$VERSION_DIFF" = "$EXPECTED_VERSION_DIFF" ] || {
  echo "name / version differences (- server only, + local only):"; echo "$VERSION_DIFF"
  fail "the sets of modules differ beyond the two phase 4 versions"; }
echo "same modules and versions, the two phase 4 modules apart"

# 2. code fingerprints of the (now identical) set of modules
DIFF=$(join <(awk '$1 == "MODULE" {print $2, $4}' "$SERVER" | sort) \
            <(awk '$1 == "MODULE" {print $2, $4}' "$LOCAL" | sort) | awk '$2 != $3 {print $1}')
echo "code fingerprint differs for: $(echo $DIFF)"
EXPECTED="account barcodes base board lartdubati_investor_home mail maintenance_shareholder_equipment payment product sale_management web"
[ "$(echo $DIFF)" = "$EXPECTED" ] || fail "fingerprints differ for other modules than expected"

# 3. what differs inside the nine Odoo modules
COUNTS=$(grep '^COUNTS ' "$REPORT")
echo "file report: $COUNTS"
case "$COUNTS" in
  *" different_other=0 "*" only_on_server=0") ;;
  *) fail "differences other than images in the file report";;
esac
OTHER_MISSING=$(sed -n '/^## missing_on_server/,/^## /p' "$REPORT" \
  | grep -v '^## ' | grep -vE '^web/static/fonts/google/[^/]+/([^/]+\.ttf|LICENSE\.txt)$' || true)
[ -z "$OTHER_MISSING" ] || fail "missing files other than fonts: $OTHER_MISSING"
echo "PARITY OK: same modules and code; apart from the phase 4 modules, only images (recompressed in the image) and font files with their licences (absent from the image) differ."

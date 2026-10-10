#!/usr/bin/env bash
# Reproducible proof of the code parity between the server and the local tests (audit of
# 7197751..b9979b9), from the files of this folder only:
# - platform_server_20261010.txt: platform.py run on artdubati_test (10/10/2026, before
#   the phase 4 update);
# - platform_local.txt: platform.py run on the local test database (Odoo 6ba80ed1, the
#   server's OCA commits, phase 4 code);
# - odoo_files_report_20261010.txt: compare_odoo_files.sh run on the server.
# It prints the modules whose code fingerprint differs and checks that they are only
# the two phase 4 modules (new code) and the nine Odoo modules of the file report, whose
# only differences are images (and the files the report lists as missing).
set -euo pipefail
cd "$(dirname "$0")"
export LC_ALL=C
DIFF=$(join <(awk '{print $2, $4}' platform_server_20261010.txt | sort) \
            <(awk '{print $2, $4}' platform_local.txt | sort) | awk '$2 != $3 {print $1}')
echo "modules: $(wc -l < platform_server_20261010.txt) on the server, $(wc -l < platform_local.txt) locally"
echo "code fingerprint differs for: $(echo $DIFF)"
EXPECTED="account barcodes base board lartdubati_investor_home mail maintenance_shareholder_equipment payment product sale_management web"
[ "$(echo $DIFF)" = "$EXPECTED" ] || { echo "PARITY FAILED: other modules differ"; exit 1; }
[ -s odoo_files_report_20261010.txt ] || { echo "PARITY INCOMPLETE: file report of the server missing"; exit 1; }
COUNTS=$(grep '^COUNTS ' odoo_files_report_20261010.txt)
echo "file report: $COUNTS"
case "$COUNTS" in
  *" different_other=0 "*" only_on_server=0") ;;
  *) echo "PARITY FAILED: differences other than images in the file report"; exit 1;;
esac
echo "PARITY OK: same code except the phase 4 modules, images and the files listed as missing on the server."

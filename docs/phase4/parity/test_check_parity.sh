#!/usr/bin/env bash
# Test of check_parity.sh: it must pass on the committed files and fail on each mutation
# (audit of 4c6d12e..aebe0aa). Each case works on a temporary copy of this folder.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
FAILURES=0

run_case() {  # run_case <name> <expected: ok|fail> <mutation, a shell command run in the copy>
  local name=$1 expected=$2 mutation=$3 work result
  work=$(mktemp -d)
  cp "$HERE"/*.txt "$HERE"/check_parity.sh "$work"/
  (cd "$work" && eval "$mutation")
  if bash "$work/check_parity.sh" "$work" > "$work/out" 2>&1; then result=ok; else result=fail; fi
  if [ "$result" = "$expected" ]; then
    echo "PASS  $name ($result)"
  else
    echo "FAIL  $name: expected $expected, got $result"; sed 's/^/      /' "$work/out"
    FAILURES=$((FAILURES + 1))
  fi
  rm -rf "$work"
}

run_case "committed files" ok ":"
run_case "a module replaced by another (122 lines kept)" fail \
  "sed -i 's/^MODULE account_add_gln /MODULE bogus_module /' platform_local.txt"
run_case "a module missing locally" fail "sed -i '/^MODULE account_add_gln /d' platform_local.txt"
run_case "an extra module locally" fail \
  "echo 'MODULE bogus_module 18.0.1.0 0000 /x' >> platform_local.txt"
run_case "another version of a module" fail \
  "sed -i 's/^MODULE contract 18.0.2.5.3 /MODULE contract 18.0.2.5.4 /' platform_local.txt"
run_case "a phase 4 module not updated locally" fail \
  "sed -i 's/^MODULE maintenance_shareholder_equipment 18.0.4.0.1 /MODULE maintenance_shareholder_equipment 18.0.4.0.0 /' platform_local.txt"
run_case "other code in a module" fail \
  "sed -i 's/^\\(MODULE contract 18.0.2.5.3 \\)[0-9a-f]*/\\10000/' platform_local.txt"
run_case "a code file different in the report" fail \
  "sed -i 's/different_other=0/different_other=1/' odoo_files_report_20261010.txt"
run_case "a non-font file missing on the server" fail \
  "sed -i 's#^web/static/fonts/google/Roboto/Roboto-Thin.ttf\$#web/static/src/core/l10n/dates.js#' odoo_files_report_20261010.txt"
run_case "file report missing" fail "rm odoo_files_report_20261010.txt"

[ "$FAILURES" = 0 ] && echo "ALL CASES PASSED" || { echo "$FAILURES CASE(S) FAILED"; exit 1; }

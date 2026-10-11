#!/usr/bin/env bash
# ROADMAP section 0, item 3: LOCAL proof that the stop rules refuse the commit (audit
# of 9c407ae). Each mutation starts from a copy of an UPDATED, NOT migrated database
# (18.0.5.0.0 on the seeded inventory), changes one thing, runs
# `run_migration.sh --apply` and requires: the launcher FAILS, the expected ERROR line
# is printed, and nothing was committed (no external ID roadmap0.*, or, for the
# migrated database, the mutated record unchanged).
#
# Usage: bash mutations.sh <updated, not migrated database>     (never on the server)
# Environment: DEVENV, OUT (logs).
set -euo pipefail
BASE=${1:?updated database (copied, never changed)}
DEVENV=${DEVENV:-/home/user/devenv}
OUT=${OUT:?directory for the logs}
HERE=$(cd "$(dirname "$0")/.." && pwd)
PSQL="psql -h /tmp -p 5433 -U root -At"
DB=r0mut
SHELL_CMD="$DEVENV/venv/bin/python $DEVENV/odoo/odoo-bin shell -c $DEVENV/odoo_srv2.conf -d $DB --no-http"
FAILED=0
mkdir -p "$OUT"

fresh() {
  dropdb -h /tmp -p 5433 -U root --if-exists "$DB"
  rm -rf "$DEVENV/data/filestore/$DB"
  createdb -h /tmp -p 5433 -U root -T "$BASE" "$DB"
  cp -r "$DEVENV/data/filestore/$BASE" "$DEVENV/data/filestore/$DB"
}
mutate() {  # python run in the Odoo shell (superuser), committed
  printf '%s\nenv.cr.commit()\nprint("MUTATED")\n' "$1" | $SHELL_CMD 2>&1 | grep -q '^MUTATED' \
    || { echo "  could not apply the mutation"; exit 1; }
}
migrate() {  # $1 = --apply or empty; output kept in $OUT/<name>.txt
  env ROADMAP0_REHEARSAL=1 LOGDIR="$OUT/$NAME" ODOO_SHELL="$SHELL_CMD" \
    bash "$HERE/run_migration.sh" $1 > "$OUT/$NAME.txt" 2>&1
}
expect_refused() {  # $1 = expected ERROR text, $2 = SQL that must return 0
  if migrate --apply; then
    echo "  NOT REFUSED: the launcher accepted the run"; FAILED=1; return
  fi
  local last  # the newest apply output (the « migrated » case has two)
  last=$(ls -t "$OUT/$NAME/"roadmap0_migration_apply_2*.txt | head -1)
  grep -q "^ERROR | .*$1" "$last" \
    || { echo "  expected ERROR « $1 » not printed"; FAILED=1; return; }
  local left
  left=$($PSQL -d "$DB" -c "$2")
  [ "$left" = 0 ] || { echo "  COMMITTED: $2 -> $left"; FAILED=1; return; }
  echo "  refused, nothing committed: $(grep -m1 "^ERROR | .*$1" "$last")"
  grep -E "^MIGRATION FAILED" "$OUT/$NAME.txt" | sed 's/^/  /'
}
NOT_MIGRATED="select count(*) from ir_model_data where module = 'roadmap0'"

NAME=kept; echo "== $NAME: a draft bill of « Computer » (to archive) -> KEPT"
fresh
mutate "p = env['product.template'].search([('name', '=', 'Computer')])
env['account.move'].create({'move_type': 'in_invoice', 'partner_id': env['res.partner'].search([('name', '=', 'Manager')]).id,
  'invoice_line_ids': [(0, 0, {'product_id': p.product_variant_id.id, 'quantity': 1, 'price_unit': 5})]})"
expect_refused "KEPT: product Computer" "$NOT_MIGRATED"

NAME=blocked; echo "== $NAME: a draft bill of the table saw (maintainable, no default category) -> BLOCKED"
fresh
mutate "p = env['product.template'].search([('name', 'like', '1800W corded table saw')])
env['account.move'].create({'move_type': 'in_invoice', 'partner_id': env['res.partner'].search([('name', '=', 'Manager')]).id,
  'invoice_line_ids': [(0, 0, {'product_id': p.product_variant_id.id, 'quantity': 1, 'price_unit': 5})]})"
expect_refused "BLOCKED: draft bill" "$NOT_MIGRATED"

NAME=count; echo "== $NAME: the tag « Insurance » already exists -> M7=7, not 8"
fresh
mutate "env['contract.tag'].create({'name': 'Insurance'})"
expect_refused "M7: 7 change(s), expected 8" "$NOT_MIGRATED"

NAME=contract; echo "== $NAME: a second line on « TEST Scaffold rental » -> contract differs"
fresh
mutate "c = env['contract.contract'].search([('name', '=', 'TEST Scaffold rental')])
p = env['product.template'].search([('name', '=', 'Location de matériel (payée)')])
c.write({'contract_line_ids': [(0, 0, {'product_id': p.product_variant_id.id, 'name': 'extra', 'quantity': 1,
  'price_unit': 10, 'recurring_rule_type': 'monthly', 'recurring_interval': 1, 'date_start': '2026-10-01'})]})"
expect_refused "contract TEST Scaffold rental .* differs from the inventory: 2 lines" "$NOT_MIGRATED"

NAME=interval; echo "== $NAME: « TEST Scaffold rental » every 2 months -> contract differs"
fresh
mutate "env['contract.contract'].search([('name', '=', 'TEST Scaffold rental')]).contract_line_ids.recurring_interval = 2"
expect_refused "contract TEST Scaffold rental .* differs from the inventory: line .*: every 2 monthly" \
  "select count(*) from contract_line l join contract_contract c on c.id = l.contract_id
    where c.name = 'TEST Scaffold rental' and (not c.active or l.recurring_interval <> 2)"

NAME=migrated; echo "== $NAME: migrated, then « Computer » unarchived -> 1 change on a migrated database"
fresh
env ROADMAP0_REHEARSAL=1 LOGDIR="$OUT/$NAME" ODOO_SHELL="$SHELL_CMD" bash "$HERE/run_migration.sh" --apply \
  > "$OUT/$NAME.first.txt" 2>&1 || { echo "  the first --apply failed"; exit 1; }
mutate "env['product.template'].with_context(active_test=False).search([('name', '=', 'Computer')]).active = True"
expect_refused "M5: 1 change(s), expected 0" \
  "select count(*) from product_template where name->>'en_US' = 'Computer' and not active"

[ "$FAILED" = 0 ] && echo "MUTATIONS OK: every mutation refused, nothing committed" \
  || { echo "MUTATIONS FAILED"; exit 1; }

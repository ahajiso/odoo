#!/usr/bin/env bash
# Backup of artdubati_test (database and filestore) before a deployment, checked before
# it is published (audit of 86cf4ac..beacfeb, after the rollback of 10/10/2026 that
# dropped the database with an empty backup path).
#
# Usage: bash backup_db.sh <label, e.g. phase4>
#
# 1. odoo_web stopped, the database is dumped and the filestore archived (through a
#    temporary container with odoo_web's volumes) under temporary names, then odoo_web
#    is started again;
# 2. the dump is read back (pg_restore --list), then restored COMPLETELY into a
#    temporary database whose installed modules (name, version) and record counts are
#    compared with the live database; the temporary database is dropped;
# 3. the archive is listed (tar -tzf), its number of files compared with the filestore
#    at capture time, and every file the dump's attachments point to looked for in it;
# 4. only then the files get their final names, with their SHA-256, and the manifest
#    $LOGDIR/<label>_backup is written, last. restore_db.sh and deploy_modules.sh read it.
# Any failure stops the script and leaves no manifest: nothing can point to a bad backup.
# Read-only for artdubati_test. odoo_web is STOPPED during the capture (database and
# filestore at the same moment, a few minutes) and started again whatever happens.
set -euo pipefail
umask 077

LABEL=${1:-}
[[ "$LABEL" =~ ^[a-z0-9_]+$ ]] || { echo "Give a label (letters, digits, _), e.g. phase4."; exit 1; }
DB=${DB:-artdubati_test}
BACKUPDIR=${BACKUPDIR:-/opt/odoo/backups}
LOGDIR=${LOGDIR:-/opt/odoo/logs}
FS=${FS:-/var/lib/odoo/.local/share/Odoo/filestore}
ADDONS=${ADDONS:-/opt/odoo/addons/custom}
STAMP=$(date +%Y%m%d_%H%M%S)
BASE="$BACKUPDIR/${DB}_${STAMP}_${LABEL}"
DUMP="$BASE.dump"
TGZ="$BASE.filestore.tar.gz"
MANIFEST="$LOGDIR/${LABEL}_backup"
VERIFY_DB="${DB}_verify_${STAMP}"

mkdir -p "$BACKUPDIR" "$LOGDIR"
# an earlier manifest of this label is set aside first: after a failure, none is left
[ ! -e "$MANIFEST" ] || mv "$MANIFEST" "$MANIFEST.replaced_$STAMP"

cleanup() {
  rm -f "$DUMP.partial" "$TGZ.partial" "$DUMP.list" "$TGZ.list"
  docker exec odoo_db dropdb -U odoo --if-exists "$VERIFY_DB" > /dev/null 2>&1 || true
}
step() { echo "== $*"; }
sql() {  # sql <database> <query>: one value per line
  docker exec -i odoo_db psql -U odoo -d "$1" -Atq -v ON_ERROR_STOP=1 -c "$2"
}
# what must be identical in the dump and in the live database
FINGERPRINT_SQL="select md5(string_agg(name || ' ' || coalesce(latest_version, ''), ',' order by name))
  from ir_module_module where state = 'installed'"
COUNT_SQL="select (select count(*) from res_users) || ' ' || (select count(*) from res_partner)
  || ' ' || (select count(*) from maintenance_equipment) || ' ' || (select count(*) from stock_quant)
  || ' ' || (select count(*) from account_move) || ' ' || (select count(*) from ir_attachment)"

step "checks"
sql "$DB" "select 1" > /dev/null
[ -z "$(git -C "$ADDONS" status --porcelain --untracked-files=no)" ] || {
  echo "Local changes in $ADDONS: nothing done, send them to Claude."; exit 1; }
COMMIT=$(git -C "$ADDONS" rev-parse HEAD)
IMG=$(docker inspect -f '{{.Config.Image}}' odoo_web)
IMAGE_ID=$(docker inspect -f '{{.Image}}' odoo_web)
[ -n "$IMG" ] || { echo "Cannot read the image of odoo_web."; exit 1; }
WAS_RUNNING=$(docker inspect -f '{{.State.Running}}' odoo_web)

# odoo_web is stopped while the database and the filestore are captured, so that both
# show the same moment (audit of 796fba5..c3670fe); it is started again whatever
# happens (trap), if it was running
STOPPED_BY_US=false
restart_odoo() {
  if [ "$STOPPED_BY_US" = true ]; then
    docker start odoo_web > /dev/null && echo "odoo_web started again." \
      || echo "WARNING: docker start odoo_web failed: start it by hand."
    STOPPED_BY_US=false
  fi
}
trap 'restart_odoo; cleanup' EXIT
in_volume() {  # a command run next to odoo_web's volumes (filestore), odoo_web stopped
  docker run --rm --volumes-from odoo_web --entrypoint "$1" "$IMG" "${@:2}"
}

step "stopping odoo_web (a few minutes, every database unavailable)"
if [ "$WAS_RUNNING" = true ]; then
  docker stop odoo_web > /dev/null
  STOPPED_BY_US=true
fi
[ "$(docker inspect -f '{{.State.Running}}' odoo_web)" = "false" ] || {
  echo "odoo_web still running."; exit 1; }
in_volume test -d "$FS/$DB" || { echo "Filestore $FS/$DB not found."; exit 1; }

step "capture: state of $DB, database dump, filestore archive (odoo_web stopped)"
LIVE_MODULES=$(sql "$DB" "$FINGERPRINT_SQL")
LIVE_COUNTS=$(sql "$DB" "$COUNT_SQL")
LIVE_FILES=$(in_volume find "$FS/$DB" -type f | wc -l)
docker exec odoo_db pg_dump -U odoo -Fc "$DB" > "$DUMP.partial"
[ -s "$DUMP.partial" ] || { echo "Empty dump."; exit 1; }
in_volume tar -czf - -C "$FS" "$DB" > "$TGZ.partial"
[ -s "$TGZ.partial" ] || { echo "Empty filestore archive."; exit 1; }
restart_odoo

step "dump readable (pg_restore --list)"
# listings go through a file: with pipefail, « grep -q » closing the pipe early would
# make tar or pg_restore fail
docker exec -i odoo_db pg_restore --list < "$DUMP.partial" > "$DUMP.list"
grep -q "TABLE DATA public ir_module_module " "$DUMP.list" || {
  echo "The dump has no ir_module_module data."; exit 1; }
rm -f "$DUMP.list"

step "complete restore into the temporary database $VERIFY_DB"
docker exec odoo_db createdb -U odoo "$VERIFY_DB"
docker exec -i odoo_db pg_restore -U odoo -d "$VERIFY_DB" --no-owner < "$DUMP.partial"
DUMP_MODULES=$(sql "$VERIFY_DB" "$FINGERPRINT_SQL")
DUMP_COUNTS=$(sql "$VERIFY_DB" "$COUNT_SQL")
[ "$LIVE_MODULES" = "$DUMP_MODULES" ] || {
  echo "Installed modules differ between the captured state and the restored dump."; exit 1; }
[ "$LIVE_COUNTS" = "$DUMP_COUNTS" ] || {
  echo "Record counts differ: captured $LIVE_COUNTS, restored $DUMP_COUNTS."; exit 1; }
echo "restored copy identical: modules $DUMP_MODULES, counts $DUMP_COUNTS"
ATTACHMENT_FILES=$(sql "$VERIFY_DB" "select distinct store_fname from ir_attachment
  where store_fname is not null and store_fname <> '' order by 1")

step "filestore archive readable and complete"
tar -tzf "$TGZ.partial" > "$TGZ.list"
ARCHIVE_FILES=$(grep -c -v '/$' "$TGZ.list" || true)
[ "$ARCHIVE_FILES" -eq "$LIVE_FILES" ] || {
  echo "Archive has $ARCHIVE_FILES files, the filestore had $LIVE_FILES."; exit 1; }
grep -q "^$DB/" "$TGZ.list" || { echo "Archive does not hold $DB/."; exit 1; }
# every file the attachments of the dump point to must be in the archive (captured at
# the same moment); missing ones already were before the backup: listed, kept in the
# manifest, sent to Claude
MISSING=0
while IFS= read -r fname; do
  [ -n "$fname" ] || continue
  grep -qxF "$DB/$fname" "$TGZ.list" || { MISSING=$((MISSING + 1)); echo "  attachment file missing: $fname"; }
done <<< "$ATTACHMENT_FILES"
echo "archive readable: $ARCHIVE_FILES files; attachment files missing: $MISSING"
rm -f "$TGZ.list"
docker exec odoo_db dropdb -U odoo "$VERIFY_DB"

step "publish"
mv "$DUMP.partial" "$DUMP"
mv "$TGZ.partial" "$TGZ"
DUMP_SHA=$(sha256sum "$DUMP" | cut -d' ' -f1)
TGZ_SHA=$(sha256sum "$TGZ" | cut -d' ' -f1)
echo "$COMMIT" > "$LOGDIR/${LABEL}_previous_commit"
cat > "$MANIFEST.tmp" <<EOF
DB=$DB
DUMP=$DUMP
DUMP_SHA256=$DUMP_SHA
FILESTORE=$TGZ
FILESTORE_SHA256=$TGZ_SHA
FILESTORE_FILES=$ARCHIVE_FILES
ATTACHMENT_FILES_MISSING=$MISSING
MODULES_MD5=$DUMP_MODULES
COUNTS=$DUMP_COUNTS
COMMIT=$COMMIT
IMAGE_ID=$IMAGE_ID
STAMP=$STAMP
EOF
mv "$MANIFEST.tmp" "$MANIFEST"
ls -l "$DUMP" "$TGZ"
echo "BACKUP OK: $MANIFEST"
cat "$MANIFEST"

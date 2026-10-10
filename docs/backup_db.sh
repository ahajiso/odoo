#!/usr/bin/env bash
# Backup of artdubati_test (database and filestore) before a deployment, checked before
# it is published (audit of 86cf4ac..beacfeb, after the rollback of 10/10/2026 that
# dropped the database with an empty backup path).
#
# Usage: bash backup_db.sh <label, e.g. phase4>
#
# 1. the database is dumped and the filestore archived under temporary names;
# 2. the dump is read back (pg_restore --list), then restored COMPLETELY into a
#    temporary database whose installed modules (name, version) and record counts are
#    compared with the live database; the temporary database is dropped;
# 3. the archive is listed (tar -tzf) and its number of files compared with the live
#    filestore;
# 4. only then the files get their final names, with their SHA-256, and the manifest
#    $LOGDIR/<label>_backup is written, last. restore_db.sh and deploy_modules.sh read it.
# Any failure stops the script and leaves no manifest: nothing can point to a bad backup.
# Read-only for artdubati_test; odoo_web keeps running.
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
trap cleanup EXIT
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
[ "$(docker inspect -f '{{.State.Running}}' odoo_web)" = "true" ] || {
  echo "odoo_web must be running (the filestore is read through it)."; exit 1; }
sql "$DB" "select 1" > /dev/null
docker exec odoo_web test -d "$FS/$DB" || { echo "Filestore $FS/$DB not found in odoo_web."; exit 1; }
COMMIT=$(git -C "$ADDONS" rev-parse HEAD)

step "database dump"
docker exec odoo_db pg_dump -U odoo -Fc "$DB" > "$DUMP.partial"
[ -s "$DUMP.partial" ] || { echo "Empty dump."; exit 1; }

step "dump readable (pg_restore --list)"
docker exec -i odoo_db pg_restore --list < "$DUMP.partial" > "$DUMP.list"
grep -q "TABLE DATA public ir_module_module " "$DUMP.list" || {
  echo "The dump has no ir_module_module data."; exit 1; }
rm -f "$DUMP.list"

step "complete restore into the temporary database $VERIFY_DB"
docker exec odoo_db createdb -U odoo "$VERIFY_DB"
docker exec -i odoo_db pg_restore -U odoo -d "$VERIFY_DB" --no-owner < "$DUMP.partial"
LIVE_MODULES=$(sql "$DB" "$FINGERPRINT_SQL")
DUMP_MODULES=$(sql "$VERIFY_DB" "$FINGERPRINT_SQL")
[ "$LIVE_MODULES" = "$DUMP_MODULES" ] || {
  echo "Installed modules differ between the database and its restored dump."; exit 1; }
LIVE_COUNTS=$(sql "$DB" "$COUNT_SQL")
DUMP_COUNTS=$(sql "$VERIFY_DB" "$COUNT_SQL")
[ "$LIVE_COUNTS" = "$DUMP_COUNTS" ] || {
  echo "Record counts differ: live $LIVE_COUNTS, restored $DUMP_COUNTS"
  echo "(someone may be working on $DB: run the backup again when it is quiet)."; exit 1; }
echo "restored copy identical: modules $DUMP_MODULES, counts $DUMP_COUNTS"
docker exec odoo_db dropdb -U odoo "$VERIFY_DB"

step "filestore archive"
LIVE_FILES=$(docker exec odoo_web find "$FS/$DB" -type f | wc -l)
docker exec odoo_web tar -czf - -C "$FS" "$DB" > "$TGZ.partial"
# listings go through a file: with pipefail, « grep -q » closing the pipe early would
# make tar or pg_restore fail
tar -tzf "$TGZ.partial" > "$TGZ.list"
ARCHIVE_FILES=$(grep -c -v '/$' "$TGZ.list" || true)
[ "$ARCHIVE_FILES" -eq "$LIVE_FILES" ] || {
  echo "Archive has $ARCHIVE_FILES files, the filestore $LIVE_FILES."; exit 1; }
grep -q "^$DB/" "$TGZ.list" || { echo "Archive does not hold $DB/."; exit 1; }
rm -f "$TGZ.list"
echo "archive readable: $ARCHIVE_FILES files"

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
MODULES_MD5=$DUMP_MODULES
COUNTS=$DUMP_COUNTS
COMMIT=$COMMIT
STAMP=$STAMP
EOF
mv "$MANIFEST.tmp" "$MANIFEST"
ls -l "$DUMP" "$TGZ"
echo "BACKUP OK: $MANIFEST"
cat "$MANIFEST"

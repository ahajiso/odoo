#!/usr/bin/env bash
# Rollback after a failed deployment: puts back the database, the filestore and the code
# of the backup made by backup_db.sh (audit of 86cf4ac..beacfeb).
#
# Usage: bash restore_db.sh <label, e.g. phase4>
#
# Nothing is changed before every check passed: manifest present, both files present
# with their SHA-256, dump readable (pg_restore --list), archive readable (tar -tzf)
# with the expected number of files, code commit known, working tree clean, enough disk
# space to keep the current database and filestore next to the restored ones.
# Then, odoo_web stopped:
# - the dump is restored into a new database; only when it succeeded and its modules and
#   record counts equal the backup's, the current database is RENAMED (kept, never dropped) <db>_before_restore_<stamp> and the new
#   one takes its name;
# - the filestore is extracted next to the current one; only when the number of files
#   extracted equals the backup's, the current one is renamed
#   <db>.before_restore_<stamp> (kept);
# - the code goes back to the commit of the backup;
# - odoo_web is started, the restored modules are compared with the backup.
# The kept database and filestore are removed later by hand, once everything is checked.
set -euo pipefail
umask 077

LABEL=${1:-}
[[ "$LABEL" =~ ^[a-z0-9_]+$ ]] || { echo "Give the label of the backup, e.g. phase4."; exit 1; }
LOGDIR=${LOGDIR:-/opt/odoo/logs}
FS=${FS:-/var/lib/odoo/.local/share/Odoo/filestore}
ADDONS=${ADDONS:-/opt/odoo/addons/custom}
MANIFEST="$LOGDIR/${LABEL}_backup"
STAMP=$(date +%Y%m%d_%H%M%S)

step() { echo "== $*"; }
stop() { echo "STOP: $*"; exit 1; }
value() {  # value <KEY>: from the manifest, never sourced
  local line
  line=$(grep -E "^$1=" "$MANIFEST" | head -1) || stop "$1 missing from $MANIFEST"
  [ -n "${line#*=}" ] || stop "$1 empty in $MANIFEST"
  printf '%s' "${line#*=}"
}
sql() {
  docker exec -i odoo_db psql -U odoo -d "$1" -Atq -v ON_ERROR_STOP=1 -c "$2"
}

step "checks (nothing is changed yet)"
[ -s "$MANIFEST" ] || stop "no backup manifest $MANIFEST: run backup_db.sh first; nothing done."
DB=$(value DB)
DUMP=$(value DUMP)
TGZ=$(value FILESTORE)
COMMIT=$(value COMMIT)
MODULES_MD5=$(value MODULES_MD5)
COUNTS=$(value COUNTS)
FILES=$(value FILESTORE_FILES)
[ -s "$DUMP" ] || stop "dump $DUMP missing or empty; nothing done."
[ -s "$TGZ" ] || stop "filestore archive $TGZ missing or empty; nothing done."
[ "$(sha256sum "$DUMP" | cut -d' ' -f1)" = "$(value DUMP_SHA256)" ] || stop "dump checksum differs; nothing done."
[ "$(sha256sum "$TGZ" | cut -d' ' -f1)" = "$(value FILESTORE_SHA256)" ] || stop "archive checksum differs; nothing done."
# listings through a file: with pipefail, « grep -q » closing the pipe early would fail
LIST=$(mktemp)
trap 'rm -f "$LIST"' EXIT
docker exec -i odoo_db pg_restore --list < "$DUMP" > "$LIST" || stop "dump not readable; nothing done."
grep -q "TABLE DATA public ir_module_module " "$LIST" || stop "dump without modules; nothing done."
tar -tzf "$TGZ" > "$LIST" || stop "archive not readable; nothing done."
[ "$(grep -c -v '/$' "$LIST" || true)" -eq "$FILES" ] || stop "archive incomplete; nothing done."
git -C "$ADDONS" rev-parse --verify --quiet "$COMMIT^{commit}" > /dev/null || stop "commit $COMMIT unknown; nothing done."
[ -z "$(git -C "$ADDONS" status --porcelain --untracked-files=no)" ] || stop "local changes in $ADDONS; nothing done."
NEW_DB="${DB}_restore_${STAMP}"
OLD_DB="${DB}_before_restore_${STAMP}"
IMG=$(docker inspect -f '{{.Config.Image}}' odoo_web)
[ -n "$IMG" ] || stop "cannot read the image of odoo_web; nothing done."
# disk space: the current database and filestore are kept next to the restored ones
DB_EXISTS=$(sql postgres "select count(*) from pg_database where datname = '$DB'")
DB_BYTES=0
[ "$DB_EXISTS" = 0 ] || DB_BYTES=$(sql "$DB" "select pg_database_size(current_database())")
PG_FREE_KB=$(docker exec odoo_db df -Pk /var/lib/postgresql/data | awk 'NR==2 {print $4}')
[ $((PG_FREE_KB * 1024)) -gt $((DB_BYTES * 2)) ] \
  || stop "not enough space for PostgreSQL: $((PG_FREE_KB / 1024)) MB free, the database takes $((DB_BYTES / 1048576)) MB; nothing done."
FS_FREE_KB=$(docker run --rm --volumes-from odoo_web --entrypoint df "$IMG" -Pk "$FS" | awk 'NR==2 {print $4}')
TGZ_BYTES=$(stat -c %s "$TGZ")
[ $((FS_FREE_KB * 1024)) -gt $((TGZ_BYTES * 3)) ] \
  || stop "not enough space for the filestore: $((FS_FREE_KB / 1024)) MB free; nothing done."
echo "backup: $DUMP, $TGZ ($FILES files), code $COMMIT"

step "stopping odoo_web"
docker stop odoo_web > /dev/null
[ "$(docker inspect -f '{{.State.Running}}' odoo_web)" = "false" ] || stop "odoo_web still running; nothing changed."

step "database: restore into $NEW_DB"
docker exec odoo_db createdb -U odoo "$NEW_DB"
docker exec -i odoo_db pg_restore -U odoo -d "$NEW_DB" --no-owner < "$DUMP" \
  || stop "restore into $NEW_DB failed; $DB untouched, odoo_web stopped. Send this to Claude."
[ "$(sql "$NEW_DB" "select md5(string_agg(name || ' ' || coalesce(latest_version, ''), ',' order by name)) from ir_module_module where state = 'installed'")" = "$MODULES_MD5" ] \
  || stop "restored modules differ from the backup; $DB untouched, odoo_web stopped. Send this to Claude."
RESTORED_COUNTS=$(sql "$NEW_DB" "select (select count(*) from res_users) || ' ' || (select count(*) from res_partner)
  || ' ' || (select count(*) from maintenance_equipment) || ' ' || (select count(*) from stock_quant)
  || ' ' || (select count(*) from account_move) || ' ' || (select count(*) from ir_attachment)")
[ "$RESTORED_COUNTS" = "$COUNTS" ] \
  || stop "restored counts $RESTORED_COUNTS differ from the backup's $COUNTS; $DB untouched, odoo_web stopped. Send this to Claude."

step "database: $DB kept as $OLD_DB, $NEW_DB becomes $DB"
if [ "$DB_EXISTS" != 0 ]; then
  sql postgres "select pg_terminate_backend(pid) from pg_stat_activity where datname = '$DB' and pid <> pg_backend_pid()" > /dev/null
  sql postgres "alter database \"$DB\" rename to \"$OLD_DB\""
fi
sql postgres "alter database \"$NEW_DB\" rename to \"$DB\""

step "filestore: $DB kept as $DB.before_restore_$STAMP"
docker run --rm -i --volumes-from odoo_web --entrypoint sh "$IMG" -c "
  set -e
  cd '$FS'
  rm -rf '$DB.restore_tmp' && mkdir '$DB.restore_tmp'
  tar -xzf - -C '$DB.restore_tmp'
  test -d '$DB.restore_tmp/$DB'
  extracted=\$(find '$DB.restore_tmp/$DB' -type f | wc -l)
  [ \"\$extracted\" -eq '$FILES' ] || { echo \"extracted \$extracted files, expected $FILES\"; exit 1; }
  [ ! -d '$DB' ] || mv '$DB' '$DB.before_restore_$STAMP'
  mv '$DB.restore_tmp/$DB' '$DB'
  rmdir '$DB.restore_tmp'
  echo \"files: \$extracted\"
" < "$TGZ" || stop "filestore restore failed (database already restored), odoo_web stopped. Send this to Claude."

step "code back to $COMMIT"
git -C "$ADDONS" checkout --quiet "$COMMIT"
[ "$(git -C "$ADDONS" rev-parse HEAD)" = "$COMMIT" ] || stop "code not at $COMMIT, odoo_web stopped."

step "starting odoo_web"
docker start odoo_web > /dev/null
echo "RESTORE OK: $DB, filestore and code back to the backup of $(value STAMP)."
echo "Kept until checked: database $OLD_DB, filestore $FS/$DB.before_restore_$STAMP."
sql "$DB" "select name || ' ' || latest_version from ir_module_module
  where name in ('lartdubati_investor_home', 'maintenance_shareholder_equipment') order by name"

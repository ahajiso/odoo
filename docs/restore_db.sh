#!/usr/bin/env bash
# Rollback after a failed deployment: puts back the database, the filestore and the code
# of the backup made by backup_db.sh (audits of 86cf4ac..beacfeb and 7197751..b9979b9).
#
# Usage: bash restore_db.sh <label, e.g. phase4>
#
# Nothing is changed before every check passed: manifest present, both files present
# with their SHA-256, dump readable (pg_restore --list), archive readable (tar -tzf)
# with the expected number of files, code commit known, working tree clean, enough disk
# space for the sizes measured at backup time (the current copies are kept).
# Then, odoo_web stopped:
# 1. both new copies are prepared under temporary names and checked: the database
#    (modules and record counts equal to the backup's) and the filestore (number of
#    files extracted equal to the backup's); nothing current is touched yet;
# 2. the two switches: the database (current one renamed <db>_before_restore_<stamp>,
#    in one transaction), then the filestore (current one renamed
#    <db>.before_restore_<stamp>); if the filestore switch fails, the database switch
#    is undone;
# 3. the code goes back to the commit of the backup;
# 4. odoo_web is started and must answer /web/health.
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
# disk space, from the sizes measured at backup time (audit of 7197751..b9979b9): the
# restored database and filestore are written next to the current ones, which are kept.
# Margin: 50 % + 200 MB for PostgreSQL (indexes rebuilt, WAL), 20 % + 100 MB for the
# filestore.
NEED_DB=$(( $(value DB_BYTES) * 3 / 2 + 200 * 1048576 ))
NEED_FS=$(( $(value FILESTORE_BYTES) * 6 / 5 + 100 * 1048576 ))
DB_EXISTS=$(sql postgres "select count(*) from pg_database where datname = '$DB'")
PG_FREE_KB=$(docker exec odoo_db df -Pk /var/lib/postgresql/data | awk 'NR==2 {print $4}')
[ $((PG_FREE_KB * 1024)) -gt "$NEED_DB" ] \
  || stop "not enough space for PostgreSQL: $((PG_FREE_KB / 1024)) MB free, $((NEED_DB / 1048576)) MB needed; nothing done."
FS_FREE_KB=$(docker run --rm --volumes-from odoo_web --entrypoint df "$IMG" -Pk "$FS" | awk 'NR==2 {print $4}')
[ $((FS_FREE_KB * 1024)) -gt "$NEED_FS" ] \
  || stop "not enough space for the filestore: $((FS_FREE_KB / 1024)) MB free, $((NEED_FS / 1048576)) MB needed; nothing done."
echo "backup: $DUMP, $TGZ ($FILES files), code $COMMIT"
echo "space: PostgreSQL $((PG_FREE_KB / 1024)) MB free for $((NEED_DB / 1048576)) MB, filestore $((FS_FREE_KB / 1024)) MB for $((NEED_FS / 1048576)) MB"
FS_TMP="$DB.restore_$STAMP"
FS_OLD="$DB.before_restore_$STAMP"

in_volume() {  # sh script run next to odoo_web's volumes (odoo_web stopped)
  docker run --rm -i --volumes-from odoo_web --entrypoint sh "$IMG" -c "$1"
}
ODOO_PORT=${ODOO_PORT:-8069}
odoo_ready() {
  local i
  for i in $(seq 1 30); do
    if [ "$(docker inspect -f '{{.State.Running}}' odoo_web)" = true ] \
        && docker exec odoo_web python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:$ODOO_PORT/web/health', timeout=3)" \
           > /dev/null 2>&1; then
      return 0
    fi
    sleep "${POLL_SECONDS:-3}"
  done
  return 1
}

step "stopping odoo_web"
docker stop odoo_web > /dev/null
[ "$(docker inspect -f '{{.State.Running}}' odoo_web)" = "false" ] || stop "odoo_web still running; nothing changed."

# 1. both new copies are prepared and checked under temporary names; nothing current
#    is touched yet
step "prepare the database: restore into $NEW_DB"
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

step "prepare the filestore: extract into $FS/$FS_TMP"
in_volume "
  set -e
  cd '$FS'
  rm -rf '$FS_TMP.x' && mkdir '$FS_TMP.x'
  tar -xzf - -C '$FS_TMP.x'
  test -d '$FS_TMP.x/$DB'
  mv '$FS_TMP.x/$DB' '$FS_TMP' && rmdir '$FS_TMP.x'
  extracted=\$(find '$FS_TMP' -type f | wc -l)
  [ \"\$extracted\" -eq '$FILES' ] || { echo \"extracted \$extracted files, expected $FILES\"; exit 1; }
  echo \"extracted: \$extracted files\"
" < "$TGZ" || stop "filestore extraction failed; $DB and its filestore untouched, odoo_web stopped. Send this to Claude."

# 2. the two switches; if the second fails, the first is undone
step "switch the database: $DB kept as $OLD_DB, $NEW_DB becomes $DB"
if [ "$DB_EXISTS" != 0 ]; then
  sql postgres "select pg_terminate_backend(pid) from pg_stat_activity where datname = '$DB' and pid <> pg_backend_pid()" > /dev/null
  sql postgres "begin; alter database \"$DB\" rename to \"$OLD_DB\"; alter database \"$NEW_DB\" rename to \"$DB\"; commit;"
else
  sql postgres "alter database \"$NEW_DB\" rename to \"$DB\""
fi

step "switch the filestore: $DB kept as $FS_OLD, $FS_TMP becomes $DB"
if ! in_volume "
  set -e
  cd '$FS'
  if [ -d '$DB' ]; then mv '$DB' '$FS_OLD'; fi
  if ! mv '$FS_TMP' '$DB'; then
    if [ -d '$FS_OLD' ]; then mv '$FS_OLD' '$DB'; fi
    exit 1
  fi
"; then
  # compensation: the database goes back as it was
  if [ "$DB_EXISTS" != 0 ]; then
    sql postgres "begin; alter database \"$DB\" rename to \"$NEW_DB\"; alter database \"$OLD_DB\" rename to \"$DB\"; commit;"
  else
    sql postgres "alter database \"$DB\" rename to \"$NEW_DB\""
  fi
  stop "filestore switch failed: database and filestore put back as before, odoo_web stopped. Send this to Claude."
fi

step "code back to $COMMIT"
git -C "$ADDONS" checkout --quiet "$COMMIT" \
  || stop "git checkout $COMMIT failed (database and filestore already restored), odoo_web stopped. Send this to Claude."
[ "$(git -C "$ADDONS" rev-parse HEAD)" = "$COMMIT" ] || stop "code not at $COMMIT, odoo_web stopped."

step "starting odoo_web"
docker start odoo_web > /dev/null || true
odoo_ready || stop "odoo_web not running or not answering after the restore (database, filestore and code restored). Check « docker logs --tail 50 odoo_web »; send this to Claude."
echo "RESTORE OK: $DB, filestore and code back to the backup of $(value STAMP); odoo_web answering."
echo "Kept until checked: database $OLD_DB, filestore $FS/$FS_OLD."
sql "$DB" "select name || ' ' || latest_version from ir_module_module
  where name in ('lartdubati_investor_home', 'maintenance_shareholder_equipment') order by name"

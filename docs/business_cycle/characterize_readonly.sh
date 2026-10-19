#!/usr/bin/env bash
# Read-only characterisation for the future business-cycle audit environment.
# PLAN ONLY: this script must be audited before anyone executes it.
# It writes nothing itself; capture stdout/stderr only after explicit execution approval.

set -euo pipefail
export LC_ALL=C
export PGOPTIONS='-c default_transaction_read_only=on'
export GIT_OPTIONAL_LOCKS=0

readonly WEB_CONTAINER="odoo_web"
readonly DB_CONTAINER="odoo_db"
readonly DB_ROLE="odoo"
readonly TEST_DB="artdubati_test"
readonly PROD_DB="artdubati"
readonly CUSTOM_ROOT="/opt/odoo/addons/custom"

section() {
    printf '\n== %s ==\n' "$1"
}

require() {
    command -v "$1" >/dev/null 2>&1 || {
        printf 'MISSING COMMAND: %s\n' "$1" >&2
        exit 2
    }
}

for command_name in docker sha256sum find findmnt stat awk sed sort git ss ip df du free swapon systemctl date hostname uname python3 wc; do
    require "$command_name"
done

section "identity"
date -u '+utc=%Y-%m-%dT%H:%M:%SZ'
hostname
uname -a
printf 'script_sha256='
sha256sum "$0" | awk '{print $1}'

section "host operating system and capacity"
sed -n -E '/^(NAME|VERSION|ID|VERSION_ID)=/p' /etc/os-release
free -b
swapon --show --bytes --output NAME,TYPE,SIZE,USED,PRIO
df -B1 -T
findmnt --real --bytes --output TARGET,SOURCE,FSTYPE,OPTIONS

section "docker engine"
docker version --format 'client={{.Client.Version}} server={{.Server.Version}}'
docker info --format 'root={{.DockerRootDir}} driver={{.Driver}} logging={{.LoggingDriver}} cgroup={{.CgroupDriver}} security={{json .SecurityOptions}} live_restore={{.LiveRestoreEnabled}}'
docker ps -a --no-trunc --format 'container={{.ID}} name={{.Names}} image={{.Image}} status={{.Status}} networks={{.Networks}}'

section "container definitions without environment values"
while IFS= read -r container_id; do
    [ -n "$container_id" ] || continue
    docker inspect --format 'name={{.Name}} id={{.Id}} image={{.Image}} user={{.Config.User}} entrypoint={{json .Config.Entrypoint}} cmd={{json .Config.Cmd}} restart={{.HostConfig.RestartPolicy.Name}} readonly_root={{.HostConfig.ReadonlyRootfs}} log_driver={{.HostConfig.LogConfig.Type}} network_mode={{.HostConfig.NetworkMode}} pid_mode={{.HostConfig.PidMode}}' "$container_id"
    docker inspect --format '{{range .Mounts}}mount type={{.Type}} source={{.Source}} destination={{.Destination}} rw={{.RW}}{{println}}{{end}}' "$container_id"
    docker inspect --format '{{range .NetworkSettings.Networks}}network id={{.NetworkID}} ip={{.IPAddress}} gateway={{.Gateway}}{{println}}{{end}}' "$container_id"
    docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$container_id" |
        while IFS='=' read -r variable value; do
            [ -n "$variable" ] || continue
            fingerprint="$(printf '%s' "$value" | sha256sum | awk '{print $1}')"
            printf 'env name=%s present=yes length=%s sha256=%s\n' "$variable" "${#value}" "$fingerprint"
        done
done < <(docker ps -aq --no-trunc)

section "docker networks and volumes"
while IFS= read -r network_id; do
    [ -n "$network_id" ] || continue
    docker network inspect --format 'network name={{.Name}} id={{.Id}} driver={{.Driver}} internal={{.Internal}} attachable={{.Attachable}} scope={{.Scope}} ipam={{json .IPAM.Config}} containers={{json .Containers}}' "$network_id"
done < <(docker network ls -q --no-trunc)
while IFS= read -r volume_name; do
    [ -n "$volume_name" ] || continue
    docker volume inspect --format 'volume name={{.Name}} driver={{.Driver}} mountpoint={{.Mountpoint}} options={{json .Options}} labels={{json .Labels}}' "$volume_name"
done < <(docker volume ls -q)

section "images used by Odoo and PostgreSQL"
for container_name in "$WEB_CONTAINER" "$DB_CONTAINER"; do
    image_id="$(docker inspect --format '{{.Image}}' "$container_name")"
    docker image inspect --format 'container='"$container_name"' image_id={{.Id}} repo_digests={{json .RepoDigests}} created={{.Created}} architecture={{.Architecture}} os={{.Os}}' "$image_id"
done

section "host listeners routes and firewall fingerprints"
ss -lntup
ip -details route show table all
if command -v nft >/dev/null 2>&1; then
    nft list ruleset | sha256sum | awk '{print "nft_ruleset_sha256=" $1}'
fi
if command -v iptables-save >/dev/null 2>&1; then
    iptables-save | sha256sum | awk '{print "iptables_ruleset_sha256=" $1}'
fi

section "PostgreSQL databases roles connections and settings"
docker exec -i "$DB_CONTAINER" psql -X -v ON_ERROR_STOP=1 -U "$DB_ROLE" -d postgres <<'SQL'
BEGIN TRANSACTION READ ONLY;
SHOW transaction_read_only;
SELECT datname, pg_get_userbyid(datdba) AS owner, datallowconn,
       pg_database_size(datname) AS bytes
FROM pg_database
ORDER BY datname;
SELECT rolname, rolsuper, rolinherit, rolcreaterole, rolcreatedb, rolcanlogin,
       rolreplication, rolbypassrls
FROM pg_roles
ORDER BY rolname;
SELECT datname, usename, application_name, client_addr, state, count(*) AS connections
FROM pg_stat_activity
GROUP BY datname, usename, application_name, client_addr, state
ORDER BY datname, usename, application_name, client_addr, state;
SELECT name,
       CASE WHEN name = 'archive_command' THEN '[fingerprinted]' ELSE setting END AS safe_setting,
       CASE WHEN name = 'archive_command' THEN length(setting) END AS hidden_length,
       CASE WHEN name = 'archive_command' THEN md5(setting) END AS hidden_md5,
       source
FROM pg_settings
WHERE name IN (
    'archive_mode', 'archive_command', 'data_directory', 'hba_file',
    'listen_addresses', 'log_destination', 'logging_collector',
    'max_connections', 'port', 'ssl', 'wal_level'
)
ORDER BY name;
SELECT pg_is_in_recovery() AS in_recovery;
COMMIT;
SQL

section "Odoo configuration file safe fields"
docker exec -i "$WEB_CONTAINER" python3 -B - <<'PY'
import configparser
import hashlib
import os

candidates = ("/etc/odoo/odoo.conf", "/etc/odoo.conf")
safe = {
    "addons_path", "admin_passwd", "data_dir", "db_host", "db_name",
    "db_password", "db_port", "db_sslmode", "db_user", "dbfilter",
    "list_db", "log_handler", "log_level", "max_cron_threads",
    "proxy_mode", "server_wide_modules", "workers",
}
secret = {"admin_passwd", "db_password"}
found = False
for path in candidates:
    if not os.path.isfile(path):
        continue
    found = True
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(path)
    values = parser["options"] if parser.has_section("options") else {}
    print(f"config path={path} sha256={hashlib.sha256(open(path, 'rb').read()).hexdigest()}")
    for key in sorted(safe):
        if key not in values:
            print(f"config key={key} present=no")
            continue
        value = values[key]
        if key in secret:
            print(f"config key={key} present=yes length={len(value)} sha256={hashlib.sha256(value.encode()).hexdigest()}")
        else:
            print(f"config key={key} value={value}")
if not found:
    raise SystemExit("no expected Odoo configuration file found")
PY

section "Odoo database parameters mail cron modules and counts"
for database_name in "$TEST_DB" "$PROD_DB"; do
    printf '%s\n' "-- database=$database_name"
    docker exec -i "$DB_CONTAINER" psql -X -v ON_ERROR_STOP=1 -U "$DB_ROLE" -d "$database_name" <<'SQL'
BEGIN TRANSACTION READ ONLY;
SHOW transaction_read_only;
SELECT key, true AS present, length(value) AS value_length, md5(value) AS value_md5
FROM ir_config_parameter
WHERE key IN (
    'database.secret', 'database.uuid', 'web.base.url', 'web.base.url.freeze'
)
ORDER BY key;
SELECT id, name, active, smtp_host, smtp_port, smtp_encryption,
       (smtp_user IS NOT NULL AND smtp_user <> '') AS user_present,
       (smtp_pass IS NOT NULL AND smtp_pass <> '') AS password_present
FROM ir_mail_server
ORDER BY id;
SELECT c.id, c.active, c.cron_name, c.interval_number, c.interval_type,
       c.nextcall, m.model
FROM ir_cron c
JOIN ir_model m ON m.id = c.model_id
ORDER BY c.id;
SELECT count(*) AS installed_modules,
       md5(string_agg(name || '=' || COALESCE(installed_version, ''), E'\n' ORDER BY name)) AS installed_modules_md5
FROM ir_module_module
WHERE state = 'installed';
SELECT 'res_users' AS relation, count(*) FROM res_users
UNION ALL SELECT 'res_partner', count(*) FROM res_partner
UNION ALL SELECT 'ir_attachment', count(*) FROM ir_attachment;
COMMIT;
SQL
done

section "secret mounts metadata and fingerprints only"
for container_name in "$WEB_CONTAINER" "$DB_CONTAINER"; do
    printf '%s\n' "-- container=$container_name"
    docker exec -i "$container_name" sh -c '
        if [ -d /run/secrets ]; then
            find /run/secrets -xdev -type f -exec stat -c "secret path=%n mode=%a uid=%u gid=%g size=%s" {} \;
            find /run/secrets -xdev -type f -exec sha256sum {} \;
        else
            printf "secret_dir_present=no\n"
        fi
    '
done

section "code checkout identity without optional locks"
git -C "$CUSTOM_ROOT" rev-parse HEAD
git -C "$CUSTOM_ROOT" status --porcelain=v1 --untracked-files=all | wc -l | awk '{print "git_status_entries=" $1}'
git -C "$CUSTOM_ROOT" status --porcelain=v1 --untracked-files=all | sha256sum | awk '{print "git_status_sha256=" $1}'
git -C "$CUSTOM_ROOT" ls-files -s | sha256sum | awk '{print "git_index_listing_sha256=" $1}'
git -C "$CUSTOM_ROOT" submodule status --recursive

section "database filestore and retained backup sizes"
for database_name in "$TEST_DB" "$PROD_DB"; do
    filestore_path="/var/lib/odoo/.local/share/Odoo/filestore/$database_name"
    docker exec -i "$WEB_CONTAINER" sh -c '
        target=$1
        if [ -d "$target" ]; then
            du -sb "$target"
            find "$target" -xdev -type f -printf "%s\n" | awk "{total += \$1; count += 1} END {print \"files=\" count, \"bytes=\" total}"
        else
            printf "filestore_present=no path=%s\n" "$target"
        fi
    ' sh "$filestore_path"
done
if [ -d /opt/odoo/backups ]; then
    find /opt/odoo/backups -xdev -maxdepth 1 -type f -printf 'backup path=%p size=%s mtime=%TY-%Tm-%TdT%TH:%TM:%TSZ\n' | sort
fi

section "reverse proxy backup scheduler and snapshot evidence"
systemctl list-unit-files --no-pager --no-legend | awk 'tolower($0) ~ /(nginx|caddy|traefik|backup|snapshot|restic|borg|duplicity|docker|odoo|postgres)/'
systemctl list-timers --all --no-pager
for config_root in /etc/nginx /etc/caddy /etc/traefik; do
    if [ -d "$config_root" ]; then
        find "$config_root" -xdev -type f -exec sha256sum {} \;
        find "$config_root" -xdev -type l -exec stat -c 'proxy_symlink path=%n target=%N' {} \;
    fi
done
python3 -B - <<'PY'
from pathlib import Path
import hashlib
import re
from urllib.parse import urlsplit, urlunsplit

roots = (Path("/etc/nginx"), Path("/etc/caddy"), Path("/etc/traefik"))
direct = {"listen", "server_name", "location", "auth_basic_user_file"}
for root in roots:
    if not root.is_dir():
        continue
    for path in sorted(item for item in root.rglob("*") if item.is_file() and not item.is_symlink()):
        try:
            lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
        except (OSError, UnicodeError):
            continue
        for number, raw in enumerate(lines, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s+(.+?);?$", line)
            if not match:
                continue
            directive, value = match.groups()
            value = value.rstrip(";").strip()
            if directive in direct:
                print(f"proxy path={path} line={number} directive={directive} value={value}")
            elif directive == "auth_basic":
                print(f"proxy path={path} line={number} directive=auth_basic present=yes")
            elif directive == "proxy_pass":
                try:
                    parsed = urlsplit(value)
                    host = parsed.hostname or ""
                    port = f":{parsed.port}" if parsed.port else ""
                    safe = urlunsplit((parsed.scheme, host + port, parsed.path, "", ""))
                except ValueError:
                    safe = "unparseable"
                print(f"proxy path={path} line={number} directive=proxy_pass safe_target={safe}")
            elif directive == "proxy_set_header":
                parts = value.split(None, 1)
                header = parts[0] if parts else ""
                header_value = parts[1] if len(parts) == 2 else ""
                digest = hashlib.sha256(header_value.encode()).hexdigest()
                print(f"proxy path={path} line={number} directive=proxy_set_header header={header} value_sha256={digest}")
PY
for schedule_root in /etc/cron.d /etc/cron.daily /etc/cron.hourly /etc/cron.weekly /etc/cron.monthly; do
    if [ -d "$schedule_root" ]; then
        find "$schedule_root" -xdev -type f -exec sha256sum {} \;
    fi
done
printf '%s\n' 'EXTERNAL_REQUIRED provider_snapshot_schedule_and_retention'
printf '%s\n' 'EXTERNAL_REQUIRED provider_volume_backup_scope'
printf '%s\n' 'EXTERNAL_REQUIRED public_dns_and_certificate_transparency_history'

section "end"
printf '%s\n' 'CHARACTERISATION COMPLETE (READ-ONLY COMMAND SET)'

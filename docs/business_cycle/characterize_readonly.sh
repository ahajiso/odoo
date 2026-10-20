#!/usr/bin/env bash
# Proposed read-only characterisation. AUDIT REQUIRED BEFORE SERVER EXECUTION.

set -uo pipefail
export LC_ALL=C
export GIT_OPTIONAL_LOCKS=0

readonly WEB_CONTAINER="odoo_web"
readonly DB_CONTAINER="odoo_db"
readonly DB_ROLE="odoo"
readonly TEST_DB="artdubati_test"
readonly PROD_DB="artdubati"
readonly CUSTOM_ROOT="/opt/odoo/addons/custom"
readonly READ_ONLY_PGOPTIONS="-c default_transaction_read_only=on"
FAILED_SECTIONS=()

readonly SCRIPT_PATH="$(readlink -f -- "${BASH_SOURCE[0]}")"
readonly SCRIPT_DIR="$(dirname -- "$SCRIPT_PATH")"
readonly HELPER="$SCRIPT_DIR/characterize_helpers.py"

if [[ ! -f "$SCRIPT_PATH" || ! -f "$HELPER" ]]; then
    printf '%s\n' 'FATAL script and helper must be executed from real files' >&2
    exit 2
fi

run_section() {
    local name="$1"
    shift
    printf '\n== %s ==\n' "$name"
    if "$@"; then
        printf 'SECTION_OK %s\n' "$name"
    else
        local rc=$?
        printf 'SECTION_FAILED %s rc=%s\n' "$name" "$rc" >&2
        FAILED_SECTIONS+=("$name")
    fi
}

identity() {
    date -u '+utc=%Y-%m-%dT%H:%M:%SZ'
    hostname
    uname -a
    sha256sum "$SCRIPT_PATH" "$HELPER"
}

docker_engine() {
    docker version --format 'client={{.Client.Version}} server={{.Server.Version}}'
    docker info --format 'root={{.DockerRootDir}} driver={{.Driver}} logging={{.LoggingDriver}} cgroup={{.CgroupDriver}} security={{json .SecurityOptions}} live_restore={{.LiveRestoreEnabled}}'
    docker ps -a --no-trunc --format 'container={{.ID}} name={{.Names}} image={{.Image}} status={{.Status}} networks={{.Networks}}'
}

docker_containers() {
    local ids=()
    mapfile -t ids < <(docker ps -aq --no-trunc)
    ((${#ids[@]})) || return 0
    docker inspect "${ids[@]}" | python3 -B "$HELPER" docker-containers
}

docker_networks() {
    local ids=()
    mapfile -t ids < <(docker network ls -q --no-trunc)
    ((${#ids[@]})) || return 0
    docker network inspect --format 'network name={{.Name}} id={{.Id}} driver={{.Driver}} internal={{.Internal}} attachable={{.Attachable}} scope={{.Scope}} ipam={{json .IPAM.Config}} container_names={{range .Containers}}{{.Name}} {{end}}' "${ids[@]}"
}

docker_volumes() {
    local names=()
    mapfile -t names < <(docker volume ls -q)
    ((${#names[@]})) || return 0
    docker volume inspect "${names[@]}" | python3 -B "$HELPER" docker-volumes
}

docker_images() {
    local container_name image_id
    for container_name in "$WEB_CONTAINER" "$DB_CONTAINER"; do
        image_id="$(docker inspect --format '{{.Image}}' "$container_name")" || return
        docker image inspect --format 'container='"$container_name"' image_id={{.Id}} repo_digests={{json .RepoDigests}} created={{.Created}} architecture={{.Architecture}} os={{.Os}}' "$image_id" || return
    done
}

firewall_nft() {
    nft list ruleset | sha256sum | awk '{print "nft_ruleset_sha256=" $1}'
}

firewall_iptables() {
    iptables-save | sha256sum | awk '{print "iptables_ruleset_sha256=" $1}'
}

postgres_cluster() {
    docker exec -e PGOPTIONS="$READ_ONLY_PGOPTIONS" -i "$DB_CONTAINER" \
        psql -X -v ON_ERROR_STOP=1 -U "$DB_ROLE" -d postgres <<'SQL'
BEGIN TRANSACTION READ ONLY;
SHOW transaction_read_only;
SHOW server_version;
SELECT datname, pg_get_userbyid(datdba) AS owner, datallowconn,
       pg_database_size(datname) AS bytes
FROM pg_database
ORDER BY datname;
SELECT rolname, rolsuper, rolinherit, rolcreaterole, rolcreatedb, rolcanlogin,
       rolreplication, rolbypassrls
FROM pg_roles
ORDER BY rolname;
SELECT datname, usename, application_name,
       CASE
         WHEN client_addr IS NULL THEN 'local'
         WHEN client_addr << inet '10.0.0.0/8'
           OR client_addr << inet '172.16.0.0/12'
           OR client_addr << inet '192.168.0.0/16' THEN 'private'
         ELSE 'external'
       END AS client_category,
       state, count(*) AS connections
FROM pg_stat_activity
GROUP BY datname, usename, application_name, client_category, state
ORDER BY datname, usename, application_name, client_category, state;
SELECT name,
       CASE WHEN name IN ('archive_command', 'archive_library')
            THEN '[present=' || CASE WHEN setting = '' THEN 'no' ELSE 'yes' END || ']'
            ELSE setting END AS safe_setting,
       source
FROM pg_settings
WHERE name IN (
    'archive_mode', 'archive_command', 'archive_library', 'data_directory',
    'hba_file', 'listen_addresses', 'log_destination', 'logging_collector',
    'max_connections', 'port', 'ssl', 'wal_level'
)
ORDER BY name;
SELECT slot_type, active, temporary, count(*) AS slots
FROM pg_replication_slots
GROUP BY slot_type, active, temporary
ORDER BY slot_type, active, temporary;
SELECT application_name, state, sync_state, count(*) AS replicas
FROM pg_stat_replication
GROUP BY application_name, state, sync_state
ORDER BY application_name, state, sync_state;
SELECT pg_is_in_recovery() AS in_recovery;
COMMIT;
SQL
}

odoo_config() {
    local config_path
    config_path="$(docker exec "$WEB_CONTAINER" printenv ODOO_RC 2>/dev/null || true)"
    if [[ -z "$config_path" ]]; then
        config_path="/etc/odoo/odoo.conf"
    fi
    if [[ ! "$config_path" =~ ^/[A-Za-z0-9_./-]+$ || "$config_path" == *".."* ]]; then
        printf '%s\n' 'unsafe ODOO_RC path refused' >&2
        return 2
    fi
    {
        printf '%s\0' "$config_path"
        docker exec -i "$WEB_CONTAINER" cat -- "$config_path"
    } | python3 -B "$HELPER" odoo-config
}

odoo_database() {
    local database_name="$1"
    docker exec -e PGOPTIONS="$READ_ONLY_PGOPTIONS" -i "$DB_CONTAINER" \
        psql -X -v ON_ERROR_STOP=1 -U "$DB_ROLE" -d "$database_name" <<'SQL'
BEGIN TRANSACTION READ ONLY;
SHOW transaction_read_only;
SELECT key,
       CASE WHEN key = 'database.secret'
            THEN '[present=' || CASE WHEN value IS NULL OR value = '' THEN 'no' ELSE 'yes' END || ']'
            ELSE value END AS safe_value
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
JOIN ir_act_server s ON s.id = c.ir_actions_server_id
JOIN ir_model m ON m.id = s.model_id
ORDER BY c.id;
SELECT count(*) AS installed_modules,
       md5(string_agg(name || ' ' || coalesce(latest_version, ''), ',' ORDER BY name)) AS installed_modules_md5
FROM ir_module_module
WHERE state = 'installed';
SELECT 'res_users' AS relation, count(*) FROM res_users
UNION ALL SELECT 'res_partner', count(*) FROM res_partner
UNION ALL SELECT 'ir_attachment', count(*) FROM ir_attachment;
SELECT user_id, COALESCE(scope, '[global]') AS scope, expiration_date, count(*) AS api_keys
FROM res_users_apikeys
GROUP BY user_id, scope, expiration_date
ORDER BY user_id, scope, expiration_date;
SELECT state, count(*) AS server_actions
FROM ir_act_server
WHERE state = 'webhook'
GROUP BY state;
SELECT active, count(*) AS fetchmail_servers
FROM fetchmail_server
GROUP BY active
ORDER BY active;
COMMIT;
SQL
}

secret_metadata() {
    local container_name="$1"
    if docker exec -i "$container_name" test -d /run/secrets; then
        docker exec -i "$container_name" find /run/secrets -xdev -type f \
            -printf 'secret path=%p mode=%m uid=%U gid=%G\n'
    else
        printf '%s\n' 'secret_dir_present=no'
    fi
}

git_identity() {
    git -c core.fsmonitor=false -c safe.directory="$CUSTOM_ROOT" -C "$CUSTOM_ROOT" rev-parse HEAD
    git -c core.fsmonitor=false -c safe.directory="$CUSTOM_ROOT" -C "$CUSTOM_ROOT" status --porcelain=v1 --untracked-files=all | wc -l | awk '{print "git_status_entries=" $1}'
    git -c core.fsmonitor=false -c safe.directory="$CUSTOM_ROOT" -C "$CUSTOM_ROOT" status --porcelain=v1 --untracked-files=all | sha256sum | awk '{print "git_status_sha256=" $1}'
    git -c core.fsmonitor=false -c safe.directory="$CUSTOM_ROOT" -C "$CUSTOM_ROOT" ls-files -s | sha256sum | awk '{print "git_index_listing_sha256=" $1}'
    git -c core.fsmonitor=false -c safe.directory="$CUSTOM_ROOT" -C "$CUSTOM_ROOT" submodule status --recursive
}

filestore_size() {
    local database_name="$1"
    local target=""
    local candidate
    for candidate in \
        "/var/lib/odoo/.local/share/Odoo/filestore/$database_name" \
        "/var/lib/odoo/filestore/$database_name"; do
        if docker exec -i "$WEB_CONTAINER" test -d "$candidate"; then
            target="$candidate"
            break
        fi
    done
    if [[ -z "$target" ]]; then
        printf '%s\n' 'filestore_present=no'
        return 0
    fi
    docker exec -i "$WEB_CONTAINER" du -sb -- "$target"
    docker exec -i "$WEB_CONTAINER" find "$target" -xdev -type f -printf '%s\n' |
        awk '{total += $1; count += 1} END {print "files=" count, "bytes=" total}'
}

backup_inventory() {
    if [[ -d /opt/odoo/backups ]]; then
        find /opt/odoo/backups -xdev -maxdepth 1 -type f \
            -printf 'backup path=%p size=%s mtime=%TY-%Tm-%TdT%TH:%TM:%TSZ\n' | sort
    else
        printf '%s\n' 'backup_directory_present=no'
    fi
}

proxy_configuration() {
    local ids=()
    mapfile -t ids < <(docker ps -aq --no-trunc)
    if ((${#ids[@]})); then
        docker inspect "${ids[@]}" | python3 -B "$HELPER" proxy-config
    else
        printf '%s\n' 'no containers available for proxy inspection'
    fi
}

cron_configuration() {
    python3 -B "$HELPER" cron-config
    systemctl list-unit-files --no-pager --no-legend |
        awk 'tolower($0) ~ /(nginx|caddy|traefik|backup|snapshot|restic|borg|duplicity|docker|odoo|postgres)/'
    systemctl list-timers --all --no-pager
}

run_section "identity" identity
run_section "host os" sed -n -E '/^(NAME|VERSION|ID|VERSION_ID)=/p' /etc/os-release
run_section "host memory" free -b
run_section "host swap" swapon --show --bytes --output NAME,TYPE,SIZE,USED,PRIO
run_section "host filesystems" df -B1 -T
run_section "host mounts" findmnt --real --bytes --output TARGET,SOURCE,FSTYPE,OPTIONS
run_section "docker engine" docker_engine
run_section "docker containers sanitized" docker_containers
run_section "docker networks" docker_networks
run_section "docker volumes sanitized" docker_volumes
run_section "docker images" docker_images
run_section "host listeners" ss -lntup
run_section "host routes" ip -details route show table all
if command -v nft >/dev/null 2>&1; then
    run_section "nft fingerprint" firewall_nft
fi
if command -v iptables-save >/dev/null 2>&1; then
    run_section "iptables fingerprint" firewall_iptables
fi
run_section "postgres cluster" postgres_cluster
run_section "odoo effective configuration" odoo_config
run_section "odoo database artdubati_test" odoo_database "$TEST_DB"
run_section "odoo database artdubati" odoo_database "$PROD_DB"
run_section "odoo secret metadata" secret_metadata "$WEB_CONTAINER"
run_section "postgres secret metadata" secret_metadata "$DB_CONTAINER"
run_section "git identity" git_identity
run_section "filestore artdubati_test" filestore_size "$TEST_DB"
run_section "filestore artdubati" filestore_size "$PROD_DB"
run_section "retained backup inventory" backup_inventory
run_section "proxy configuration sanitized" proxy_configuration
run_section "cron and timer configuration sanitized" cron_configuration
run_section "external evidence" printf '%s\n' \
    'EXTERNAL_REQUIRED provider_snapshot_schedule_and_retention' \
    'EXTERNAL_REQUIRED provider_volume_backup_scope' \
    'EXTERNAL_REQUIRED public_dns_and_certificate_transparency_history'

if ((${#FAILED_SECTIONS[@]})); then
    printf 'CHARACTERISATION FAILED sections=%s\n' "${FAILED_SECTIONS[*]}" >&2
    exit 1
fi
printf '%s\n' 'CHARACTERISATION OK'

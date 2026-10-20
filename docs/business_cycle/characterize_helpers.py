#!/usr/bin/env python3
"""Read-only parsers/sanitisers for characterize_readonly.sh."""

from __future__ import annotations

import configparser
import json
from pathlib import Path
import re
import shlex
import sys
from urllib.parse import urlsplit, urlunsplit


SENSITIVE = re.compile(r"(?:auth|pass|passwd|password|secret|token|api.?key|private.?key|credential)", re.I)
PROXY = re.compile(r"(?:nginx|caddy|traefik|haproxy|reverse.?proxy)", re.I)
DETAIL_NAMES = {"odoo_web", "odoo_db"}


def safe_command(tokens: object) -> list[str]:
    if not isinstance(tokens, list):
        return []
    result: list[str] = []
    hide_next = False
    for index, raw in enumerate(tokens):
        token = str(raw)
        if index == 0:
            result.append(safe_proxy_target(token) if "://" in token else token)
            continue
        if hide_next:
            result.append("[arg]")
            hide_next = False
            continue
        if token.startswith("--"):
            option, separator, _value = token.partition("=")
            result.append(f"{option}=[arg]" if separator else option)
            if not separator and SENSITIVE.search(option):
                hide_next = True
            continue
        if re.match(r"^-[wWp].+", token):
            result.append(f"{token[:2]}[arg]")
            continue
        if token.startswith("-"):
            result.append(token[:2] if len(token) > 2 else token)
        else:
            result.append("[arg]")
        if token in {"-c", "-w", "-W", "-p"}:
            hide_next = True
    return result


def safe_labels(labels: object, proxy: bool) -> dict[str, str]:
    if not isinstance(labels, dict):
        return {}
    output: dict[str, str] = {}
    for key, raw in sorted(labels.items()):
        value = "" if raw is None else str(raw)
        if SENSITIVE.search(key):
            output[key] = "[present]"
        else:
            output[key] = "[present]"
    return output


def docker_containers() -> None:
    objects = json.load(sys.stdin)
    for item in sorted(objects, key=lambda value: value.get("Name", "")):
        name = str(item.get("Name", "")).lstrip("/")
        config = item.get("Config") or {}
        host = item.get("HostConfig") or {}
        image = str(config.get("Image", ""))
        is_proxy = bool(PROXY.search(f"{name} {image}"))
        detailed = name in DETAIL_NAMES or is_proxy
        base = {
            "name": name,
            "id": item.get("Id"),
            "image_id": item.get("Image"),
            "image_name": image,
            "running": (item.get("State") or {}).get("Running"),
            "log_driver": (host.get("LogConfig") or {}).get("Type"),
            "network_mode": host.get("NetworkMode"),
            "restart": (host.get("RestartPolicy") or {}).get("Name"),
        }
        if detailed:
            base.update(
                user=config.get("User"),
                entrypoint=safe_command(config.get("Entrypoint")),
                cmd=safe_command(config.get("Cmd")),
                env_names=sorted(
                    str(value).split("=", 1)[0]
                    for value in (config.get("Env") or [])
                    if "=" in str(value)
                ),
                mounts=[
                    {
                        "type": mount.get("Type"),
                        "source": mount.get("Source"),
                        "destination": mount.get("Destination"),
                        "rw": mount.get("RW"),
                    }
                    for mount in item.get("Mounts") or []
                ],
                labels=safe_labels(config.get("Labels"), is_proxy),
            )
        print(json.dumps(base, sort_keys=True, separators=(",", ":")))


def docker_volumes() -> None:
    objects = json.load(sys.stdin)
    for item in sorted(objects, key=lambda value: value.get("Name", "")):
        print(
            json.dumps(
                {
                    "name": item.get("Name"),
                    "driver": item.get("Driver"),
                    "mountpoint": item.get("Mountpoint"),
                    "option_names": sorted((item.get("Options") or {}).keys()),
                    "label_names": sorted((item.get("Labels") or {}).keys()),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )


def host_mounts() -> None:
    payload = json.load(sys.stdin)

    def visit(items: object) -> None:
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            options = []
            for raw in str(item.get("options") or "").split(","):
                key, separator, value = raw.partition("=")
                if not raw:
                    continue
                if separator and key.lower() in {"user", "username", "credentials", "password", "passwd"}:
                    options.append(f"{key}=[present]")
                else:
                    options.append(raw if not (separator and SENSITIVE.search(key)) else f"{key}=[present]")
            print(json.dumps({
                "target": item.get("target"),
                "source": item.get("source"),
                "fstype": item.get("fstype"),
                "options": options,
            }, sort_keys=True, separators=(",", ":")))
            visit(item.get("children"))

    visit(payload.get("filesystems") if isinstance(payload, dict) else None)


def odoo_config() -> None:
    payload = sys.stdin.buffer.read()
    path_raw, separator, content = payload.partition(b"\0")
    if not separator:
        raise SystemExit("missing Odoo config path separator")
    path = path_raw.decode("utf-8", errors="strict")
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(content.decode("utf-8", errors="strict"))
    values = parser["options"] if parser.has_section("options") else {}
    safe = {
        "addons_path", "data_dir", "db_host", "db_name", "db_port", "db_sslmode",
        "db_template", "db_user", "dbfilter", "gevent_port",
        "http_port", "list_db", "log_handler", "log_level", "max_cron_threads",
        "proxy_mode", "server_wide_modules", "smtp_port", "smtp_server", "smtp_ssl",
        "workers",
    }
    secrets = {"admin_passwd", "db_password", "email_from", "smtp_password", "smtp_user"}
    print(f"config path={path}")
    for key in sorted(safe | secrets):
        if key not in values:
            print(f"config key={key} present=no")
        elif key in secrets:
            print(f"config key={key} present=yes")
        else:
            print(f"config key={key} value={values[key]}")


def safe_proxy_target(value: str) -> str:
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        return urlunsplit((parsed.scheme, host + port, "", "", ""))
    except ValueError:
        return "unparseable"


def proxy_line(path: Path, number: int, line: str) -> None:
    match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s+(.+?);?$", line)
    if not match:
        return
    directive, value = match.groups()
    value = value.rstrip(";").strip()
    prefix = f"proxy path={path} line={number} directive={directive}"
    if directive in {"listen", "server_name", "location", "auth_basic_user_file"}:
        print(f"{prefix} value={value}")
    elif directive == "auth_basic":
        print(f"{prefix} present=yes")
    elif directive == "proxy_pass":
        print(f"{prefix} safe_target={safe_proxy_target(value)}")
    elif directive == "proxy_set_header":
        parts = value.split(None, 1)
        header = parts[0] if parts else ""
        print(f"{prefix} header={header} value_present={'yes' if len(parts) == 2 else 'no'}")


def scan_proxy_path(path: Path) -> None:
    candidates = [path] if path.is_file() else sorted(path.rglob("*")) if path.is_dir() else []
    for candidate in candidates:
        if not candidate.is_file() or candidate.is_symlink():
            continue
        try:
            lines = candidate.read_text(encoding="utf-8", errors="strict").splitlines()
        except (OSError, UnicodeError):
            continue
        print(f"proxy_file path={candidate}")
        for number, raw in enumerate(lines, start=1):
            line = raw.strip()
            if line and not line.startswith("#"):
                proxy_line(candidate, number, line)


def proxy_config() -> None:
    inspected = json.load(sys.stdin)
    roots = {Path("/etc/nginx"), Path("/etc/caddy"), Path("/etc/traefik")}
    for item in inspected:
        name = str(item.get("Name", ""))
        image = str((item.get("Config") or {}).get("Image", ""))
        if not PROXY.search(f"{name} {image}"):
            continue
        for mount in item.get("Mounts") or []:
            source = mount.get("Source")
            destination = str(mount.get("Destination") or "")
            config_roots = ("/etc/nginx", "/etc/caddy", "/etc/traefik")
            if source and any(destination == root or destination.startswith(root + "/") for root in config_roots):
                roots.add(Path(str(source)))
    for root in sorted(roots):
        scan_proxy_path(root)


def masked_cron_command(command: str) -> str:
    try:
        tokens = shlex.split(command, comments=True, posix=True)
    except ValueError:
        return "unparseable present=yes"
    if not tokens:
        return "empty"
    while tokens and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0]):
        tokens.pop(0)
    if not tokens:
        return "environment_only"
    executable = tokens[0]
    option_names = []
    for token in tokens[1:]:
        if token.startswith("-"):
            option_names.append(token.split("=", 1)[0])
    return f"executable={executable} arguments={max(0, len(tokens) - 1)} option_names={','.join(option_names)}"


def cron_line(path: Path, number: int, raw: str, system_style: bool) -> None:
    line = raw.strip()
    if not line or line.startswith("#") or "=" in line.split(None, 1)[0]:
        return
    macro = re.fullmatch(r"@(reboot|yearly|annually|monthly|weekly|daily|midnight|hourly)", line.split(None, 1)[0], re.I)
    if macro:
        fields = line.split(None, 2 if system_style else 1)
        minimum = 3 if system_style else 2
        schedule_fields = fields[:1]
        user_index = 1 if system_style else None
        command_index = 2 if system_style else 1
    else:
        fields = line.split(None, 6 if system_style else 5)
        minimum = 7 if system_style else 6
        schedule_fields = fields[:5]
        user_index = 5 if system_style else None
        command_index = 6 if system_style else 5
    schedule_valid = bool(macro) or all(re.fullmatch(r"[A-Za-z0-9*/?,#LWK-]+", field, re.I) for field in schedule_fields)
    if len(fields) < minimum or not schedule_valid:
        print(f"cron path={path} line={number} unparsed=yes")
        return
    schedule = " ".join(schedule_fields)
    user = fields[user_index] if user_index is not None else path.name
    command = fields[command_index]
    print(f"cron path={path} line={number} schedule={schedule!r} user={user} {masked_cron_command(command)}")


def cron_config() -> None:
    paths = [Path("/etc/crontab")]
    paths.extend(sorted(Path("/etc/cron.d").glob("*")) if Path("/etc/cron.d").is_dir() else [])
    for root in (Path("/var/spool/cron/crontabs"), Path("/var/spool/cron")):
        if root.is_dir():
            paths.extend(sorted(path for path in root.glob("*") if path.is_file()))
    seen: set[Path] = set()
    for path in paths:
        if path in seen or not path.is_file() or path.is_symlink():
            continue
        seen.add(path)
        try:
            lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
        except (OSError, UnicodeError):
            continue
        system_style = path == Path("/etc/crontab") or path.parent == Path("/etc/cron.d")
        for number, raw in enumerate(lines, start=1):
            cron_line(path, number, raw, system_style)
    for directory in ("/etc/cron.hourly", "/etc/cron.daily", "/etc/cron.weekly", "/etc/cron.monthly"):
        root = Path(directory)
        if root.is_dir():
            for entry in sorted(root.iterdir()):
                if entry.is_file() and not entry.is_symlink():
                    print(f"periodic path={entry}")


COMMANDS = {
    "cron-config": cron_config,
    "docker-containers": docker_containers,
    "docker-volumes": docker_volumes,
    "host-mounts": host_mounts,
    "odoo-config": odoo_config,
    "proxy-config": proxy_config,
}


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        raise SystemExit("expected one known helper command")
    COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    main()

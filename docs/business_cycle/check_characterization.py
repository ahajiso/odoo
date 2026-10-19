#!/usr/bin/env python3
"""Static safety checks for characterize_readonly.sh; does not execute it."""

from pathlib import Path
import re
import sys


SCRIPT = Path(__file__).with_name("characterize_readonly.sh")
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "default_transaction_read_only=on",
    "BEGIN TRANSACTION READ ONLY",
    "docker info",
    "docker inspect",
    "docker network inspect",
    "docker volume inspect",
    "pg_roles",
    "pg_stat_activity",
    "web.base.url.freeze",
    "ir_mail_server",
    "swapon --show",
    "LoggingDriver",
    "provider_snapshot_schedule_and_retention",
)
for token in required:
    if token not in text:
        raise SystemExit(f"missing required read-only probe: {token}")

forbidden = (
    r"\b(rm|mv|cp|mkdir|touch|truncate|chmod|chown|install)\b",
    r"\bsed\s+-i\b",
    r"\btee\b",
    r"\bdocker\s+(run|create|start|stop|restart|rm|compose)\b",
    r"\bsystemctl\s+(start|stop|restart|reload|enable|disable|mask|unmask)\b",
    r"\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE|VACUUM|REINDEX|GRANT|REVOKE)\b",
)
for pattern in forbidden:
    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    if match:
        line = text.count("\n", 0, match.start()) + 1
        raise SystemExit(f"forbidden write-like construct at line {line}: {match.group(0)!r}")

for number, line_text in enumerate(text.splitlines(), start=1):
    scrubbed = line_text.replace(">/dev/null", "").replace("2>&1", "")
    if re.search(r"(?<![<>=])>>(?![=])|(?<![<>=])>(?![=&])", scrubbed):
        raise SystemExit(f"forbidden output redirection at line {number}")

if text.count("BEGIN TRANSACTION READ ONLY") != text.count("COMMIT;"):
    raise SystemExit("every SQL read-only transaction must end explicitly")

print("CHARACTERISATION STATIC CHECK OK")

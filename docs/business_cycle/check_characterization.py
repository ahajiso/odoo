#!/usr/bin/env python3
"""Exact-file and semantic allowlist for the characterisation command set."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "characterize_readonly.sh"
HELPER = ROOT / "characterize_helpers.py"
EXPECTED_SCRIPT_SHA256 = "bd6bc707683a585b2f58b172124c6a3909019e212cf9c765f6b3e8704001fb74"
EXPECTED_HELPER_SHA256 = "0d4020ee143f984e74f16bd53dd0e2496e8c23744eae6b9709dd3a9bc7965615"

ALLOWED_COMMANDS = {
    "awk", "break", "cat", "command", "date", "df", "docker", "done", "du", "else",
    "dirname", "exit", "fi", "find", "findmnt", "for", "free", "git", "hostname", "if",
    "ip", "iptables-save", "local", "mapfile", "nft", "printf", "psql", "python3", "do",
    "readlink", "return", "run_section", "sed", "sha256sum", "shift", "sort",
    "ss", "swapon", "systemctl", "then", "uname", "wc",
}
ALLOWED_DOCKER = {"exec", "image", "info", "inspect", "network", "ps", "version", "volume"}
ALLOWED_DOCKER_NESTED = {"image": {"inspect"}, "network": {"inspect", "ls"}, "volume": {"inspect", "ls"}}
ALLOWED_GIT = {"ls-files", "rev-parse", "status", "submodule"}
ALLOWED_HELPERS = {"cron-config", "docker-containers", "docker-volumes", "odoo-config", "proxy-config"}
ALLOWED_IMPORTS = {
    "__future__", "configparser", "hashlib", "json", "pathlib", "re", "shlex", "sys",
    "urllib.parse",
}
FORBIDDEN_SQL = {
    "ALTER", "CALL", "COPY", "CREATE", "DELETE", "DO", "DROP", "GRANT", "INSERT",
    "LOCK", "MERGE", "REINDEX", "RESET", "REVOKE", "SET", "TRUNCATE", "UPDATE",
    "VACUUM",
}
FORBIDDEN_SQL_FUNCTIONS = {
    "dblink", "lo_export", "pg_cancel_backend", "pg_reload_conf", "pg_rotate_logfile",
    "pg_terminate_backend", "set_config",
}
FORBIDDEN_PYTHON_CALLS = {
    "chmod", "chown", "exec", "eval", "mkdir", "open", "remove", "rename", "replace",
    "rmdir", "symlink_to", "touch", "unlink", "write_bytes", "write_text",
}


class ValidationError(RuntimeError):
    pass


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def heredocs(text: str, marker: str) -> list[str]:
    return re.findall(rf"<<'{re.escape(marker)}'\n(.*?)\n{re.escape(marker)}", text, re.S)


def strip_heredocs(text: str) -> str:
    return re.sub(r"<<'([A-Z]+)'\n.*?\n\1", "<<'HEREDOC'", text, flags=re.S)


def validate_sql(sql: str) -> None:
    without_comments = re.sub(r"--[^\n]*", "", sql)
    statements = [item.strip() for item in without_comments.split(";") if item.strip()]
    for statement in statements:
        first = statement.split(None, 1)[0].upper()
        if first not in {"BEGIN", "SHOW", "SELECT", "COMMIT"}:
            raise ValidationError(f"SQL statement is not allowlisted: {first}")
        upper = statement.upper()
        for token in FORBIDDEN_SQL:
            if re.search(rf"\b{token}\b", upper):
                raise ValidationError(f"forbidden SQL token: {token}")
        for function in FORBIDDEN_SQL_FUNCTIONS:
            if re.search(rf"\b{re.escape(function)}\s*\(", statement, re.I):
                raise ValidationError(f"forbidden SQL function: {function}")
    if not statements or statements[0].upper() != "BEGIN TRANSACTION READ ONLY":
        raise ValidationError("SQL block must start with BEGIN TRANSACTION READ ONLY")
    if statements[-1].upper() != "COMMIT":
        raise ValidationError("SQL block must end with COMMIT")


def command_words(shell: str) -> list[tuple[int, str, str]]:
    found = []
    for number, raw in enumerate(shell.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#") or line in {"{", "}", "do", "done", "then", "else", "fi"}:
            continue
        if line.startswith(("-", "'", '"')):
            continue
        if line.endswith("() {") or line.startswith(("readonly ", "export ", "set ", "[[ ", "((", "}")):
            continue
        structural = re.sub(r"'[^']*'|\"(?:\\.|[^\"])*\"", "''", line)
        for segment in re.split(r"(?<!\|)\|(?!\|)|&&|;", structural):
            segment = segment.strip()
            segment = re.sub(r"^[A-Za-z_][A-Za-z0-9_]*(?:\+)?=(?:''|\S+)\s*", "", segment)
            if not segment:
                continue
            match = re.match(r"(?:if\s+)?([A-Za-z0-9_.-]+)\b(.*)", segment)
            if match:
                found.append((number, match.group(1), match.group(2).strip()))
    return found


def validate_shell_allowlist(text: str) -> None:
    shell = strip_heredocs(text)
    for number, command, arguments in command_words(shell):
        if command not in ALLOWED_COMMANDS:
            raise ValidationError(f"shell command not allowlisted at line {number}: {command}")
        if command == "docker":
            tokens = arguments.split()
            while tokens and tokens[0] in {"-e", "-i"}:
                tokens = tokens[2:] if tokens[0] == "-e" else tokens[1:]
            if not tokens or tokens[0] not in ALLOWED_DOCKER:
                raise ValidationError(f"Docker subcommand not allowlisted at line {number}")
            if tokens[0] in ALLOWED_DOCKER_NESTED and (len(tokens) < 2 or tokens[1] not in ALLOWED_DOCKER_NESTED[tokens[0]]):
                raise ValidationError(f"Docker nested subcommand not allowlisted at line {number}")
            if tokens[0] == "exec" and re.search(r"\bodoo\s+shell\b", arguments):
                raise ValidationError("Odoo shell is forbidden")
        elif command == "git":
            matches = [item for item in ALLOWED_GIT if re.search(rf"\b{re.escape(item)}\b", arguments)]
            if not matches:
                raise ValidationError(f"Git subcommand not allowlisted at line {number}")
        elif command == "systemctl" and not arguments.startswith(("list-unit-files ", "list-timers ")):
            raise ValidationError(f"systemctl action not allowlisted at line {number}")
        elif command == "python3":
            if re.search(r"(?:^|\s)-c(?:\s|$)", arguments) or not any(name in arguments for name in ALLOWED_HELPERS):
                raise ValidationError(f"Python invocation not allowlisted at line {number}")
        elif command == "find" and re.search(r"\s-(?:delete|exec|execdir|fprint|fls|ok|okdir)\b", arguments):
            raise ValidationError(f"find action not allowlisted at line {number}")
        elif command in {"nft", "iptables-save"}:
            expected = "list ruleset" if command == "nft" else ""
            if arguments != expected:
                raise ValidationError(f"firewall command not allowlisted at line {number}")

    banned_fragments = (
        r"\bdd\s+", r"\bln\s+", r"\bkill\s+", r"\bcrontab\s+", r"\bdocker\s+(kill|pause|unpause|restart|stop|start|rm|run|create)\b",
        r"\bgit\s+(?:[^\n]*\s)?(?:checkout|clean|reset|switch|restore)\b", r"\bsystemctl\s+daemon-reload\b",
        r"\bpython3\s+-c\b", r"\b(open|write_text|write_bytes)\s*\(", r"(^|[^<])>>?\s*[^/&]",
    )
    for pattern in banned_fragments:
        match = re.search(pattern, shell, re.I | re.M)
        if match:
            raise ValidationError(f"non-read-only shell construct: {match.group(0)!r}")
    for match in re.finditer(r"(?:\$\(|<\s*<\()\s*([A-Za-z0-9_.-]+)", shell):
        if match.group(1) not in ALLOWED_COMMANDS:
            raise ValidationError(f"command substitution not allowlisted: {match.group(1)}")


def validate_helper(text: str) -> None:
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in ALLOWED_IMPORTS:
                    raise ValidationError(f"Python import not allowlisted: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module not in ALLOWED_IMPORTS:
                raise ValidationError(f"Python import not allowlisted: {module}")
        elif isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name in FORBIDDEN_PYTHON_CALLS:
                raise ValidationError(f"Python call not allowlisted: {name}")


def validate_script(text: str, *, check_hash: bool = True) -> None:
    if check_hash and digest(text) != EXPECTED_SCRIPT_SHA256:
        raise ValidationError("script SHA-256 differs from the audited allowlist")
    blocks = heredocs(text, "SQL")
    if len(blocks) != 2:
        raise ValidationError("expected exactly two SQL heredocs")
    for block in blocks:
        validate_sql(block)
    validate_shell_allowlist(text)


def main() -> None:
    script_text = SCRIPT.read_text(encoding="utf-8")
    helper_text = HELPER.read_text(encoding="utf-8")
    validate_script(script_text)
    if digest(helper_text) != EXPECTED_HELPER_SHA256:
        raise ValidationError("helper SHA-256 differs from the audited allowlist")
    validate_helper(helper_text)
    print("CHARACTERISATION ALLOWLIST CHECK OK")


if __name__ == "__main__":
    try:
        main()
    except (OSError, SyntaxError, ValidationError) as error:
        print(f"CHARACTERISATION ALLOWLIST CHECK FAILED: {error}", file=sys.stderr)
        raise SystemExit(1)

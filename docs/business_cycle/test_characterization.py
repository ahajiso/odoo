#!/usr/bin/env python3
"""Negative and sanitisation tests for the read-only characterisation package."""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import characterize_helpers as helpers  # noqa: E402
import check_characterization as checker  # noqa: E402


class AllowlistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = checker.SCRIPT.read_text(encoding="utf-8")
        cls.helper = checker.HELPER.read_text(encoding="utf-8")

    def test_current_files_pass(self) -> None:
        checker.validate_script(self.script)
        checker.validate_helper(self.helper)

    def test_any_unreviewed_script_change_breaks_the_pin(self) -> None:
        with self.assertRaises(checker.ValidationError):
            checker.validate_script(self.script + "\n# mutation\n")

    def test_dangerous_shell_and_sql_mutations_are_rejected_semantically(self) -> None:
        sql_mutations = (
            "SET transaction_read_only = off;",
            "COPY pg_database TO PROGRAM 'id';",
            "SELECT pg_terminate_backend(1);",
            "SELECT pg_reload_conf();",
        )
        shell_mutations = (
            "docker kill odoo_web",
            "docker pause odoo_web",
            "docker exec odoo_web odoo shell -d artdubati_test",
            "dd if=/dev/zero of=/tmp/canary",
            "ln -s /tmp/a /tmp/b",
            "kill -9 1",
            "crontab -r",
            "systemctl daemon-reload",
            "git checkout main",
            "git clean -fdx",
            "find /tmp -fprint /tmp/canary",
            "python3 -c \"open('/tmp/canary','w').write('x')\"",
            "find /tmp -delete",
            "value=\"$(curl https://example.invalid)\"",
        )
        for mutation in sql_mutations:
            with self.subTest(mutation=mutation):
                candidate = self.script.replace("COMMIT;", mutation + "\nCOMMIT;", 1)
                with self.assertRaises(checker.ValidationError):
                    checker.validate_script(candidate, check_hash=False)
        for mutation in shell_mutations:
            with self.subTest(mutation=mutation):
                with self.assertRaises(checker.ValidationError):
                    checker.validate_script(self.script + "\n" + mutation + "\n", check_hash=False)

    def test_python_write_and_process_mutations_are_rejected(self) -> None:
        mutations = (
            "\nimport subprocess\n",
            "\nPath('/tmp/canary').write_text('x')\n",
            "\nopen('/tmp/canary', 'w')\n",
            "\nimport os\nos.remove('/tmp/canary')\n",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                with self.assertRaises(checker.ValidationError):
                    checker.validate_helper(self.helper + mutation)


class SanitisationTests(unittest.TestCase):
    def run_container_parser(self, payload: object) -> str:
        previous = sys.stdin
        output = StringIO()
        try:
            sys.stdin = StringIO(json.dumps(payload))
            with redirect_stdout(output):
                helpers.docker_containers()
        finally:
            sys.stdin = previous
        return output.getvalue()

    def test_multiline_environment_value_never_appears(self) -> None:
        payload = [{
            "Name": "/odoo_web",
            "Id": "container-id",
            "Image": "image-id",
            "State": {"Running": True},
            "Config": {
                "Image": "odoo:test",
                "Env": ["CERT=first line\nMIIEvSECRETLINE", "NORMAL=value"],
                "Cmd": [],
                "Entrypoint": [],
                "Labels": {},
            },
            "HostConfig": {"LogConfig": {"Type": "local"}, "RestartPolicy": {}},
            "Mounts": [],
        }]
        result = self.run_container_parser(payload)
        self.assertIn('"env_names":["CERT","NORMAL"]', result)
        self.assertNotIn("first line", result)
        self.assertNotIn("MIIEvSECRETLINE", result)
        self.assertNotIn("NORMAL=value", result)

    def test_command_secrets_and_volume_values_are_not_printed(self) -> None:
        payload = [{
            "Name": "/odoo_web",
            "Id": "container-id",
            "Image": "image-id",
            "State": {"Running": True},
            "Config": {
                "Image": "odoo:test",
                "Env": [],
                "Cmd": [
                    "sh", "-c", "curl -H 'Authorization: Bearer embedded-secret'",
                    "--db_password=hunter2", "--token", "secret-token", "--workers=2",
                    "-whunter2", "postgresql://person:hunter2@db.invalid/database",
                ],
                "Entrypoint": [],
                "Labels": {},
            },
            "HostConfig": {"LogConfig": {"Type": "local"}, "RestartPolicy": {}},
            "Mounts": [],
        }]
        result = self.run_container_parser(payload)
        self.assertIn("--db_password=[arg]", result)
        self.assertIn('"--token","[arg]"', result)
        self.assertIn("-w[arg]", result)
        self.assertNotIn("hunter2", result)
        self.assertNotIn("secret-token", result)
        self.assertNotIn("embedded-secret", result)
        self.assertNotIn("person", result)
        self.assertNotIn("db.invalid", result)

        previous = sys.stdin
        output = StringIO()
        try:
            sys.stdin = StringIO(json.dumps([{
                "Name": "remote", "Driver": "local", "Mountpoint": "/mnt/remote",
                "Options": {"password": "hunter2", "username": "person"},
                "Labels": {"project": "audit"},
            }]))
            with redirect_stdout(output):
                helpers.docker_volumes()
        finally:
            sys.stdin = previous
        result = output.getvalue()
        self.assertIn('"option_names":["password","username"]', result)
        self.assertNotIn("hunter2", result)
        self.assertNotIn("person", result)

    def test_proxy_and_cron_sanitisation_drops_low_entropy_secret_oracles(self) -> None:
        labels = helpers.safe_labels({
            "traefik.http.routers.erp.rule": "Host(`erp.invalid`) && Header(`X-Key`, `hunter2`)",
            "com.example.token": "secret-token",
        }, proxy=True)
        rendered = json.dumps(labels, sort_keys=True)
        self.assertNotIn("hunter2", rendered)
        self.assertNotIn("secret-token", rendered)
        self.assertEqual(helpers.safe_proxy_target(
            "https://person:hunter2@proxy.invalid/secret-path?token=secret-token"
        ), "https://proxy.invalid")

        cron = helpers.masked_cron_command(
            "SECRET=hunter2 /usr/local/bin/backup --token=secret-token --quiet"
        )
        self.assertIn("executable=/usr/local/bin/backup", cron)
        self.assertIn("--token", cron)
        self.assertNotIn("hunter2", cron)
        self.assertNotIn("secret-token", cron)

        for system_style, line in (
            (False, "@reboot PGPASSWORD=hunter2 pg_dump -h db example"),
            (True, "@daily root PGPASSWORD=hunter2 pg_dump -h db example"),
        ):
            output = StringIO()
            with redirect_stdout(output):
                helpers.cron_line(Path("/etc/crontab" if system_style else "/var/spool/cron/root"), 1, line, system_style)
            rendered_cron = output.getvalue()
            self.assertIn("schedule='@", rendered_cron)
            self.assertIn("executable=pg_dump", rendered_cron)
            self.assertNotIn("hunter2", rendered_cron)

        output = StringIO()
        with redirect_stdout(output):
            helpers.cron_line(Path("/etc/cron.d/broken"), 1, "backup hunter2 a b c d", True)
        malformed = output.getvalue()
        self.assertIn("unparsed=yes", malformed)
        self.assertNotIn("hunter2", malformed)

        previous = sys.stdin
        output = StringIO()
        try:
            sys.stdin = StringIO(json.dumps({"filesystems": [
                {
                    "target": "/mnt/share", "source": "//server/share", "fstype": "cifs",
                    "options": "rw,username=person,credentials=/secret/path,password=hunter2",
                },
                {
                    "target": "/mnt/dav", "source": "https://person:hunter2@dav.invalid/x",
                    "fstype": "fuse", "options": "rw",
                },
                {
                    "target": "/mnt/ssh", "source": "person@host.invalid:/x",
                    "fstype": "fuse.sshfs", "options": "rw",
                },
            ]}))
            with redirect_stdout(output):
                helpers.host_mounts()
        finally:
            sys.stdin = previous
        mounts = output.getvalue()
        self.assertNotIn("person", mounts)
        self.assertNotIn("/secret/path", mounts)
        self.assertNotIn("hunter2", mounts)
        self.assertIn("username=[present]", mounts)
        self.assertIn("https://dav.invalid/x", mounts)
        self.assertIn("[identity]@host.invalid:/x", mounts)

        script = checker.SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("secret path=%p mode=%m uid=%U gid=%G size=%s", script)
        for required in (
            "date -u '+utc=%Y-%m-%dT%H:%M:%SZ' || return",
            "docker version --format 'client={{.Client.Version}} server={{.Server.Version}}' || return",
            'python3 -B "$HELPER" cron-config || return',
            'docker exec -i "$WEB_CONTAINER" du -sb -- "$target" || return',
        ):
            self.assertIn(required, script)


if __name__ == "__main__":
    unittest.main()

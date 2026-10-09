"""Local check of setup_phase2f.py (audit of 6cdc8b9, point 3). Never run on the server.

Runs the real script, through JSON-RPC, against a LOCAL Odoo serving the phase 2 code
(2345e7e) on a local database made with the rehearsal data:
- D1 (integrated equipment without a responsible): ids given by --d1;
- D3 (« Test… »): ids given by --d3;
- --other: an equipment in neither list.

`--apply` refuses every database except artdubati_test: for the apply cases this
harness runs the unchanged script source with only that constant replaced, in memory,
by the local database name. The state is read before and after each case through
JSON-RPC, so a refused run must leave it unchanged.

Usage (local admin of the local database, never a server account):
    ODOO_URL=http://localhost:8099 ODOO_DB=p2f_setup ODOO_LOGIN=admin ODOO_PASSWORD=... \
    python3 check_setup_phase2f.py --d1 1 --d3 4 --other 5 --login admin
"""
import argparse
import contextlib
import io
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "setup_phase2f.py")
parser = argparse.ArgumentParser()
parser.add_argument("--d1", type=int, required=True)
parser.add_argument("--d3", type=int, required=True)
parser.add_argument("--other", type=int, required=True)
parser.add_argument("--login", required=True)
opts = parser.parse_args()
URL, DB = os.environ["ODOO_URL"], os.environ["ODOO_DB"]
if not URL.startswith(("http://localhost", "http://127.0.0.1")) or DB == "artdubati_test":
    raise SystemExit("Local check only: a localhost URL and a local database")
SOURCE = open(SCRIPT, encoding="utf-8").read()
CONSTANT = 'ALLOWED_DB = "artdubati_test"'
assert SOURCE.count(CONSTANT) == 1


def state():
    """Responsible and active flag of the three equipment, read through JSON-RPC."""
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())

    def post(path, params):
        req = urllib.request.Request(URL + path, json.dumps({"jsonrpc": "2.0", "params": params}).encode(),
                                     {"Content-Type": "application/json"})
        return json.load(opener.open(req))["result"]

    post("/web/session/authenticate", {"db": DB, "login": os.environ["ODOO_LOGIN"],
                                       "password": os.environ["ODOO_PASSWORD"]})
    rows = post("/web/dataset/call_kw", {
        "model": "maintenance.equipment", "method": "read",
        "args": [[opts.d1, opts.d3, opts.other], ["owner_user_id", "active"]],
        "kwargs": {"context": {"active_test": False}}})
    return {r["id"]: ((r["owner_user_id"] or [None, None])[1], r["active"]) for r in rows}


def run(argv, local_apply=False):
    """Run the script; returns (exit message or None, output)."""
    source = SOURCE.replace(CONSTANT, f'ALLOWED_DB = "{DB}"') if local_apply else SOURCE
    out = io.StringIO()
    sys.argv = [SCRIPT] + argv
    code = None
    with contextlib.redirect_stdout(out):
        try:
            exec(compile(source, SCRIPT, "exec"), {"__name__": "__main__", "__file__": SCRIPT})
        except SystemExit as exc:
            code = None if exc.code in (0, None) else str(exc.code)
    return code, out.getvalue()


failures = []


def case(name, argv, expect_error, expect_change=None, local_apply=False):
    """expect_change(before, after) -> bool; without it the state must not change."""
    before = state()
    code, output = run(argv, local_apply)
    after = state()
    changed_ok = expect_change(before, after) if expect_change else after == before
    ok = (bool(code) == bool(expect_error)
          and (not expect_error or expect_error in code)
          and changed_ok)
    print(f"{'OK  ' if ok else 'FAIL'} {name}")
    print(f"     args: {' '.join(argv)}")
    print(f"     exit: {code or 'none'}")
    print(f"     state before {before}\n     state after  {after}")
    if not ok:
        failures.append(name)
        print(output)


L = opts.login
case("unchanged script refuses --apply on a database other than artdubati_test",
     ["--responsible", f"{opts.d1}={L}", "--apply"], "Refusing to modify")
case("D1 target valid (dry run)", ["--responsible", f"{opts.d1}={L}"], None)
case("target outside D1 refused (dry run)", ["--responsible", f"{opts.other}={L}"],
     f"equipment {opts.other} is not in the D1 list")
case("D3 target valid (dry run)", ["--archive-equipment", str(opts.d3)], None)
case("target outside D3 refused (dry run)", ["--archive-equipment", str(opts.other)],
     f"--archive-equipment {opts.other}: not in the D3 list")
case("valid D1 + invalid D3 with --apply: nothing written",
     ["--responsible", f"{opts.d1}={L}", "--archive-equipment", str(opts.other), "--apply"],
     "Errors, nothing written", local_apply=True)
case("invalid D1 + valid D3 with --apply: nothing written",
     ["--responsible", f"{opts.other}={L}", "--archive-equipment", str(opts.d3), "--apply"],
     "Errors, nothing written", local_apply=True)
case("valid D1 and D3 with --apply: both written",
     ["--responsible", f"{opts.d1}={L}", "--archive-equipment", str(opts.d3), "--apply"],
     None, local_apply=True,
     expect_change=lambda before, after: (
         before[opts.d1][0] is None and after[opts.d1][0] is not None
         and before[opts.d3][1] is True and after[opts.d3][1] is False
         and after[opts.other] == before[opts.other]))
print("\nCHECK", "FAILED: " + ", ".join(failures) if failures else "OK")
sys.exit(1 if failures else 0)

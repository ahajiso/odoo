"""Code fingerprint of the installed modules (audit of d8d5b22..c3670fe). Read-only.

Prints, for every installed module, the SHA-256 of its source files (relative path and
content of every file of the module folder, sorted; __pycache__, .pyc and .git
excluded), so that the code tested locally can be compared with the code running on
artdubati_test, whatever its origin (Odoo image, OCA folder, git or not). Run through
the Odoo shell, the same way on both sides:

    docker exec -i odoo_web odoo shell -d artdubati_test --no-http \
      < docs/phase4/platform.py 2>/dev/null | grep '^MODULE '

Output: « MODULE <name> <version> <sha256> <folder of its addons path> ».
"""
import hashlib
import os

from odoo.modules.module import get_module_path

SKIP_DIRS = {"__pycache__", ".git"}
SKIP_SUFFIXES = (".pyc", ".pyo")


def module_hash(path):
    digest = hashlib.sha256()
    for root, dirs, files in os.walk(path):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            if name.endswith(SKIP_SUFFIXES):
                continue
            full = os.path.join(root, name)
            digest.update(os.path.relpath(full, path).encode())
            digest.update(b"\0")
            with open(full, "rb") as handle:
                digest.update(handle.read())
            digest.update(b"\0")
    return digest.hexdigest()


modules = env["ir.module.module"].search(  # noqa: F821
    [("state", "=", "installed")], order="name")
for module in modules:
    path = get_module_path(module.name, display_warning=False)
    if not path:
        print("MODULE %s %s missing -" % (module.name, module.latest_version))
        continue
    print("MODULE %s %s %s %s" % (module.name, module.latest_version, module_hash(path),
                                  os.path.dirname(os.path.realpath(path))))

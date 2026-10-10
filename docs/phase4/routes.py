"""Inventory of the HTTP routes of the installed modules, for the investor accounts
(P4-2f, docs/phase4/ROUTES.md). Read only. Run it after every module installation or
update, through the Odoo shell:

    docker exec -i odoo_web odoo shell -d artdubati_test --no-http \
      < docs/phase4/routes.py 2>/dev/null | grep '^ROUTE'

Prints one line per route: ROUTE | auth | type | allowed or refused to investor
sessions | URL | module of the controller. Authenticated routes (auth user / bearer)
are refused to investor accounts unless listed in INVESTOR_ROUTES, public routes unless
listed in INVESTOR_PUBLIC_ROUTES (anonymous requests are not filtered); auth « none »
routes have no user.
"""
from odoo.http import _generate_routing_rules

from odoo.addons.lartdubati_investor_home.models.investor_security import (
    INVESTOR_PUBLIC_ROUTES,
    INVESTOR_ROUTES,
)

modules = env["ir.module.module"].search([("state", "=", "installed")]).mapped("name")  # noqa: F821
ordered = ["base", "web"] + sorted(set(modules) - {"base", "web"})
rows = set()
for url, endpoint in _generate_routing_rules(ordered, nodb_only=False):
    auth = endpoint.routing.get("auth")
    allowed = {"user": INVESTOR_ROUTES, "bearer": INVESTOR_ROUTES,
               "public": INVESTOR_PUBLIC_ROUTES}.get(auth)
    if allowed is None:
        status = "no user"
    else:
        status = "allowed" if url in allowed else "refused"
    original = getattr(endpoint, "original_endpoint", endpoint)
    rows.add((auth, endpoint.routing.get("type"), status, url, original.__module__))
for row in sorted(rows, key=lambda r: (r[2], r[3])):
    print("ROUTE | " + " | ".join(str(value) for value in row))

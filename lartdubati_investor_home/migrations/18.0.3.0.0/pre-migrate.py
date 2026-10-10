"""Phase 4 (docs/phase4/PLAN.md §3, P4-0): adopt the investor home page records created
by docs/investor_home/setup_investor_home.py, so that the module's data updates them
instead of creating duplicates. Found by their English name; stops when a name matches
several records (the precheck lists them first). Read queries and ORM writes only."""
from odoo import SUPERUSER_ID, api

RECORDS = [
    ("investor_home_screen", "quick.start.screen", "quick_start_screen", "Investor Home"),
    ("investor_button_financial", "quick.start.screen.action",
     "quick_start_screen_action", "Financial"),
    ("investor_button_administrative", "quick.start.screen.action",
     "quick_start_screen_action", "Administrative"),
    ("investor_button_commerce", "quick.start.screen.action",
     "quick_start_screen_action", "Commerce & Services"),
    ("investor_button_production", "quick.start.screen.action",
     "quick_start_screen_action", "Production"),
]


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Data = env["ir.model.data"]
    for name, model, table, label in RECORDS:
        if Data.search_count([("module", "=", "lartdubati_investor_home"),
                              ("name", "=", name)]):
            continue
        cr.execute("SELECT to_regclass(%s)", [table])
        if not cr.fetchone()[0]:
            return
        cr.execute(f"SELECT id FROM {table} WHERE name->>'en_US' = %s", [label])
        ids = [row[0] for row in cr.fetchall()]
        if len(ids) > 1:
            raise RuntimeError(f"Phase 4: {len(ids)} records « {label} » in {model}, "
                               "expected at most one (see the precheck).")
        if ids:
            Data.create({"module": "lartdubati_investor_home", "name": name,
                         "model": model, "res_id": ids[0], "noupdate": False})

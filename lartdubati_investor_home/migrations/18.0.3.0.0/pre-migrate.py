"""Phase 4 (docs/phase4/PLAN.md §3, P4-0): adopt the investor home page records created
by docs/investor_home/setup_investor_home.py, so that the module's data updates them
instead of creating duplicates.

A record is found by its name in any of the three languages the script wrote: the
script's `translate()` could leave the last language written (Persian) in the source
value `en_US` (found by the migration rehearsal of 10/10/2026), so the English name
alone is not enough. Stops when a name matches several records (the precheck lists
them first). Read queries and ORM writes only."""
from odoo import SUPERUSER_ID, api

# external ID, model, table, names written by the script (en_US, fr_FR, fa_IR)
RECORDS = [
    ("investor_home_screen", "quick.start.screen", "quick_start_screen",
     ("Investor Home", "Accueil investisseur", "خانه سرمایه‌گذار")),
    ("investor_button_financial", "quick.start.screen.action", "quick_start_screen_action",
     ("Financial", "Financier", "مالی")),
    ("investor_button_administrative", "quick.start.screen.action",
     "quick_start_screen_action", ("Administrative", "Administratif", "اداری")),
    ("investor_button_commerce", "quick.start.screen.action", "quick_start_screen_action",
     ("Commerce & Services", "Commerce et services", "بازرگانی و خدمات")),
    ("investor_button_production", "quick.start.screen.action", "quick_start_screen_action",
     ("Production", "Production", "تولید")),
]


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Data = env["ir.model.data"]
    for name, model, table, labels in RECORDS:
        if Data.search_count([("module", "=", "lartdubati_investor_home"),
                              ("name", "=", name)]):
            continue
        cr.execute("SELECT to_regclass(%s)", [table])
        if not cr.fetchone()[0]:
            return
        labels = list(labels)
        cr.execute(f"""
            SELECT id FROM {table}
             WHERE name->>'en_US' = ANY(%s) OR name->>'fr_FR' = ANY(%s)
                OR name->>'fa_IR' = ANY(%s)
        """, [labels, labels, labels])
        ids = [row[0] for row in cr.fetchall()]
        if len(ids) > 1:
            raise RuntimeError(f"Phase 4: {len(ids)} records named {labels} in {model}, "
                               "expected at most one (see the precheck).")
        if ids:
            Data.create({"module": "lartdubati_investor_home", "name": name,
                         "model": model, "res_id": ids[0], "noupdate": False})

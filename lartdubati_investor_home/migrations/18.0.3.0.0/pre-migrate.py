"""Phase 4 (docs/phase4/PLAN.md §3, P4-0): adopt the investor home page records created
by the old docs/investor_home/setup_investor_home.py, so that the module's data updates
them instead of creating duplicates (audit of dff33cb: never adopt another profile's
screen or buttons).

1. The old investor screen: the one quick start screen named « Investor Home » in any
   of the three languages the script wrote (its `translate()` could leave the Persian
   name in the source value `en_US`, rehearsal of 10/10/2026). None: nothing to adopt
   (the data creates everything); several: stop.
2. Its four buttons, searched only among that screen's buttons, each one by its name
   (any language), its sequence and its current action (the script's server actions,
   or the module's client actions on a second run). A mismatch stops the update.
The precheck (docs/phase4/precheck_home.sql) runs the same checks before the update.
Read queries and ORM writes only."""
from odoo import SUPERUSER_ID, api

MODULE = "lartdubati_investor_home"
SCREEN = ("investor_home_screen",
          ("Investor Home", "Accueil investisseur", "خانه سرمایه‌گذار"))
# external ID, names (en_US, fr_FR, fa_IR), sequence, kind of action
BUTTONS = [
    ("investor_button_financial", ("Financial", "Financier", "مالی"), 10, "financial"),
    ("investor_button_administrative", ("Administrative", "Administratif", "اداری"), 20,
     "soon"),
    ("investor_button_commerce",
     ("Commerce & Services", "Commerce et services", "بازرگانی و خدمات"), 30, "soon"),
    ("investor_button_production", ("Production", "Production", "تولید"), 40, "soon"),
]
NAME_MATCH = "(name->>'en_US' = ANY(%s) OR name->>'fr_FR' = ANY(%s) OR name->>'fa_IR' = ANY(%s))"


def _xmlid_res_id(cr, name):
    cr.execute("SELECT res_id FROM ir_model_data WHERE module = %s AND name = %s",
               [MODULE, name])
    row = cr.fetchone()
    return row and row[0]


def _expected_actions(cr):
    """The actions a button of the old screen may hold, per kind."""
    cr.execute("SELECT id FROM ir_act_server WHERE name->>'en_US' = %s",
               ["Investor Home: coming soon"])
    soon = {f"ir.actions.server,{row[0]}" for row in cr.fetchall()}
    financial = set()
    for name, model in (("action_server_stock_monitor", "ir.actions.server"),
                        ("action_stock_monitor", "ir.actions.client")):
        res_id = _xmlid_res_id(cr, name)
        if res_id:
            financial.add(f"{model},{res_id}")
    coming = _xmlid_res_id(cr, "action_coming_soon")
    if coming:
        soon.add(f"ir.actions.client,{coming}")
    return {"financial": financial, "soon": soon}


def migrate(cr, version):
    cr.execute("SELECT to_regclass('quick_start_screen')")
    if not cr.fetchone()[0]:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Data = env["ir.model.data"]
    screen_id = _xmlid_res_id(cr, SCREEN[0])
    if not screen_id:
        labels = list(SCREEN[1])
        cr.execute(f"SELECT id FROM quick_start_screen WHERE {NAME_MATCH}", [labels] * 3)
        ids = [row[0] for row in cr.fetchall()]
        if not ids:
            return  # no old investor screen: the module's data creates everything
        if len(ids) > 1:
            raise RuntimeError(f"Phase 4: {len(ids)} quick start screens named {labels}, "
                               "expected one (see the precheck).")
        screen_id = ids[0]
        Data.create({"module": MODULE, "name": SCREEN[0], "model": "quick.start.screen",
                     "res_id": screen_id, "noupdate": False})
    expected = _expected_actions(cr)
    for name, labels, sequence, kind in BUTTONS:
        if _xmlid_res_id(cr, name):
            continue
        labels = list(labels)
        cr.execute(f"""
            SELECT a.id, a.sequence, a.action_ref_id
              FROM quick_start_screen_action a
              JOIN quick_start_screen_quick_start_screen_action_rel r
                ON r.quick_start_screen_action_id = a.id AND r.quick_start_screen_id = %s
             WHERE {NAME_MATCH.replace('name', 'a.name')}
        """, [screen_id] + [labels] * 3)
        rows = cr.fetchall()
        if not rows:
            continue  # the data creates it
        if len(rows) > 1 or rows[0][1] != sequence or rows[0][2] not in expected[kind]:
            raise RuntimeError(
                f"Phase 4: button {labels[0]} of the investor screen does not match "
                f"(found {rows}, expected sequence {sequence} and one of "
                f"{sorted(expected[kind])}; see the precheck).")
        Data.create({"module": MODULE, "name": name, "model": "quick.start.screen.action",
                     "res_id": rows[0][0], "noupdate": False})

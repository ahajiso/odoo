"""Phase 4 (docs/phase4/PLAN.md §3, P4-4): every existing investor account opens the
investor home page (window action), instead of the OCA server action the setup script
set, which investor accounts can no longer run."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    group = env.ref("lartdubati_investor_home.group_stock_investor")
    group.with_context(active_test=False).users._set_investor_home()

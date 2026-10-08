from odoo import SUPERUSER_ID, api

from odoo.addons.maintenance_shareholder_equipment.hooks import set_default_rent_account


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    set_default_rent_account(env)

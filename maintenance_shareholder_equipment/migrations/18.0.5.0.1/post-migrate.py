"""« Item and Service Requests » (docs/roadmap0/MENU_PLAN.md).

An update keeps the existing French and Persian values of a record whose English source
changed (the action, its help, the menus, the field label, the view titles): they would
still read « Demandes de produit » / « درخواست‌های محصول ». Odoo loads the .po files
right after this script without overwriting; this script reloads this module's own .po
files with overwrite first, through the module's standard method (no SQL). Only this
module's terms are concerned; a translation edited by hand in the interface for one of
them is replaced by the file's.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)
MODULE = "maintenance_shareholder_equipment"


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    module = env["ir.module.module"].search([("name", "=", MODULE)])
    module._update_translations(overwrite=True)
    _logger.info("%s: translations of the module reloaded with overwrite", MODULE)

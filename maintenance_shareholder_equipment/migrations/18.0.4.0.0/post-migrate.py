"""Phase 3: the monitor stocks (docs/phase3/PLAN.md §6.2).

Candidates: the stock location of every active warehouse and every active lent-out
location. Each is flagged « Monitor Stock » with the company currency, through the ORM:
the constraint refuses a monitor stock whose address has no city or no country, and
the update then fails (the precheck lists such stocks before the update).
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Location = env["stock.location"]
    candidates = env["stock.warehouse"].search([]).lot_stock_id | Location.search(
        [("place_type", "=", "lent_out"), ("usage", "=", "internal")])
    for location in candidates.filtered(lambda loc: not loc.is_monitor_stock):
        company = location.company_id or env.company
        location.write({"is_monitor_stock": True,
                        "monitor_currency_id": company.currency_id.id})
    _logger.info("Phase 3 monitor stocks: %s", candidates.mapped("complete_name"))

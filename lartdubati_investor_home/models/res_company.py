from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Read by the stock monitor view (lartdubati.stock.monitor): stored on the company
    # so that the SQL view can read them.
    # P9 (phase 3, test choice, C12): each amount at the rate of its own date by
    # default; « No Conversion » removed (docs/phase3/PLAN.md §3.5).
    stock_monitor_currency_mode = fields.Selection(
        [
            ("historical", "Rate at Each Amount's Date"),
            ("latest", "Latest Rate"),
        ],
        string="Stock Monitor Currency Conversion",
        default="historical",
        required=True,
    )
    # P7: a replacement value older than this is flagged « to check »
    stock_monitor_replacement_max_age = fields.Integer(
        string="Replacement Value Validity (months)",
        default=12,
        required=True,
    )

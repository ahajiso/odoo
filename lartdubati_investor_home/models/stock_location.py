from odoo import fields, models


class StockLocation(models.Model):
    _inherit = "stock.location"

    # The address comes from the warehouse (standard): a stock at another
    # address is set up as its own warehouse.
    place_type = fields.Selection(
        [
            ("physical", "Physical"),
            ("lent_out", "Lent Out"),
            ("virtual", "Virtual"),
        ],
        default="physical",
        required=True,
        help="Lent Out: the stock that lent-out items belong to and return to.",
    )

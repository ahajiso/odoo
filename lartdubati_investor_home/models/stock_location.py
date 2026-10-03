from odoo import api, fields, models


class StockLocation(models.Model):
    _inherit = "stock.location"

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
    # Copied from the warehouse address, then editable per stock.
    country_id = fields.Many2one(
        "res.country",
        compute="_compute_address",
        store=True,
        readonly=False,
    )
    state_id = fields.Many2one(
        "res.country.state",
        string="State",
        compute="_compute_address",
        store=True,
        readonly=False,
        domain="[('country_id', '=?', country_id)]",
    )
    city = fields.Char(compute="_compute_address", store=True, readonly=False)
    currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_currency_id",
        store=True,
        readonly=False,
        help="Currency the stock is reported in.",
    )

    @api.depends(
        "warehouse_id.partner_id.country_id",
        "warehouse_id.partner_id.state_id",
        "warehouse_id.partner_id.city",
    )
    def _compute_address(self):
        for location in self:
            partner = location.warehouse_id.partner_id
            if partner:
                location.country_id = partner.country_id
                location.state_id = partner.state_id
                location.city = partner.city

    @api.depends("company_id")
    def _compute_currency_id(self):
        for location in self:
            if not location.currency_id:
                location.currency_id = (
                    location.company_id or self.env.company
                ).currency_id

from odoo import fields, models

from .ownership import RENT_PERIOD_SELECTION


class StockRental(models.Model):
    """Rent paid for consumables owned by a third party (stock.quant owner)."""

    _name = "lartdubati.stock.rental"
    _description = "Consumable Rental Terms"
    _order = "rent_start_date desc, id desc"
    _rec_name = "product_id"

    owner_id = fields.Many2one("res.partner", string="Owner", required=True, index=True)
    product_id = fields.Many2one(
        "product.product",
        required=True,
        index=True,
        domain="[('is_storable', '=', True)]",
    )
    rent_amount = fields.Monetary(required=True)
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    rent_period = fields.Selection(RENT_PERIOD_SELECTION, required=True, default="month")
    rent_start_date = fields.Date(required=True, default=fields.Date.context_today)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "owner_product_unique",
            "unique(owner_id, product_id, company_id)",
            "Rental terms already exist for this owner and product.",
        ),
    ]

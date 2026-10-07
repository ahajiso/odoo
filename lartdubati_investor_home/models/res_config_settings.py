from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    stock_monitor_currency_mode = fields.Selection(
        related="company_id.stock_monitor_currency_mode", readonly=False
    )
    stock_monitor_replacement_price = fields.Selection(
        related="company_id.stock_monitor_replacement_price", readonly=False
    )

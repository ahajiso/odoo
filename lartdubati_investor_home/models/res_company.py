from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Read by the stock monitor reports (docs/stock_monitor/*.sql): OCA
    # bi_sql_editor forbids reading system parameters, so these choices are
    # stored on the company.
    stock_monitor_currency_mode = fields.Selection(
        [
            ("latest", "Latest Rate"),
            ("entry_date", "Rate on Entry Date"),
            ("none", "No Conversion"),
        ],
        string="Stock Monitor Currency Conversion",
        default="latest",
        required=True,
    )
    stock_monitor_replacement_price = fields.Selection(
        [("cost", "Product Cost"), ("list_price", "Sales Price")],
        string="Stock Monitor Replacement Price",
        default="cost",
        required=True,
    )

from odoo import api, fields, models
from odoo.osv import expression


class StockAccess(models.Model):
    """Stock access profile for restricted (investor) users.

    An empty list on a dimension means no restriction on that dimension.
    """

    _name = "lartdubati.stock.access"
    _description = "Stock Access Profile"

    name = fields.Char(required=True, translate=True)
    country_ids = fields.Many2many("res.country", string="Allowed Countries")
    location_ids = fields.Many2many(
        "stock.location",
        string="Allowed Stocks",
        domain="[('usage', '=', 'internal')]",
        help="Sub-locations of an allowed stock are allowed too.",
    )
    ownership_type_ids = fields.Many2many(
        "lartdubati.ownership.type", string="Allowed Ownership"
    )
    family_ids = fields.Many2many("lartdubati.item.family", string="Allowed Families")
    user_ids = fields.One2many("res.users", "stock_access_id", string="Users")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.registry.clear_cache()
        return records

    def write(self, vals):
        res = super().write(vals)
        self.env.registry.clear_cache()
        return res

    def unlink(self):
        res = super().unlink()
        self.env.registry.clear_cache()
        return res

    def _location_domain(self):
        """Record-rule domain on stock.location for this profile."""
        if not self:
            return expression.FALSE_DOMAIN
        self.ensure_one()
        domain = []
        if self.location_ids:
            domain.append([("id", "child_of", self.location_ids.ids)])
        if self.country_ids:
            domain.append(
                [("warehouse_id.partner_id.country_id", "in", self.country_ids.ids)]
            )
        return expression.AND(domain) if domain else expression.TRUE_DOMAIN

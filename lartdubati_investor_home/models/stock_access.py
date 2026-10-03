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

    def _rule_domain(self, target):
        """Record-rule domain for target 'equipment', 'quant' or 'location'."""
        if not self:
            return expression.FALSE_DOMAIN
        self.ensure_one()
        families = set(self.family_ids.mapped("code"))
        ownerships = self.ownership_type_ids.mapped("code")
        location_ids = self.location_ids.ids
        country_ids = self.country_ids.ids

        if target == "location":
            domain = []
            if location_ids:
                domain.append([("id", "child_of", location_ids)])
            if country_ids:
                domain.append([("country_id", "in", country_ids)])
            return expression.AND(domain) if domain else expression.TRUE_DOMAIN

        family = "asset" if target == "equipment" else "consumable"
        if families and family not in families:
            return expression.FALSE_DOMAIN
        location_field = "current_location_id" if target == "equipment" else "location_id"
        domain = []
        if ownerships:
            domain.append([("ownership", "in", ownerships)])
        if location_ids:
            domain.append([(location_field, "child_of", location_ids)])
        if country_ids:
            domain.append([(f"{location_field}.country_id", "in", country_ids)])
        return expression.AND(domain) if domain else expression.TRUE_DOMAIN

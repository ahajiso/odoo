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
        """Record-rule domain on stock.location for this profile.

        Country: the sub-locations of the monitor stocks whose own address is in an
        allowed country (never warehouse_id: Bg/Stock is outside its warehouse root).
        The stocks are searched here, so the rule cache is cleared whenever a stock's
        flag, parent or address changes (StockLocation, ResPartner below)."""
        if not self:
            return expression.FALSE_DOMAIN
        self.ensure_one()
        domain = []
        if self.location_ids:
            domain.append([("id", "child_of", self.location_ids.ids)])
        if self.country_ids:
            stocks = self.env["stock.location"].sudo().search([
                ("is_monitor_stock", "=", True),
                ("address_id.country_id", "in", self.country_ids.ids),
            ])
            domain.append([("id", "child_of", stocks.ids)] if stocks
                          else expression.FALSE_DOMAIN)
        return expression.AND(domain) if domain else expression.TRUE_DOMAIN

    def _monitor_domain(self):
        """Record-rule domain on the stock monitor (lartdubati.stock.monitor) for this
        profile. Rules are evaluated as superuser: the fields reserved to staff (ids)
        can be used here without giving the investor any right on them."""
        if not self:
            return expression.FALSE_DOMAIN
        self.ensure_one()
        domain = []
        if self.family_ids:
            domain.append([("family", "in", self.family_ids.mapped("code"))])
        if self.ownership_type_ids:
            domain.append([("ownership_status", "in", self.ownership_type_ids.mapped("code"))])
        if self.location_ids:
            ids = self.location_ids.ids
            domain.append(["|", ("stock_id", "child_of", ids), ("location_id", "child_of", ids)])
        if self.country_ids:
            domain.append([("country_id", "in", self.country_ids.ids)])
        return expression.AND(domain) if domain else expression.TRUE_DOMAIN


class StockLocation(models.Model):
    _inherit = "stock.location"

    def write(self, vals):
        res = super().write(vals)
        if {"is_monitor_stock", "address_id", "location_id", "active"} & set(vals):
            self.env.registry.clear_cache()  # location rule of the access profiles
        return res


class ResPartner(models.Model):
    _inherit = "res.partner"

    def write(self, vals):
        res = super().write(vals)
        if "country_id" in vals and self.env["stock.location"].sudo().search_count(
                [("is_monitor_stock", "=", True), ("address_id", "in", self.ids)], limit=1):
            self.env.registry.clear_cache()  # location rule of the access profiles
        return res

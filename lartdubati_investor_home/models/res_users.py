from odoo import fields, models
from odoo.osv import expression


class ResUsers(models.Model):
    _inherit = "res.users"

    stock_access_id = fields.Many2one(
        "lartdubati.stock.access",
        string="Stock Access Profile",
        groups="base.group_erp_manager",
        help="Only used for members of the Stock Monitor Investor group. "
        "A member without a profile sees no stock.",
    )

    def write(self, vals):
        res = super().write(vals)
        if "stock_access_id" in vals:
            self.env.registry.clear_cache()
        return res

    def stock_access_rule_domain(self, target):
        """Domain used by the global record rules of this module.

        Always computed for the current user, whatever record it is called on.
        """
        user = self.env.user.sudo()
        if not user.has_group("lartdubati_investor_home.group_stock_investor"):
            return expression.TRUE_DOMAIN
        if target == "location":
            # Partner, transit and virtual locations stay readable so that
            # pickings keep working.
            return expression.OR(
                [[("usage", "!=", "internal")], user.stock_access_id._location_domain()]
            )
        if target == "monitor":
            return user.stock_access_id._monitor_domain()
        if target == "move_line":
            # standard stock gives every internal user read, write, create and delete
            # on all move lines (access_stock_move_line_all): an investor without
            # Inventory rights gets none (audit of 888d229)
            if user.has_group("stock.group_stock_user"):
                return expression.TRUE_DOMAIN
            return expression.FALSE_DOMAIN
        raise ValueError(target)

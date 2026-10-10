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
        # phase 4 (docs/phase4/PLAN.md §2, P4-2b): the few models an investor account
        # may read, narrowed to its own records
        if target == "menu":
            root = self.env.ref("lartdubati_investor_home.menu_stock_monitor_root")
            return [("id", "child_of", root.id)]
        if target == "home_screen":
            screen = self.env.ref("lartdubati_investor_home.investor_home_screen",
                                  raise_if_not_found=False)
            return [("id", "=", screen.id)] if screen else expression.FALSE_DOMAIN
        if target == "home_button":
            # the buttons named in INVESTOR_BUTTONS, not whatever the screen lists
            from .investor_security import INVESTOR_BUTTONS
            buttons = [self.env.ref(xmlid, raise_if_not_found=False)
                       for xmlid in INVESTOR_BUTTONS]
            return [("id", "in", [button.id for button in buttons if button])]
        if target == "user":
            return [("id", "=", user.id)]
        if target == "partner":
            return [("id", "in", (user.partner_id | user.company_ids.partner_id).ids)]
        if target == "none":
            return expression.FALSE_DOMAIN
        if target == "users_settings":
            return [("user_id", "=", user.id)]
        if target == "own_presence":
            return [("user_id", "=", user.id)]
        if target == "own_created":
            return [("create_uid", "=", user.id)]
        if target == "move_line":
            # standard stock gives every internal user read, write, create and delete
            # on all move lines (access_stock_move_line_all): an investor without
            # Inventory rights gets none (audit of 888d229)
            if user.has_group("stock.group_stock_user"):
                return expression.TRUE_DOMAIN
            return expression.FALSE_DOMAIN
        raise ValueError(target)

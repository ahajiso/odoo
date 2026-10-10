"""Phase 4: investor accounts read only the stock monitor (docs/phase4/PLAN.md §2).

An investor account is a member of « Stock Monitor Investor »; it may hold no other
group than Internal User, the groups Internal User implies (transitively) and « Access
to export feature » (P4-5). For such an account, outside sudo:
- P4-2a: every model is refused except INVESTOR_MODELS (central default deny in
  `ir.model.access`, whatever ACL other modules grant);
- P4-2d: no server action runs; the home buttons open only their own action.
The record rules (security.xml) narrow the few listed models.
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

INVESTOR_GROUP = "lartdubati_investor_home.group_stock_investor"

# P4-2a: the models an investor account may access, per mode; each one justified in
# docs/phase4/PLAN.md §2 and tested (tests/test_investor_security.py)
INVESTOR_MODELS = {
    "read": frozenset({
        "lartdubati.stock.monitor",  # the monitor (profile and company rules)
        "quick.start.screen",  # home page (rule: the investor screen)
        "quick.start.screen.action",  # home buttons (rule: the investor buttons)
        "res.users",  # web client session (rule: own record)
        "res.partner",  # own avatar and name (rule: own and company partner)
        "res.company",  # company name, currency (standard multi-company rule)
        "res.currency",  # amounts of the dashboard
        "res.lang",  # language switch in the preferences
        "res.users.settings",  # web client settings (rule: own record)
        "ir.ui.menu",  # menu loading runs as the user (rule: monitor tree)
        # the mail client init (/mail/data) and the websocket subscription search the
        # user's channels as the user; the rule shows none (no message ever reaches an
        # investor account through a channel)
        "discuss.channel",
        "discuss.channel.member",  # same, mail client init (rule: none)
        "mail.message",  # same, mail client init: inbox / starred (rule: none)
        "mail.activity",  # activity systray of the web client (rule: none)
        "ir.filters",  # favourite filters loaded with the views (rule: none)
    }),
    "write": frozenset({
        "res.users.settings",  # web client settings (rule: own record)
    }),
    "create": frozenset(),
    "unlink": frozenset(),
}

# P4-2d: actions an investor account may load, by external ID
INVESTOR_ACTIONS = (
    "lartdubati_investor_home.action_investor_home",
    "lartdubati_investor_home.action_stock_monitor",
    "lartdubati_investor_home.action_stock_monitor_analysis",
    "lartdubati_investor_home.action_coming_soon",
)
# P4-2d: each home button and the exact action it may open: (model, external ID, tag)
INVESTOR_BUTTONS = {
    "lartdubati_investor_home.investor_button_financial": (
        "ir.actions.client", "lartdubati_investor_home.action_stock_monitor",
        "lartdubati_stock_monitor"),
    "lartdubati_investor_home.investor_button_administrative": (
        "ir.actions.client", "lartdubati_investor_home.action_coming_soon",
        "lartdubati_coming_soon"),
    "lartdubati_investor_home.investor_button_commerce": (
        "ir.actions.client", "lartdubati_investor_home.action_coming_soon",
        "lartdubati_coming_soon"),
    "lartdubati_investor_home.investor_button_production": (
        "ir.actions.client", "lartdubati_investor_home.action_coming_soon",
        "lartdubati_coming_soon"),
}


def is_investor(env):
    """True for an investor account outside sudo. Read in sudo (cached): this is called
    from the access check itself."""
    return not env.su and env.user.sudo()._has_group(INVESTOR_GROUP)


class IrModelAccess(models.Model):
    _inherit = "ir.model.access"

    def _get_allowed_models(self, mode="read"):
        allowed = super()._get_allowed_models(mode)
        if is_investor(self.env):
            return allowed & INVESTOR_MODELS[mode]
        return allowed


class Base(models.AbstractModel):
    _inherit = "base"

    def export_data(self, fields_to_export):
        # exporting only `id` reads nothing (Odoo builds the external IDs in sudo): an
        # investor account must be able to read the records it exports
        if is_investor(self.env):
            self.check_access("read")
        return super().export_data(fields_to_export)


class IrActionsServer(models.Model):
    _inherit = "ir.actions.server"

    def run(self):
        # before anything, in particular before run() works in sudo
        if is_investor(self.env):
            raise AccessError(_("Investor accounts cannot run server actions."))
        return super().run()


class QuickStartScreenAction(models.Model):
    _inherit = "quick.start.screen.action"

    def run_action(self):
        self.ensure_one()
        if not is_investor(self.env):
            return super().run_action()
        self.check_access("read")  # the record rule: only the investor screen's buttons
        button = self.sudo()
        xmlid = button.get_external_id().get(button.id)
        expected = INVESTOR_BUTTONS.get(xmlid)
        action = button.action_ref_id
        if not expected or not action or action._name != expected[0] \
                or action != self.env.ref(expected[1], raise_if_not_found=False) \
                or action.tag != expected[2]:
            raise AccessError(_("This button is not available to investor accounts."))
        return super(QuickStartScreenAction, button).run_action()


class ResUsers(models.Model):
    _inherit = "res.users"

    investor_without_profile = fields.Boolean(compute="_compute_investor_without_profile")

    @api.depends("groups_id", "stock_access_id")
    def _compute_investor_without_profile(self):
        group = self.env.ref(INVESTOR_GROUP)
        for user in self:
            user.investor_without_profile = group in user.groups_id \
                and not user.sudo().stock_access_id

    @api.model
    def _investor_allowed_groups(self):
        """P4-5: the groups an investor account may hold, computed (never a fixed
        list): the investor group, Internal User and every group it implies
        transitively (Technical Features, Multi Currencies...), export."""
        internal = self.env.ref("base.group_user")
        return (self.env.ref(INVESTOR_GROUP) | internal | internal.trans_implied_ids
                | self.env.ref("base.group_allow_export"))

    @api.constrains("groups_id")
    def _check_investor_groups(self):
        group = self.env.ref(INVESTOR_GROUP)
        allowed = self._investor_allowed_groups()
        for user in self.sudo():
            if group not in user.groups_id:
                continue
            forbidden = user.groups_id - allowed
            if forbidden:
                raise ValidationError(_(
                    "%(user)s is an investor account: it may not hold other rights. "
                    "Remove: %(groups)s.", user=user.name,
                    groups=", ".join(sorted(forbidden.mapped("full_name")))))

    def _set_investor_home(self):
        """P4-4: an investor account opens the investor home page."""
        group = self.env.ref(INVESTOR_GROUP)
        home = self.env.ref("lartdubati_investor_home.action_investor_home",
                            raise_if_not_found=False)
        screen = self.env.ref("lartdubati_investor_home.investor_home_screen",
                              raise_if_not_found=False)
        if not home:
            return
        # the OCA server action the setup script used to set: an investor account can no
        # longer run it (P4-2d)
        old = self.env.ref("web_quick_start_screen.start_screen_action",
                           raise_if_not_found=False)
        for user in self.sudo().filtered(lambda u: group in u.groups_id):
            vals = {}
            # action_id is an ir.actions.actions: compare ids, not records of two models
            if not user.action_id or (old and user.action_id.id == old.id):
                vals["action_id"] = home.id
            if screen and not user.quick_start_screen_id:
                vals["quick_start_screen_id"] = screen.id
            if vals:
                user.write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users._set_investor_home()
        return users

    def write(self, vals):
        res = super().write(vals)
        if "groups_id" in vals or any(key.startswith("in_group_") or key.startswith("sel_groups_")
                                      for key in vals):
            self._set_investor_home()
        return res

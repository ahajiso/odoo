"""Phase 4: investor accounts read only the stock monitor (docs/phase4/PLAN.md §2).

An investor account is a member of « Stock Monitor Investor »; it may hold no other
group than Internal User, the groups Internal User implies (transitively) and « Access
to export feature » (P4-5). For such an account, outside sudo:
- P4-2a: every model is refused except INVESTOR_MODELS (central default deny in
  `ir.model.access`, whatever ACL other modules grant);
- P4-2d: no server action runs; the home buttons open only their own action.
The record rules (security.xml) narrow the few listed models.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)

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
        # own password change (audit of 6063db1): the standard wizard and the password
        # check it asks for first (rules: own records only)
        "change.password.own",
        "res.users.identitycheck",
        # own online status, written by the websocket as the user (rule: own record)
        "bus.presence",
        # the websocket subscription searches the guests whose presence the client asks
        # for, as the user (rule: none)
        "mail.guest",
    }),
    "write": frozenset({
        "res.users.settings",  # web client settings (rule: own record)
        "change.password.own",
        "res.users.identitycheck",  # the password typed (the check runs in sudo)
        "bus.presence",
    }),
    # res.users.identitycheck is created in sudo by @check_identity
    "create": frozenset({"change.password.own", "bus.presence"}),
    "unlink": frozenset({"change.password.own"}),  # change_password() unlinks it
}

# P4-2e (audit of dff33cb): the public methods an investor account may call through
# /web/dataset/call_kw and call_button. A public method may work in sudo or in SQL
# without any ORM check (e.g. stock.picking.type.get_action_picking_tree_ready returns
# an action read in sudo), so the model whitelist alone is not enough: the model must be
# listed AND the method. Standard reads only, plus what the web client needs (found by
# the tours, each one named here).
READ_METHODS = frozenset({
    "fields_get", "get_views", "read", "web_read", "search", "search_read",
    "web_search_read", "search_count", "read_group", "web_read_group", "name_search",
    "has_access",
})
INVESTOR_METHODS = {
    model: READ_METHODS for model in INVESTOR_MODELS["read"]
}
INVESTOR_METHODS.update({
    # the dashboard's aggregates (under the user's rights and rules)
    "lartdubati.stock.monitor": READ_METHODS | {"get_dashboard_data", "export_data"},
    # the home buttons (exact action check in run_action)
    "quick.start.screen.action": READ_METHODS | {"run_action"},
    # own preferences: the user menu opens them (action_get), the dialog saves them
    # through the standard self-writeable fields; activity systray
    # has_group: the list view asks whether the user may export (own groups only)
    "res.users": READ_METHODS | {"action_get", "onchange", "web_save", "has_group",
                                 "preference_change_password", "preference_save",
                                 "systray_get_activities"},
    # web client settings (rule: own record)
    "res.users.settings": READ_METHODS | {"set_res_users_settings"},
    # own password change: the wizard, then the password check (@check_identity)
    "change.password.own": READ_METHODS | {"onchange", "web_save", "change_password"},
    "res.users.identitycheck": READ_METHODS | {"onchange", "web_save", "run_check"},
})

# P4-2f (audit of 6063db1): the authenticated routes (auth « user » or « bearer ») an
# investor account may reach; every other one is refused before its controller runs,
# whatever module adds it later (ir.http._pre_dispatch). Routes resolving models,
# actions or reports themselves, possibly in sudo, are refused this way:
# /web/model/get_definitions, /bus/get_model_definitions, /json, /json/1, /report/*,
# /stock/<format>/<report>... The list comes from the inventory of the routes of the
# installed modules (docs/phase4/ROUTES.md) and from the tours.
INVESTOR_ROUTES = frozenset({
    "/web/webclient/load_menus/<string:unique>",
    "/web/session/get_session_info",
    "/web/session/check",
    "/web/action/load",  # whitelist of actions (controllers/action.py)
    "/web/action/load_breadcrumbs",  # goes through load (same whitelist)
    "/web/dataset/call_kw",  # INVESTOR_METHODS (controllers/dataset.py)
    "/web/dataset/call_kw/<path:path>",
    "/web/dataset/call_button",
    "/web/dataset/call_button/<path:path>",
    "/web/domain/validate",  # custom filter of the analysis views (search_count as the user)
    # export of the monitor (P4-5, controllers/export.py) and the pivot download (the
    # client sends the table it shows, nothing is read)
    "/web/export/formats",
    "/web/export/get_fields",
    "/web/export/namelist",
    "/web/export/csv",
    "/web/export/xlsx",
    "/web/pivot/export_xlsx",
})

# P4-2g (audit of 2071e6e): the public routes (auth « public ») an investor account may
# reach once logged in. A public route runs as the logged-in user and may behave
# differently than for an anonymous visitor (internal-user branches, sudo): for an
# investor session every other one is refused. Anonymous requests are not concerned
# (login page, assets, token links). Found by the tours (docs/phase4/ROUTES.md).
INVESTOR_PUBLIC_ROUTES = frozenset({
    "/web/assets/<string:unique>/<string:filename>",  # the web client's assets
    "/web/bundle/<string:bundle_name>",  # list of a lazy bundle's asset files
    "/web/webclient/translations/<string:unique>",
    "/web/manifest.webmanifest",
    "/web/service-worker.js",
    "/odoo/offline",  # page the service worker keeps for offline use
    "/web/image",  # avatars: read access checked as the user (default deny, rules)
    "/web/image/<string:model>/<int:id>/<string:field>",
    "/bus/websocket_worker_bundle",
    "/websocket",  # no group channel for investors (ir.websocket below)
    "/mail/data",  # mail client init: own data only (tested with every option)
})


def check_investor_call(env, model, method):
    """P4-2e: refuse to an investor account any call outside INVESTOR_METHODS, before
    the standard controller runs (raises AccessError)."""
    if is_investor(env) and method not in INVESTOR_METHODS.get(model, ()):
        _logger.info("Investor call refused: %s.%s, uid %s", model, method, env.uid)
        raise AccessError(_("This operation is not available to investor accounts."))


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


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _pre_dispatch(cls, rule, args):
        # P4-2f, P4-2g: before the standard pre-dispatch and the controller; auth
        # « none » routes have no user environment
        allowed = {"user": INVESTOR_ROUTES, "bearer": INVESTOR_ROUTES,
                   "public": INVESTOR_PUBLIC_ROUTES}.get(rule.endpoint.routing.get("auth"))
        if allowed is not None and rule.rule not in allowed and request.env.uid \
                and is_investor(request.env):
            _logger.info("Investor route refused: %s, uid %s", rule.rule, request.env.uid)
            raise AccessError(_("This page is not available to investor accounts."))
        return super()._pre_dispatch(rule, args)


class IrWebsocket(models.AbstractModel):
    _inherit = "ir.websocket"

    def _build_bus_channel_list(self, channels):
        # P4-2g: Odoo subscribes every user to the channels of their groups; an investor
        # account would receive what is sent to all internal users (channels
        # auto-subscribing Internal User, shared canned responses). Kept: its own
        # partner, broadcast, and the discussion channels it can read (none, rule).
        channels = super()._build_bus_channel_list(channels)
        if is_investor(self.env):
            channels = [channel for channel in channels
                        if not (isinstance(channel, models.BaseModel)
                                and channel._name == "res.groups")]
        return channels

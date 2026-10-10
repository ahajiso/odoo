"""Phase 4: investor accounts read only the stock monitor (docs/phase4/PLAN.md §2, §4).

Every check runs under the real investor account: the ORM with `with_user`, and an HTTP
session for JSON-RPC, actions and URLs.
"""
import base64

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, tagged
from odoo.tests.common import JsonRpcException

from odoo.addons.lartdubati_investor_home.models.investor_security import (
    INVESTOR_ACTIONS,
    INVESTOR_BUTTONS,
)
from odoo.addons.lartdubati_investor_home.tests.test_stock_monitor import MonitorAccessCommon

# a sample of refused models from every installed area
REFUSED_MODELS = [
    "stock.quant", "stock.picking", "stock.move", "stock.location", "stock.warehouse",
    "stock.lot", "product.product", "product.template", "product.category",
    "maintenance.equipment", "maintenance.request", "equipment.operation",
    "account.move", "account.move.line", "account.account", "account.asset",
    "purchase.order", "contract.contract", "contract.line",
    "mail.followers", "mail.notification", "ir.attachment",
    "res.groups", "ir.actions.server", "ir.actions.client", "ir.actions.act_window",
    "ir.model", "ir.config_parameter", "lartdubati.stock.access", "calendar.event",
]
# a model no rule or list of ours names, readable by every internal user in standard
# Odoo: refused all the same (default deny)
UNNAMED_MODEL = "uom.uom"
PNG = base64.b64encode(
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00"
    b"\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8"
    b"\xbd\x00\x00\x00\x00IEND\xaeB`\x82")


class InvestorSecurityCommon(MonitorAccessCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.investor.groups_id |= cls.env.ref("base.group_allow_export")
        cls.other_user = cls.store

    def _sample(self, model):
        return self.env[model].sudo().with_context(active_test=False).search([], limit=1)


@tagged("post_install", "-at_install")
class TestInvestorDefaultDeny(InvestorSecurityCommon):
    """P4-2a: every model is refused to an investor account except the listed ones."""

    def test_refused_models_in_every_mode(self):
        for model in REFUSED_MODELS + [UNNAMED_MODEL]:
            if model not in self.env:
                continue
            with self.subTest(model=model):
                Model = self.env[model].with_user(self.investor)
                record = self._sample(model).with_user(self.investor)
                calls = {
                    "search": lambda: Model.search([]),
                    "search_count": lambda: Model.search_count([]),
                    "search_read": lambda: Model.search_read([], ["id"]),
                    "read_group": lambda: Model.read_group([], ["id:count"], []),
                    "web_search_read": lambda: Model.web_search_read([], {"id": {}}),
                    "create": lambda: Model.create({}),
                }
                if record:
                    calls.update({
                        "read": lambda: record.read(["display_name"]),
                        "export_data": lambda: record.export_data(["id"]),
                        "unlink": lambda: record.unlink(),
                    })
                    if "name" in Model._fields and Model._fields["name"].store:
                        calls["write"] = lambda: record.write({"name": "Changed"})
                for name, call in calls.items():
                    with self.subTest(call=name):
                        try:
                            call()
                        except AccessError:
                            continue
                        except Exception:  # noqa: BLE001
                            # some create() read their values before the ORM (e.g.
                            # account.move.line): the access check must refuse anyway
                            if name == "create":
                                with self.assertRaises(AccessError):
                                    Model.check_access("create")
                                continue
                            raise
                        self.fail(f"{model}.{name} not refused")

    def test_unnamed_model_is_standard_for_staff(self):
        # the default deny is not a list: uom.uom stays readable by an internal user
        self.assertTrue(self.env[UNNAMED_MODEL].with_user(self.store).search_count([]))

    def test_listed_models_only_own_records(self):
        Users = self.env["res.users"].with_user(self.investor)
        self.assertEqual(Users.search([]), self.investor)
        with self.assertRaises(AccessError):
            self.store.with_user(self.investor).read(["name"])
        Partners = self.env["res.partner"].with_user(self.investor)
        self.assertEqual(Partners.search([]),
                         self.investor.partner_id | self.investor.company_ids.partner_id)
        with self.assertRaises(AccessError):
            self.store.partner_id.with_user(self.investor).read(["name"])
        with self.assertRaises(AccessError):
            self.investor.partner_id.with_user(self.investor).write({"name": "X"})
        with self.assertRaises(AccessError):
            Partners.create({"name": "New contact"})
        # own preferences through the standard self-writeable fields
        self.investor.with_user(self.investor).write({"lang": "fr_FR", "tz": "Europe/Paris"})
        self.assertEqual(self.investor.lang, "fr_FR")
        with self.assertRaises(AccessError):
            self.investor.with_user(self.investor).write({"login": "changed"})

    def test_channels_readable_but_none_visible(self):
        general = self.env.ref("mail.channel_all_employees", raise_if_not_found=False)
        Channel = self.env["discuss.channel"].with_user(self.investor)
        self.assertFalse(Channel.search([]))
        if general:
            with self.assertRaises(AccessError):
                general.with_user(self.investor).read(["name"])
        with self.assertRaises(AccessError):
            Channel.create({"name": "investor channel"})

    def test_monitor_and_export(self):
        Monitor = self.Monitor.with_user(self.investor)
        rows = Monitor.search([("company_id", "=", self.company.id)])
        self.assertTrue(rows)
        self.assertTrue(rows.export_data(["product_name", "inventory_value"])["datas"])
        for field in ("stock_value", "accounting_value", "rent_paid", "owner_name",
                      "responsible_name", "stock_id", "product_id"):
            with self.subTest(field=field), self.assertRaises(AccessError):
                rows.export_data([field])
        self.assertTrue(Monitor.get_dashboard_data({})["count"])

    def test_home_screen_and_buttons(self):
        screen = self.env.ref("lartdubati_investor_home.investor_home_screen")
        other = self.env["quick.start.screen"].create({"name": "Staff screen"})
        foreign = self.env["quick.start.screen.action"].create({
            "name": "Foreign", "action_ref_id": "ir.actions.act_window,%d"
            % self.env.ref("base.action_res_users").id})
        Screen = self.env["quick.start.screen"].with_user(self.investor)
        self.assertEqual(Screen.search([]), screen)
        Buttons = self.env["quick.start.screen.action"].with_user(self.investor)
        self.assertEqual(set(Buttons.search([]).ids),
                         {self.env.ref(xmlid).id for xmlid in INVESTOR_BUTTONS})
        self.assertNotIn(other, Screen.search([]))
        with self.assertRaises(AccessError):
            foreign.with_user(self.investor).read(["name"])
        with self.assertRaises(AccessError):
            screen.with_user(self.investor).write({"name": "Changed"})

    def test_menus_monitor_tree_only(self):
        root = self.env.ref("lartdubati_investor_home.menu_stock_monitor_root")
        Menu = self.env["ir.ui.menu"].with_user(self.investor)
        self.assertEqual(Menu.search([]), Menu.search([("id", "child_of", root.id)]))
        menus = Menu.load_menus(False)
        self.assertEqual(menus["root"]["children"], [root.id])
        staff_roots = self.env["ir.ui.menu"].with_user(self.store).load_menus(False)
        self.assertGreater(len(staff_roots["root"]["children"]), 1)


@tagged("post_install", "-at_install")
class TestInvestorGroups(InvestorSecurityCommon):
    """P4-5: an investor account holds no other right."""

    def test_forbidden_groups_refused(self):
        for xmlid in ("stock.group_stock_user", "account.group_account_readonly",
                      "purchase.group_purchase_user", "base.group_system",
                      "base.group_erp_manager", "maintenance.group_equipment_manager",
                      "maintenance_shareholder_equipment.group_equipment_operator"):
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if not group:
                continue
            with self.subTest(group=xmlid), self.assertRaises(ValidationError):
                self.investor.groups_id |= group
        with self.assertRaises(ValidationError):
            self.store.groups_id |= self.env.ref(
                "lartdubati_investor_home.group_stock_investor")

    def test_implied_groups_and_export_allowed(self):
        internal = self.env.ref("base.group_user")
        self.assertIn(self.env.ref("base.group_no_one"), internal.trans_implied_ids)
        self.investor.groups_id |= internal.trans_implied_ids \
            | self.env.ref("base.group_allow_export")
        self.investor.flush_recordset()

    def test_home_action_set(self):
        home = self.env.ref("lartdubati_investor_home.action_investor_home")
        self.assertEqual(self.investor.action_id.id, home.id)
        self.assertEqual(self.investor.quick_start_screen_id,
                         self.env.ref("lartdubati_investor_home.investor_home_screen"))
        old = self.env.ref("web_quick_start_screen.start_screen_action")
        self.investor.action_id = old.id
        self.investor._set_investor_home()
        self.assertEqual(self.investor.action_id.id, home.id)
        self.assertNotEqual(self.store.action_id.id, home.id)

    def test_warning_without_profile(self):
        self.assertFalse(self.investor.investor_without_profile)
        self.investor.stock_access_id = False
        self.investor.invalidate_recordset(["investor_without_profile"])
        self.assertTrue(self.investor.investor_without_profile)
        self.assertFalse(self.store.investor_without_profile)


@tagged("post_install", "-at_install")
class TestInvestorActions(InvestorSecurityCommon, HttpCase):
    """P4-2d through the real HTTP routes: loadable actions, server actions, home
    buttons, JSON-RPC and URLs."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.investor.password = cls.investor.login
        cls.store.password = cls.store.login
        Server = cls.env["ir.actions.server"]
        cls.server_internal = Server.create({
            "name": "Granted to internal users (test)", "state": "code",
            "model_id": cls.env.ref("base.model_res_partner").id, "code": "action = False",
            "groups_id": [Command.set(cls.env.ref("base.group_user").ids)]})
        cls.server_users = Server.create({
            "name": "No group, on users (test)", "state": "code",
            "model_id": cls.env.ref("base.model_res_users").id, "code": "action = False"})
        cls.staff_action = cls.env.ref("stock.action_picking_tree_all")
        cls.path_action = cls.env["ir.actions.actions"].search([("path", "!=", False)], limit=1)

    def _load(self, action_id):
        return self.make_jsonrpc_request("/web/action/load", {"action_id": action_id})

    def test_load_only_whitelisted_actions(self):
        self.authenticate(self.investor.login, self.investor.login)
        refused = [self.staff_action.id, "stock.action_picking_tree_all",
                   self.env.ref("base.action_res_users").id, self.server_internal.id,
                   self.env.ref("web_quick_start_screen.start_screen_action").id]
        if self.path_action:
            refused.append(self.path_action.path)
        for action_id in refused:
            with self.subTest(action=action_id), self.assertRaises(JsonRpcException):
                self._load(action_id)
        for xmlid in INVESTOR_ACTIONS:
            action = self.env.ref(xmlid)
            for action_id in (action.id, xmlid):
                with self.subTest(action=action_id):
                    self.assertEqual(self._load(action_id)["id"], action.id)
        crumbs = self.make_jsonrpc_request("/web/action/load_breadcrumbs", {"actions": [
            {"action": self.staff_action.id},
            {"action": "lartdubati_investor_home.action_stock_monitor"}]})
        self.assertIn("error", crumbs[0])
        self.assertNotIn("error", crumbs[1])

    def test_staff_loads_as_before(self):
        self.authenticate(self.store.login, self.store.login)
        self.assertEqual(self._load(self.staff_action.id)["id"], self.staff_action.id)

    def test_server_actions_never_run(self):
        start = self.env.ref("web_quick_start_screen.start_screen_action")
        for action in (self.server_internal, self.server_users, start):
            with self.subTest(action=action.name), self.assertRaises(AccessError):
                action.with_user(self.investor).run()
        self.authenticate(self.investor.login, self.investor.login)
        for action in (self.server_internal, self.server_users, start):
            with self.subTest(action=action.name), self.assertRaises(JsonRpcException):
                self.make_jsonrpc_request("/web/action/run", {"action_id": action.id})
        # framework code running actions in sudo (base automations) is not affected
        self.assertFalse(self.server_users.with_user(self.investor).sudo().run())

    def test_home_buttons_open_only_their_action(self):
        tags = {}
        for xmlid in INVESTOR_BUTTONS:
            button = self.env.ref(xmlid).with_user(self.investor)
            tags[xmlid] = button.run_action()["tag"]
        self.assertEqual(tags["lartdubati_investor_home.investor_button_financial"],
                         "lartdubati_stock_monitor")
        self.assertEqual(tags["lartdubati_investor_home.investor_button_production"],
                         "lartdubati_coming_soon")
        financial = self.env.ref("lartdubati_investor_home.investor_button_financial")
        other_tag = self.env["ir.actions.client"].create({"name": "Other", "tag": "reload"})
        # same type and tag as the dashboard, another record (other context or params):
        # only the exact action check refuses it
        same_tag = self.env.ref("lartdubati_investor_home.action_stock_monitor").copy(
            {"name": "Look-alike", "context": "{'default_x': 1}"})
        for target in ("ir.actions.client,%d" % same_tag.id,"ir.actions.act_window,%d" % self.staff_action.id,
                       "ir.actions.server,%d" % self.server_internal.id,
                       "ir.actions.client,%d" % other_tag.id,
                       "ir.actions.client,%d"
                       % self.env.ref("lartdubati_investor_home.action_coming_soon").id):
            financial.action_ref_id = target
            with self.subTest(target=target), self.assertRaises(AccessError):
                financial.with_user(self.investor).run_action()
        # staff keep the OCA behaviour
        self.assertTrue(financial.with_user(self.store).run_action())

    def test_json_rpc_and_urls(self):
        product = self.env["product.product"].create({"name": "Secret", "image_1920": PNG,
                                                      "standard_price": 42.0})
        attachment = self.env["ir.attachment"].create({
            "name": "secret.txt", "datas": base64.b64encode(b"secret"),
            "res_model": "product.product", "res_id": product.id})
        self.authenticate(self.investor.login, self.investor.login)
        for model, method, args in (("stock.quant", "search_read", [[], ["quantity"]]),
                                    ("product.product", "read", [[product.id],
                                                                 ["standard_price"]]),
                                    (UNNAMED_MODEL, "search_count", [[]]),
                                    ("ir.ui.menu", "search_read", [[], ["name"]])):
            with self.subTest(model=model):
                call = lambda: self.make_jsonrpc_request(  # noqa: E731
                    "/web/dataset/call_kw",
                    {"model": model, "method": method, "args": args, "kwargs": {}})
                if model == "ir.ui.menu":
                    names = {menu["name"] for menu in call()}
                    self.assertNotIn("Inventory", names)
                else:
                    with self.assertRaises(JsonRpcException):
                        call()
        self.assertTrue(self.make_jsonrpc_request("/web/dataset/call_kw", {
            "model": "lartdubati.stock.monitor", "method": "search_count", "args": [[]],
            "kwargs": {}}))
        content = self.url_open(f"/web/content/{attachment.id}")
        self.assertNotEqual(content.content, b"secret")
        image = self.url_open(f"/web/image/product.product/{product.id}/image_128")
        self.assertNotEqual(image.content, base64.b64decode(PNG))

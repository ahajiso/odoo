"""Phase 4: investor accounts read only the stock monitor (docs/phase4/PLAN.md §2, §4).

Every check runs under the real investor account: the ORM with `with_user`, and an HTTP
session for JSON-RPC, actions and URLs.
"""
import base64
import importlib.util
import json
import os
import re
import xmlrpc.client

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, tagged
from odoo.tests.common import JsonRpcException

from odoo.addons.lartdubati_investor_home.models.investor_security import (
    INVESTOR_ACTIONS,
    INVESTOR_BUTTONS,
    INVESTOR_ROUTES,
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
# what a browser sends when the user opens a URL (/json/1 checks them for a session)
BROWSER_HEADERS = {"Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate",
                   "Sec-Fetch-Site": "same-origin", "Sec-Fetch-User": "?1"}
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


@tagged("post_install", "-at_install")
class TestInvestorCalls(InvestorSecurityCommon, HttpCase):
    """P4-2e (audit of dff33cb): public methods, export routes and the external API.
    A public method may work in sudo or SQL without any ORM check: the model and the
    method must both be listed for an investor account."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.investor.password = cls.investor.login
        cls.store.password = cls.store.login
        cls.picking_type = cls.env["stock.picking.type"].search([], limit=1)

    def _call(self, model, method, args, kwargs=None, route="/web/dataset/call_kw"):
        return self.make_jsonrpc_request(route, {
            "model": model, "method": method, "args": args, "kwargs": kwargs or {}})

    def test_public_methods_without_orm_check(self):
        # through the ORM the method works for the investor: it reads the action in sudo
        # and checks nothing (this is what the controller check stops)
        self.assertEqual(self.env["stock.picking.type"].with_user(self.investor)
                         .get_action_picking_tree_ready()["type"], "ir.actions.act_window")
        self.authenticate(self.investor.login, self.investor.login)
        channels = self.env["discuss.channel"].search_count([])
        for model, method, args, kwargs in (
                ("stock.picking.type", "get_action_picking_tree_ready",
                 [self.picking_type.ids], {}),
                ("stock.picking.type", "get_action_picking_tree_ready", [[]], {}),
                # a listed model, an unlisted method working in sudo
                ("discuss.channel", "channel_get", [],
                 {"partners_to": [self.store.partner_id.id]}),
                ("res.users", "name_create", ["Someone"], {}),
                ("res.partner", "message_post", [[self.investor.partner_id.id]],
                 {"body": "x"}),
                ("lartdubati.stock.monitor", "init", [], {}),
                ("ir.actions.actions", "get_bindings", ["res.partner"], {})):
            for route in ("/web/dataset/call_kw", "/web/dataset/call_button"):
                with self.subTest(model=model, method=method, route=route), \
                        self.assertRaises(JsonRpcException):
                    self._call(model, method, args, kwargs, route=route)
        self.assertEqual(self.env["discuss.channel"].search_count([]), channels)
        # what the investor's pages use still works
        self.assertTrue(self._call("lartdubati.stock.monitor", "get_dashboard_data", [{}]))
        financial = self.env.ref("lartdubati_investor_home.investor_button_financial")
        self.assertEqual(self._call("quick.start.screen.action", "run_action",
                                    [financial.ids], route="/web/dataset/call_button")["tag"],
                         "lartdubati_stock_monitor")

    def test_resequence_refused(self):
        buttons = self.env["quick.start.screen.action"].browse(
            [self.env.ref(xmlid).id for xmlid in INVESTOR_BUTTONS])
        before = buttons.mapped("sequence")
        self.authenticate(self.investor.login, self.investor.login)
        with self.assertRaises(JsonRpcException):
            self.make_jsonrpc_request("/web/dataset/resequence", {
                "model": "quick.start.screen.action", "ids": list(reversed(buttons.ids))})
        buttons.invalidate_recordset()
        self.assertEqual(buttons.mapped("sequence"), before)

    def test_export_routes(self):
        self.authenticate(self.investor.login, self.investor.login)
        with self.assertRaises(JsonRpcException):
            self.make_jsonrpc_request("/web/export/get_fields",
                                      {"model": "stock.quant", "domain": []})
        self.assertTrue(self.make_jsonrpc_request(
            "/web/export/get_fields", {"model": "lartdubati.stock.monitor", "domain": [],
                                       "import_compat": False}))
        page = self.url_open("/odoo").text
        token = re.search(r'csrf_token: "(\w+)"', page).group(1)

        def export(model, fields):
            return self.url_open("/web/export/csv", data={"csrf_token": token, "data": json.dumps({
                "model": model, "fields": [{"name": name, "label": name} for name in fields],
                "ids": False, "domain": [], "import_compat": False})})
        refused = export("stock.quant", ["quantity"])
        self.assertNotEqual(refused.status_code, 200)
        allowed = export("lartdubati.stock.monitor", ["product_name"])
        self.assertEqual(allowed.status_code, 200)
        self.assertIn("Screws", allowed.text)

    def test_external_api_refused(self):
        db = self.env.cr.dbname
        for proxy_call in (
                lambda login, uid: self.xmlrpc_object.execute_kw(
                    db, uid, login, "res.currency", "search_count", [[]]),
                lambda login, uid: self.make_jsonrpc_request("/jsonrpc", {
                    "service": "object", "method": "execute_kw",
                    "args": [db, uid, login, "res.currency", "search_count", [[]]]})):
            try:
                proxy_call(self.investor.login, self.investor.id)
            except (xmlrpc.client.Fault, JsonRpcException):
                pass
            else:
                self.fail("external API not refused to the investor")
            self.assertTrue(proxy_call(self.store.login, self.store.id))


@tagged("post_install", "-at_install")
class TestInvestorRoutes(InvestorSecurityCommon, HttpCase):
    """P4-2f (audit of 6063db1): routes resolving models, actions or reports themselves
    (possibly in sudo) are refused by the route whitelist before their controller; staff
    keep the standard behaviour. And the own password change, end to end."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.investor.password = cls.investor.login
        cls.store.password = cls.store.login
        partner = cls.env["res.partner"].create({"name": "Supplier (routes test)"})
        cls.order = cls.env["purchase.order"].create({
            "partner_id": partner.id, "order_line": [Command.create({
                "product_id": cls.drill.id, "product_qty": 1, "price_unit": 10})]})
        cls.picking = cls.env["stock.picking"].create({
            "partner_id": partner.id,
            "picking_type_id": cls.env.ref("stock.picking_type_in").id})
        cls.invoice = cls.env["account.move"].create({
            "move_type": "out_invoice", "partner_id": partner.id,
            "invoice_line_ids": [Command.create({"name": "Secret line", "quantity": 1,
                                                 "price_unit": 10})]})

    def _token(self):
        return re.search(r'csrf_token: "(\w+)"', self.url_open("/odoo").text).group(1)

    def _definitions(self, route, key, models):
        return self.url_open(route, data={"csrf_token": self._token(),
                                          key: json.dumps(models)})

    def test_model_definitions_refused(self):
        models = ["account.move", "res.groups", "maintenance.equipment",
                  "lartdubati.stock.monitor"]
        self.authenticate(self.investor.login, self.investor.login)
        for route, key in (("/web/model/get_definitions", "model_names"),
                           ("/bus/get_model_definitions", "model_names_to_fetch")):
            for model in models:
                with self.subTest(route=route, model=model):
                    response = self._definitions(route, key, [model])
                    self.assertEqual(response.status_code, 403)
                    self.assertNotIn(b'"fields"', response.content)
        self.authenticate("admin", "admin")
        response = self._definitions("/web/model/get_definitions", "model_names",
                                     ["account.move"])
        self.assertEqual(response.status_code, 200)
        self.assertIn("fields", response.json()["account.move"])

    def test_json_routes_refused(self):
        self.env["ir.config_parameter"].sudo().set_param("web.json.enabled", "1")
        picking = self.env.ref("stock.action_picking_tree_all")
        invoices = self.env.ref("account.action_move_out_invoice_type")
        analysis = self.env.ref("lartdubati_investor_home.action_stock_monitor_analysis")
        subpaths = [f"action-{picking.id}", "action-stock.action_picking_tree_all",
                    f"action-{invoices.id}", "action-account.action_move_out_invoice_type",
                    f"action-{analysis.id}"]
        if picking.path:
            subpaths.append(picking.path)
        # /json/1 accepts a session only from a browser navigation (Sec-Fetch headers),
        # or an API key: both are refused by the route whitelist, not by the standard
        # check (no API key can be made by an investor account; one made by an
        # administrator is refused all the same)
        key = self.env["res.users.apikeys"].with_user(self.investor).sudo()._generate(
            None, "routes test", False)
        self.authenticate(self.investor.login, self.investor.login)
        for prefix in ("/json/", "/json/1/"):
            for subpath in subpaths:
                with self.subTest(url=prefix + subpath):
                    response = self.url_open(prefix + subpath, allow_redirects=False,
                                             headers=BROWSER_HEADERS)
                    self.assertEqual(response.status_code, 403)
        self.authenticate(None, None)
        response = self.url_open("/json/1/action-stock.action_picking_tree_all",
                                 headers={"Authorization": f"Bearer {key}"})
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("records", response.text)
        # staff: standard behaviour
        self.authenticate("admin", "admin")
        response = self.url_open("/json/1/action-stock.action_picking_tree_all",
                                 headers=BROWSER_HEADERS)
        self.assertEqual(response.status_code, 200)
        self.assertIn("records", response.json())

    def test_reports_refused(self):
        self.authenticate(self.investor.login, self.investor.login)
        urls = [f"/report/html/stock.report_picking/{self.picking.id}",
                f"/report/pdf/stock.report_deliveryslip/{self.picking.id}",
                f"/report/html/purchase.report_purchaseorder/{self.order.id}",
                f"/report/text/purchase.report_purchasequotation/{self.order.id}",
                f"/report/html/account.report_invoice/{self.invoice.id}",
                f"/report/pdf/account.report_invoice_with_payments/{self.invoice.id}",
                "/stock/pdf/stock.report_picking"]
        for url in urls:
            with self.subTest(url=url):
                response = self.url_open(url)
                self.assertEqual(response.status_code, 403)
                self.assertNotIn(self.picking.name.encode(), response.content)
                self.assertNotIn(self.order.name.encode(), response.content)
                self.assertNotIn(b"Secret line", response.content)
        response = self.url_open("/report/download", data={
            "csrf_token": self._token(),
            "data": json.dumps([f"/report/html/account.report_invoice/{self.invoice.id}",
                                "qweb-html"])})
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(b"Secret line", response.content)
        # staff: standard behaviour (an administrator, an order of their company: the
        # purchase order report needs no barcode renderer)
        admin = self.env.ref("base.user_admin")
        order = self.env["purchase.order"].with_company(admin.company_id).create({
            "partner_id": self.order.partner_id.id, "order_line": [Command.create({
                "name": "Line", "product_id": self.drill.id, "product_qty": 1,
                "price_unit": 10})]})
        self.authenticate("admin", "admin")
        response = self.url_open(f"/report/html/purchase.report_purchaseorder/{order.id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(order.name.encode(), response.content)

    def test_other_authenticated_routes_refused(self):
        """Routes no investor page uses: refused because they are not listed, whatever
        they do (the whitelist, not a list of known risks)."""
        self.authenticate(self.investor.login, self.investor.login)
        for route, params in (("/web/session/account", {}),
                              ("/web/session/modules", {}),
                              ("/web/view/edit_custom", {"custom_id": 1, "arch": "x"}),
                              ("/web/action/run", {"action_id": 1}),
                              ("/mail/inbox/messages", {}),
                              ("/mail/thread/messages", {"thread_model": "res.partner",
                                                          "thread_id": 1})):
            with self.subTest(route=route), self.assertRaises(JsonRpcException):
                self.make_jsonrpc_request(route, params)
        for url in ("/my", "/my/invoices", "/my/purchase", "/web/become",
                    f"/account/download_invoice_documents/{self.invoice.id}/pdf"):
            with self.subTest(url=url):
                self.assertEqual(self.url_open(url, allow_redirects=False).status_code, 403)
        # listed routes: what the investor pages use
        self.assertTrue(self.make_jsonrpc_request("/web/session/get_session_info", {}))
        self.assertIn("/web/dataset/call_kw/<path:path>", INVESTOR_ROUTES)

    def test_staff_routes_unchanged(self):
        self.authenticate(self.store.login, self.store.login)
        self.assertTrue(self.make_jsonrpc_request("/web/session/modules", {}))
        self.assertEqual(self.url_open("/my", allow_redirects=False).status_code, 200)

    def test_own_password_change(self):
        """The standard flow: preferences → wizard → password check → reload, then the
        new password logs in. Another user's wizard stays out of reach."""
        others = self.env["change.password.own"].with_user(self.store).create(
            {"new_password": "store-secret-1", "confirm_password": "store-secret-1"})
        self.authenticate(self.investor.login, self.investor.login)

        def call(model, method, args, kwargs=None, route="/web/dataset/call_kw"):
            return self.make_jsonrpc_request(route, {
                "model": model, "method": method, "args": args, "kwargs": kwargs or {}})
        # preference_change_password asks for the password first (@check_identity)
        check = call("res.users", "preference_change_password", [[self.investor.id]],
                     route="/web/dataset/call_button")
        self.assertEqual(check["res_model"], "res.users.identitycheck")
        call("res.users.identitycheck", "get_views", [], {"views": [[False, "form"]]})
        call("res.users.identitycheck", "web_save",
             [[check["res_id"]], {"password": self.investor.login}], {"specification": {}})
        action = call("res.users.identitycheck", "run_check", [[check["res_id"]]],
                      route="/web/dataset/call_button")
        self.assertEqual(action["res_model"], "change.password.own")
        call("change.password.own", "get_views", [], {"views": [[False, "form"]]})
        new = "investor-new-1"
        wizard = call("change.password.own", "web_save",
                      [[], {"new_password": new, "confirm_password": new}],
                      {"specification": {}})[0]["id"]
        with self.assertRaises(JsonRpcException):
            call("change.password.own", "web_read", [others.ids],
                 {"specification": {"new_password": {}}})
        result = call("change.password.own", "change_password", [[wizard]],
                      route="/web/dataset/call_button")
        self.assertEqual(result["tag"], "reload")
        self.authenticate(self.investor.login, new)
        self.assertEqual(self.make_jsonrpc_request("/web/session/get_session_info", {})["uid"],
                         self.investor.id)


def _pre_migrate():
    path = os.path.join(os.path.dirname(__file__), "..", "migrations", "18.0.3.0.0",
                        "pre-migrate.py")
    spec = importlib.util.spec_from_file_location("p4_pre_migrate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.migrate


@tagged("post_install", "-at_install")
class TestHomeAdoption(InvestorSecurityCommon):
    """P4-0 pre-migration (audit of dff33cb): the old investor screen is found first,
    then its buttons among its own buttons only, by name in any language, sequence and
    current action; another profile's screen is never adopted."""

    def setUp(self):
        super().setUp()
        Data = self.env["ir.model.data"]
        names = ["investor_home_screen", "investor_button_financial",
                 "investor_button_administrative", "investor_button_commerce",
                 "investor_button_production"]
        self.new_records = self.env["quick.start.screen"].browse(
            self.env.ref("lartdubati_investor_home.investor_home_screen").id)
        new_buttons = self.env["quick.start.screen.action"].browse(
            [self.env.ref(f"lartdubati_investor_home.{n}").id for n in names[1:]])
        Data.search([("module", "=", "lartdubati_investor_home"),
                     ("name", "in", names)]).unlink()
        # the module's own records renamed so that only the old ones match
        for lang in ("en_US", "fr_FR", "fa_IR"):  # translations of the module's records
            self.new_records.with_context(lang=lang).write({"name": "Removed for the test"})
            new_buttons.with_context(lang=lang).write({"name": "Removed for the test"})
        Server = self.env["ir.actions.server"]
        self.soon = Server.create({"name": "Investor Home: coming soon", "state": "code",
                                   "model_id": self.env.ref("base.model_res_users").id,
                                   "code": "action = False"})
        monitor = self.env.ref("lartdubati_investor_home.action_server_stock_monitor")
        Button = self.env["quick.start.screen.action"]

        def button(name, sequence, action):
            record = Button.create({"name": name, "sequence": sequence,
                                    "action_ref_id": f"{action._name},{action.id}"})
            return record
        # the old screen as the script left it: Persian in en_US
        self.old_buttons = (button("مالی", 10, monitor) | button("اداری", 20, self.soon)
                            | button("بازرگانی و خدمات", 30, self.soon)
                            | button("تولید", 40, self.soon))
        self.old_screen = self.env["quick.start.screen"].create({
            "name": "خانه سرمایه‌گذار", "action_ids": [Command.set(self.old_buttons.ids)]})
        # another profile's screen with buttons of the same names
        self.other_buttons = button("Production", 40, self.soon) | button("Financial", 10,
                                                                          monitor)
        self.other_screen = self.env["quick.start.screen"].create({
            "name": "Workshop", "action_ids": [Command.set(self.other_buttons.ids)]})
        self.env.flush_all()

    def _bound(self, name):
        return self.env["ir.model.data"].search([
            ("module", "=", "lartdubati_investor_home"), ("name", "=", name)]).res_id

    def test_adopts_only_the_investor_screen_and_its_buttons(self):
        _pre_migrate()(self.env.cr, "18.0.2.0.0")
        self.assertEqual(self._bound("investor_home_screen"), self.old_screen.id)
        for name, button in zip(("financial", "administrative", "commerce", "production"),
                                self.old_buttons):
            self.assertEqual(self._bound(f"investor_button_{name}"), button.id)
        bound = {self._bound(f"investor_button_{n}") for n in
                 ("financial", "administrative", "commerce", "production")}
        self.assertFalse(bound & set(self.other_buttons.ids))

    def test_mismatch_stops(self):
        self.old_buttons[0].sequence = 15
        self.env.flush_all()
        with self.assertRaises(RuntimeError):
            _pre_migrate()(self.env.cr, "18.0.2.0.0")

    def test_two_investor_screens_stop(self):
        self.env["quick.start.screen"].create({"name": "Accueil investisseur"})
        self.env.flush_all()
        with self.assertRaises(RuntimeError):
            _pre_migrate()(self.env.cr, "18.0.2.0.0")

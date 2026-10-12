"""ROADMAP section 0, MENU_PLAN.md (revision 2, audit of fa06f62): « Item and Service
Requests » menus. One action; one entry per application, shown according to the access
rights (a menu is visible only when all its parents are); the catalogue managers have
their own application and need neither Inventory nor Purchase rights. The tests set
their language themselves."""
from lxml import etree

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .test_product_catalogue import MODULE, CatalogueCommon


@tagged("post_install", "-at_install")
class TestRequestMenus(CatalogueCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env = cls.env(context=dict(cls.env.context, lang="en_US"))
        Users = env["res.users"].with_context(no_reset_password=True)
        manager_group = env.ref("%s.group_product_catalogue_manager" % MODULE)

        def user(login, groups):
            return Users.create({
                "name": login, "login": login, "email": "%s@example.com" % login,
                "lang": "en_US",
                "company_id": cls.company.id, "company_ids": [Command.set(cls.company.ids)],
                "groups_id": [Command.set([env.ref("base.group_user").id] + [g.id for g in groups])],
            })

        cls.manager_buyer = user("cat_mgr_buyer", [manager_group,
                                                   env.ref("purchase.group_purchase_user")])
        cls.stock_only = user("cat_stock_only", [env.ref("stock.group_stock_user")])
        cls.accountant = user("cat_accountant", [env.ref("account.group_account_invoice")])
        cls.action = env.ref("%s.action_product_creation_request" % MODULE)
        cls.menu_inventory = env.ref("%s.menu_product_creation_request" % MODULE)
        cls.menu_purchase = env.ref("%s.menu_product_creation_request_purchase" % MODULE)
        cls.menu_catalogue = env.ref("%s.menu_product_catalogue_requests" % MODULE)
        cls.menu_corrections = env.ref("%s.menu_product_structural_correction" % MODULE)
        cls.catalogue_root = env.ref("%s.menu_product_catalogue_root" % MODULE)
        # the manager alone (CatalogueCommon): internal user + Product Catalogue Manager,
        # no Inventory nor Purchase right
        assert not cls.manager2.has_group("stock.group_stock_user")
        assert not cls.manager2.has_group("purchase.group_purchase_user")

    def _visible(self, user):
        return self.env["ir.ui.menu"].with_user(user)._visible_menu_ids()

    def _request_menus(self, user):
        visible = self._visible(user)
        return self.env["ir.ui.menu"].browse([
            mid for mid in visible
            if self.env["ir.ui.menu"].browse(mid).action == self.action])

    # ------------------------------------------------------------------ structure

    def test_one_action_three_entries(self):
        for menu, parent in ((self.menu_inventory, "stock.menu_stock_inventory_control"),
                             (self.menu_purchase, "purchase.menu_purchase_products"),
                             (self.menu_catalogue, "%s.menu_product_catalogue_root" % MODULE)):
            self.assertEqual(menu.action, self.action)
            self.assertEqual(menu.parent_id, self.env.ref(parent))
        self.assertFalse(self.action.domain)
        self.assertEqual(self.menu_corrections.parent_id, self.catalogue_root)
        self.assertEqual(self.menu_inventory.groups_id,
                         self.env.ref("%s.group_equipment_operator" % MODULE)
                         | self.env.ref("stock.group_stock_user"))
        self.assertEqual(self.menu_purchase.groups_id, self.env.ref("purchase.group_purchase_user"))
        manager_group = self.env.ref("%s.group_product_catalogue_manager" % MODULE)
        for menu in (self.catalogue_root, self.menu_catalogue, self.menu_corrections):
            self.assertEqual(menu.groups_id, manager_group)

    def test_names_three_languages(self):
        expected = {"en_US": "Item and Service Requests",
                    "fr_FR": "Demandes d'articles et services",
                    "fa_IR": "درخواست‌های کالا و خدمات"}
        for lang, name in expected.items():
            self.env["res.lang"]._activate_lang(lang)
            self.assertEqual(self.action.with_context(lang=lang).name, name, lang)
            for menu in (self.menu_inventory, self.menu_purchase, self.menu_catalogue):
                self.assertEqual(menu.with_context(lang=lang).name, name, lang)
        # the catalogue managers' application (audit of 561f84d)
        roots = {"en_US": "Product Catalogue", "fr_FR": "Catalogue produits",
                 "fa_IR": "کاتالوگ محصولات"}
        for lang, name in roots.items():
            self.assertEqual(self.catalogue_root.with_context(lang=lang).name, name, lang)
            field = self.env["product.category"].with_context(lang=lang).fields_get(
                ["request_ready"], ["string"])["request_ready"]["string"]
            self.assertNotIn("Product Requests", field, lang)

    # ------------------------------------------------------------------ visibility

    def test_manager_alone_has_his_own_entry_and_can_work(self):
        visible = self._visible(self.manager2)
        for menu in (self.catalogue_root, self.menu_catalogue, self.menu_corrections):
            self.assertIn(menu.id, visible)
        for menu in (self.menu_inventory, self.menu_purchase):
            self.assertNotIn(menu.id, visible)
        # he opens the list and the form as the web client does
        Request = self.env["product.creation.request"].with_user(self.manager2)
        views = Request.get_views([(False, "list"), (False, "form")])["views"]
        request = self._request(default_code="MG-1", barcode=False, supplier_code="MG-1")
        request.action_submit()
        rows = Request.web_search_read([], {"name": {}, "state": {}})["records"]
        self.assertIn(request.id, [row["id"] for row in rows])
        form_fields = {node.get("name") for node in etree.fromstring(views["form"]["arch"]).iter("field")}
        spec = {name: ({"fields": {"display_name": {}}}
                       if Request._fields[name].type in ("many2one", "many2many", "one2many")
                       else {})
                for name in form_fields if name in Request._fields}
        Request.browse(request.id).web_read(spec)
        # and works: approves and executes (he is not the requester)
        request.with_user(self.manager2).action_approve()
        request.with_user(self.manager2).action_execute()
        self.assertEqual(request.state, "done")
        # the structural corrections too
        Correction = self.env["product.structural.correction"].with_user(self.manager2)
        Correction.get_views([(False, "list"), (False, "form")])
        Correction.web_search_read([], {"name": {}})

    def test_requesters_see_their_application_only(self):
        self.assertEqual(self._request_menus(self.buyer), self.menu_purchase)
        self.assertEqual(self._request_menus(self.stock_only), self.menu_inventory)
        # the equipment operator sees exactly the Inventory entry (audit of 561f84d); his
        # group implies Inventory/User, which shows the root of Inventory
        self.assertTrue(self.user_operator.has_group("stock.group_stock_user"))
        self.assertFalse(self.user_operator.has_group("purchase.group_purchase_user"))
        self.assertEqual(self._request_menus(self.user_operator), self.menu_inventory)
        self.assertNotIn(self.catalogue_root.id, self._visible(self.buyer))

    def test_accountant_gets_no_menu(self):
        self.assertFalse(self._request_menus(self.accountant))
        self.assertNotIn(self.catalogue_root.id, self._visible(self.accountant))

    def test_manager_and_buyer_one_entry_per_application(self):
        menus = self._request_menus(self.manager_buyer)
        self.assertEqual(menus, self.menu_purchase | self.menu_catalogue)
        roots = [int(menu.parent_path.split("/")[0]) for menu in menus]
        self.assertEqual(len(roots), len(set(roots)), "two entries in one application")

    # ------------------------------------------------------------------ form and rules

    def test_scope_banner_in_the_form(self):
        for lang, text in (("en_US", "It does not record a contract"),
                           ("fr_FR", "Elle n'enregistre ni contrat"),
                           ("fa_IR", "قرارداد، اشتراک یا صورت‌حساب ثبت نمی‌کند")):
            self.env["res.lang"]._activate_lang(lang)
            arch = self.env["product.creation.request"].with_context(lang=lang).get_views(
                [(False, "form")])["views"]["form"]["arch"]
            banner = etree.fromstring(arch).xpath("//div[@name='request_scope']")
            self.assertTrue(banner, lang)
            self.assertIn(text, " ".join("".join(banner[0].itertext()).split()), lang)

    def test_records_through_the_menus(self):
        """Same action for everyone: the record rules decide what each one sees."""
        mine = self._request(user=self.buyer, default_code="MB-1", barcode=False,
                             supplier_code="MB-1")
        other = self._request(default_code="MB-2", barcode=False, supplier_code="MB-2")
        domain = self.action.domain or []

        def seen(user):
            return {row["id"] for row in self.env["product.creation.request"].with_user(user)
                    .web_search_read(domain, {"name": {}})["records"]}

        self.assertIn(mine.id, seen(self.buyer))
        self.assertNotIn(other.id, seen(self.buyer))
        self.assertTrue({mine.id, other.id} <= seen(self.manager2))
        self.assertTrue({mine.id, other.id} <= seen(self.manager_buyer))

    def test_manager_sees_his_companies_only(self):
        company2 = self.env["res.company"].create({"name": "Other company (test)"})
        foreign = self.env["product.creation.request"].create({
            "family": "service", "product_name": "Foreign service (test)",
            "categ_id": self.categ_service.id, "company_id": company2.id})
        Request = self.env["product.creation.request"].with_user(self.manager2)
        self.assertNotIn(foreign, Request.search([]))
        self.manager2.company_ids = [Command.link(company2.id)]
        self.assertIn(foreign, Request.with_context(
            allowed_company_ids=[self.company.id, company2.id]).search([]))

    def test_requester_still_cannot_approve(self):
        request = self._request(user=self.manager2, default_code="MS-1", barcode=False,
                                supplier_code="MS-1")
        request.with_user(self.manager2).action_submit()
        with self.assertRaisesRegex(UserError, "requester"):
            request.with_user(self.manager2).action_approve()

    def test_direct_creation_message_names_the_paths(self):
        with self.assertRaises(AccessError) as caught:
            self.env["product.template"].with_user(self.buyer).create({"name": "Direct (test)"})
        message = str(caught.exception)
        self.assertIn("According to your access rights", message)
        for path in ("Inventory → Products → Item and Service Requests",
                     "Purchase → Products → Item and Service Requests",
                     "Product Catalogue → Item and Service Requests"):
            self.assertIn(path, message)

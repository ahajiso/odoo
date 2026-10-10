from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.osv import expression
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStockAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.france = cls.env.ref("base.fr")
        cls.germany = cls.env.ref("base.de")
        Warehouse = cls.env["stock.warehouse"]
        Partner = cls.env["res.partner"]
        cls.wh_fr = Warehouse.create({"name": "WH France", "code": "TWFR"})
        cls.wh_other = Warehouse.create({"name": "WH Other", "code": "TWOT"})
        cls.stock_a = cls.wh_fr.lot_stock_id
        cls.stock_b = cls.wh_other.lot_stock_id
        # geography = the stock's own address (phase 3), never the warehouse partner
        currency = cls.env.company.currency_id.id
        cls.stock_a.write({"is_monitor_stock": True, "monitor_currency_id": currency,
                           "address_id": Partner.create({
                               "name": "Site France", "city": "Bougival",
                               "country_id": cls.france.id}).id})
        cls.stock_b.write({"is_monitor_stock": True, "monitor_currency_id": currency,
                           "address_id": Partner.create({
                               "name": "Site Germany", "city": "Berlin",
                               "country_id": cls.germany.id}).id})
        # a real investor: internal user + investor, no Inventory group
        cls.user = cls.env["res.users"].create(
            {
                "name": "Investor",
                "login": "investor_test",
                "groups_id": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("lartdubati_investor_home.group_stock_investor").id,
                        ]
                    )
                ],
            }
        )
        cls.Profile = cls.env["lartdubati.stock.access"]

    def _visible(self, domain):
        """Locations the profile rule lets the user see. Since phase 4 an investor
        account reads no location at all (default deny, test_investor_security): the
        rule is kept for safety and checked through its computed domain."""
        rule = self.env["ir.rule"].with_user(self.user)._compute_domain("stock.location", "read")
        return self.env["stock.location"].search(expression.AND([rule or [], domain]))

    def _visible_stocks(self):
        return self._visible([("id", "in", (self.stock_a | self.stock_b).ids)])

    def test_no_profile_sees_nothing(self):
        self.assertFalse(self._visible_stocks())
        supplier = self.env.ref("stock.stock_location_suppliers")
        self.assertTrue(self._visible([("id", "=", supplier.id)]))

    def test_investor_reads_no_location(self):
        self.user.stock_access_id = self.Profile.create({"name": "All"})
        with self.assertRaises(AccessError):
            self.env["stock.location"].with_user(self.user).search([])

    def test_empty_profile_no_restriction(self):
        self.user.stock_access_id = self.Profile.create({"name": "All"})
        self.assertEqual(self._visible_stocks(), self.stock_a | self.stock_b)

    def test_restrictions(self):
        profile = self.Profile.create(
            {"name": "France", "country_ids": [Command.set(self.france.ids)]}
        )
        self.user.stock_access_id = profile
        self.assertEqual(self._visible_stocks(), self.stock_a)

        profile.write(
            {"country_ids": [Command.clear()], "location_ids": [Command.set(self.stock_b.ids)]}
        )
        self.assertEqual(self._visible_stocks(), self.stock_b)

    def test_non_member_unrestricted(self):
        self.user.groups_id -= self.env.ref("lartdubati_investor_home.group_stock_investor")
        self.assertEqual(self._visible_stocks(), self.stock_a | self.stock_b)

    def test_sub_location_without_address_follows_its_stock(self):
        shelf = self.env["stock.location"].create(
            {"name": "Shelf", "usage": "internal", "location_id": self.stock_a.id})
        self.user.stock_access_id = self.Profile.create(
            {"name": "France", "country_ids": [Command.set(self.france.ids)]})
        self.assertEqual(self._visible([("id", "=", shelf.id)]), shelf)

    def test_new_address_country_applies_at_once(self):
        self.user.stock_access_id = self.Profile.create(
            {"name": "Germany", "country_ids": [Command.set(self.germany.ids)]})
        self.assertEqual(self._visible_stocks(), self.stock_b)
        self.stock_a.address_id.country_id = self.germany
        self.assertEqual(self._visible_stocks(), self.stock_a | self.stock_b)

    def test_monitor_domain(self):
        Profile = self.Profile
        self.assertEqual(Profile.browse()._monitor_domain(), [(0, "=", 1)])
        self.assertEqual(Profile.create({"name": "All"})._monitor_domain(), [(1, "=", 1)])
        profile = Profile.create(
            {
                "name": "Rented assets in France",
                "country_ids": [Command.set(self.france.ids)],
                "ownership_type_ids": [
                    Command.set(self.env.ref("lartdubati_investor_home.ownership_rented").ids)
                ],
                "family_ids": [
                    Command.set(self.env.ref("lartdubati_investor_home.family_asset").ids)
                ],
            }
        )
        domain = profile._monitor_domain()
        self.assertIn(("family", "in", ["asset"]), domain)
        self.assertIn(("ownership_status", "in", ["rented"]), domain)
        self.assertIn(("country_id", "in", self.france.ids), domain)


@tagged("post_install", "-at_install")
class TestInvestorMoveLines(TransactionCase):
    """Standard stock gives every internal user read, write, create and delete on all
    move lines (access_stock_move_line_all): an investor without Inventory rights gets
    none of them (audit of 888d229). Since phase 4 the default deny refuses the model
    first and an investor account cannot hold Inventory rights at all."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stock = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.env.company.id)], limit=1).lot_stock_id
        cls.supplier = cls.env.ref("stock.stock_location_suppliers")
        cls.product = cls.env["product.product"].create(
            {"name": "Cement bag (test)", "type": "consu", "is_storable": True})
        cls.move = cls.env["stock.move"].create({
            "name": "Receipt (test)", "product_id": cls.product.id, "product_uom_qty": 10.0,
            "product_uom": cls.product.uom_id.id, "location_id": cls.supplier.id,
            "location_dest_id": cls.stock.id, "company_id": cls.env.company.id})
        cls.move._action_confirm()
        cls.line = cls.env["stock.move.line"].create(cls._values(cls))

        def user(login, *groups):
            return cls.env["res.users"].with_context(no_reset_password=True).create({
                "name": login, "login": login,
                "groups_id": [Command.set([cls.env.ref(g).id for g in ("base.group_user",) + groups])],
            })
        cls.investor = user("inv_no_stock", "lartdubati_investor_home.group_stock_investor")
        cls.stock_user = user("plain_stock_user", "stock.group_stock_user")
        # a profile without restriction: only the move line rule is under test here
        everything = cls.env["lartdubati.stock.access"].create({"name": "All (test)"})
        cls.investor.stock_access_id = everything

    def _values(self):
        return {"product_id": self.product.id, "location_id": self.supplier.id,
                "location_dest_id": self.stock.id, "quantity": 1.0,
                "product_uom_id": self.product.uom_id.id, "company_id": self.env.company.id,
                "move_id": self.move.id}

    def test_investor_without_inventory_has_no_access(self):
        MoveLine = self.env["stock.move.line"].with_user(self.investor)
        for call in (lambda: MoveLine.search([("id", "=", self.line.id)]),
                     lambda: self.line.with_user(self.investor).read(["quantity"]),
                     lambda: MoveLine.create(dict(self._values(), move_id=False)),
                     lambda: MoveLine.create(self._values()),
                     lambda: self.line.with_user(self.investor).write({"quantity": 2.0}),
                     lambda: self.line.with_user(self.investor).unlink()):
            with self.assertRaises(AccessError):
                call()
        self.assertTrue(self.line.exists())
        self.assertEqual(self.line.quantity, 1.0)
        # the move-line rule of 2f stays behind the default deny
        self.assertEqual(self.env["ir.rule"].with_user(self.investor)._compute_domain(
            "stock.move.line", "read"), [(0, "=", 1)])

    def test_investor_with_inventory_refused(self):
        with self.assertRaises(ValidationError):
            self.investor.groups_id |= self.env.ref("stock.group_stock_user")

    def test_ordinary_inventory_user_unchanged(self):
        MoveLine = self.env["stock.move.line"].with_user(self.stock_user)
        self.assertEqual(MoveLine.search([("id", "=", self.line.id)]), self.line)
        line = MoveLine.create(self._values())
        line.write({"quantity": 3.0})
        self.assertEqual(line.quantity, 3.0)
        line.unlink()
        self.assertFalse(line.exists())

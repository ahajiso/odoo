from contextlib import contextmanager

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStockAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.france = cls.env.ref("base.fr")
        Warehouse = cls.env["stock.warehouse"]
        # The stock address is the warehouse address (standard).
        cls.wh_fr = Warehouse.create(
            {
                "name": "WH France",
                "code": "TWFR",
                "partner_id": cls.env["res.partner"]
                .create({"name": "Site France", "country_id": cls.france.id})
                .id,
            }
        )
        cls.wh_other = Warehouse.create(
            {
                "name": "WH Other",
                "code": "TWOT",
                "partner_id": cls.env["res.partner"].create({"name": "Site Other"}).id,
            }
        )
        cls.stock_a = cls.wh_fr.lot_stock_id
        cls.stock_b = cls.wh_other.lot_stock_id
        cls.user = cls.env["res.users"].create(
            {
                "name": "Investor",
                "login": "investor_test",
                "groups_id": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("stock.group_stock_user").id,
                            cls.env.ref("lartdubati_investor_home.group_stock_investor").id,
                        ]
                    )
                ],
            }
        )
        cls.Profile = cls.env["lartdubati.stock.access"]

    def _visible_stocks(self):
        return self.env["stock.location"].with_user(self.user).search(
            [("id", "in", (self.stock_a | self.stock_b).ids)]
        )

    def test_no_profile_sees_nothing(self):
        self.assertFalse(self._visible_stocks())
        supplier = self.env.ref("stock.stock_location_suppliers")
        self.assertTrue(
            self.env["stock.location"].with_user(self.user).search([("id", "=", supplier.id)])
        )

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
        self.assertIn(("x_family", "in", ["asset"]), domain)
        self.assertIn(("x_ownership", "in", ["rented"]), domain)
        self.assertIn(("x_country_id", "in", self.france.ids), domain)


@tagged("post_install", "-at_install")
class TestInvestorMoveLines(TransactionCase):
    """Standard stock gives every internal user read, write, create and delete on all
    move lines (access_stock_move_line_all): an investor without Inventory rights gets
    none of them (audit of 888d229)."""

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
        cls.investor_stock = user("inv_stock", "lartdubati_investor_home.group_stock_investor",
                                  "stock.group_stock_user")
        cls.stock_user = user("plain_stock_user", "stock.group_stock_user")
        # a profile without restriction: only the move line rule is under test here
        everything = cls.env["lartdubati.stock.access"].create({"name": "All (test)"})
        (cls.investor | cls.investor_stock).stock_access_id = everything

    @contextmanager
    def _denied_by_move_line_rule(self, *operations):
        """AccessError raised by a record rule of stock.move.line for one of
        `operations` (the message is generic for users without debug rights: the log
        names the operation and the model)."""
        with self.assertLogs("odoo.addons.base.models.ir_rule", "INFO") as logs, \
                self.assertRaises(AccessError):
            yield
        self.assertTrue(any("operation: %s on" % operation in line
                            and "model: stock.move.line" in line
                            for line in logs.output for operation in operations),
                        logs.output)

    def _values(self):
        return {"product_id": self.product.id, "location_id": self.supplier.id,
                "location_dest_id": self.stock.id, "quantity": 1.0,
                "product_uom_id": self.product.uom_id.id, "company_id": self.env.company.id,
                "move_id": self.move.id}

    def test_investor_without_inventory_has_no_access(self):
        MoveLine = self.env["stock.move.line"].with_user(self.investor)
        self.assertFalse(MoveLine.search([("id", "=", self.line.id)]))
        with self.assertRaises(AccessError):
            self.line.with_user(self.investor).read(["quantity"])
        # a line without a move: standard stock alone would allow it; refused by the rule
        # the new line is read back during its creation: the same rule refuses it
        with self._denied_by_move_line_rule("create", "read"):
            MoveLine.create(dict(self._values(), move_id=False))
        with self.assertRaises(AccessError):
            MoveLine.create(self._values())
        # the line is invisible to them: write and unlink stop at its read check or at
        # their own, both from the same rule (the only one refusing on move lines here)
        with self._denied_by_move_line_rule("write", "read"):
            self.line.with_user(self.investor).write({"quantity": 2.0})
        with self._denied_by_move_line_rule("unlink", "read"):
            self.line.with_user(self.investor).unlink()
        self.assertTrue(self.line.exists())
        self.assertEqual(self.line.quantity, 1.0)

    def test_investor_with_inventory_keeps_standard_rights(self):
        line = self.env["stock.move.line"].with_user(self.investor_stock).create(self._values())
        line.write({"quantity": 2.0})
        self.assertEqual(self.env["stock.move.line"].with_user(self.investor_stock).search(
            [("id", "in", (line | self.line).ids)]), line | self.line)
        line.unlink()

    def test_ordinary_inventory_user_unchanged(self):
        MoveLine = self.env["stock.move.line"].with_user(self.stock_user)
        self.assertEqual(MoveLine.search([("id", "=", self.line.id)]), self.line)
        line = MoveLine.create(self._values())
        line.write({"quantity": 3.0})
        self.assertEqual(line.quantity, 3.0)
        line.unlink()
        self.assertFalse(line.exists())

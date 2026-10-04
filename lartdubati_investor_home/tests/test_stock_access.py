from odoo import Command
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

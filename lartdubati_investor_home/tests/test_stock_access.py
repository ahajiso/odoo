from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStockAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.france = cls.env.ref("base.fr")
        cls.stock_a = cls.env["stock.location"].create(
            {"name": "Stock A", "usage": "internal", "country_id": cls.france.id}
        )
        cls.stock_b = cls.env["stock.location"].create(
            {"name": "Stock B", "usage": "internal"}
        )
        Equipment = cls.env["maintenance.equipment"]
        cls.eq_a = Equipment.create({"name": "Eq A", "current_location_id": cls.stock_a.id})
        cls.eq_b = Equipment.create(
            {
                "name": "Eq B",
                "current_location_id": cls.stock_b.id,
                "acquisition_mode": "rental",
                "owner_type": "third_party",
            }
        )
        # Maintenance managers see every equipment through a group rule:
        # the global investor rule must still restrict them.
        cls.user = cls.env["res.users"].create(
            {
                "name": "Investor",
                "login": "investor_test",
                "groups_id": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("stock.group_stock_user").id,
                            cls.env.ref("maintenance.group_equipment_manager").id,
                            cls.env.ref("lartdubati_investor_home.group_stock_investor").id,
                        ]
                    )
                ],
            }
        )
        cls.Profile = cls.env["lartdubati.stock.access"]

    def _visible_equipment(self):
        return self.env["maintenance.equipment"].with_user(self.user).search(
            [("id", "in", (self.eq_a | self.eq_b).ids)]
        )

    def _visible_stocks(self):
        return self.env["stock.location"].with_user(self.user).search(
            [("id", "in", (self.stock_a | self.stock_b).ids)]
        )

    def test_no_profile_sees_nothing(self):
        self.assertFalse(self._visible_equipment())
        self.assertFalse(self._visible_stocks())
        supplier = self.env.ref("stock.stock_location_suppliers")
        self.assertTrue(
            self.env["stock.location"].with_user(self.user).search([("id", "=", supplier.id)])
        )

    def test_empty_profile_no_restriction(self):
        self.user.stock_access_id = self.Profile.create({"name": "All"})
        self.assertEqual(self._visible_equipment(), self.eq_a | self.eq_b)

    def test_restrictions(self):
        profile = self.Profile.create({"name": "France", "country_ids": [Command.set(self.france.ids)]})
        self.user.stock_access_id = profile
        self.assertEqual(self._visible_equipment(), self.eq_a)
        self.assertEqual(self._visible_stocks(), self.stock_a)

        profile.write(
            {
                "country_ids": [Command.clear()],
                "ownership_type_ids": [
                    Command.set(self.env.ref("lartdubati_investor_home.ownership_rented").ids)
                ],
            }
        )
        self.assertEqual(self._visible_equipment(), self.eq_b)

        profile.family_ids = self.env.ref("lartdubati_investor_home.family_consumable")
        self.assertFalse(self._visible_equipment())

    def test_non_member_unrestricted(self):
        self.user.groups_id -= self.env.ref("lartdubati_investor_home.group_stock_investor")
        self.assertEqual(self._visible_equipment(), self.eq_a | self.eq_b)

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestOwnership(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stock = cls.env["stock.location"].create(
            {"name": "Test Stock", "usage": "internal"}
        )
        cls.lent_out_stock = cls.env["stock.location"].create(
            {"name": "Test Lent Out", "usage": "internal", "place_type": "lent_out"}
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Test Consumable", "type": "consu", "is_storable": True}
        )
        cls.third_party = cls.env["res.partner"].create({"name": "Third Party"})

    def test_equipment_mapping(self):
        Equipment = self.env["maintenance.equipment"]
        cases = [
            ("purchase", "company", "owned"),
            ("purchase", "shareholder", "borrowed"),
            ("purchase", "third_party", "borrowed"),
            ("rental", "third_party", "rented"),
            ("borrowed", "shareholder", "borrowed"),
            ("loaned_out", "company", "lent_out"),
        ]
        for mode, owner_type, expected in cases:
            equipment = Equipment.create(
                {"name": "Eq", "acquisition_mode": mode, "owner_type": owner_type}
            )
            self.assertEqual(equipment.ownership, expected, f"{mode}/{owner_type}")

    def _quant(self, location, owner=False):
        Quant = self.env["stock.quant"]
        Quant._update_available_quantity(self.product, location, 5, owner_id=owner)
        return Quant.search(
            [
                ("product_id", "=", self.product.id),
                ("location_id", "=", location.id),
                ("owner_id", "=", owner and owner.id),
            ]
        )

    def test_quant_ownership(self):
        owned = self._quant(self.stock)
        third = self._quant(self.stock, self.third_party)
        lent = self._quant(self.lent_out_stock)
        self.assertEqual(owned.ownership, "owned")
        self.assertEqual(third.ownership, "borrowed")
        self.assertEqual(lent.ownership, "lent_out")

        self.env["lartdubati.stock.rental"].create(
            {"owner_id": self.third_party.id, "product_id": self.product.id, "rent_amount": 10}
        )
        third.invalidate_recordset(["ownership"])
        self.assertEqual(third.ownership, "rented")

        Quant = self.env["stock.quant"]
        domain = [("product_id", "=", self.product.id)]
        self.assertEqual(Quant.search(domain + [("ownership", "=", "rented")]), third)
        self.assertEqual(Quant.search(domain + [("ownership", "=", "owned")]), owned)
        self.assertEqual(
            Quant.search(domain + [("ownership", "not in", ["owned", "rented"])]), lent
        )

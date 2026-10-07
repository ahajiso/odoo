from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestEquipmentStock(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stock = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.env.company.id)], limit=1
        ).lot_stock_id

    def test_stock_required(self):
        Equipment = self.env["maintenance.equipment"]
        with self.assertRaises(ValidationError):
            Equipment.create({"name": "No stock"})
        with self.assertRaises(ValidationError):
            Equipment.create(
                {
                    "name": "Supplier location",
                    "current_location_id": self.env.ref("stock.stock_location_suppliers").id,
                }
            )
        equipment = Equipment.create({"name": "In stock", "current_location_id": self.stock.id})
        with self.assertRaises(ValidationError):
            equipment.current_location_id = False
        # Archived equipment no longer needs a stock.
        equipment.write({"active": False, "current_location_id": False})

    def test_equipment_from_vendor_bill(self):
        product = self.env["product.product"].create(
            {"name": "Test drill", "maintenance_ok": True, "type": "consu"}
        )
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.env["res.partner"].create({"name": "Vendor"}).id,
                "invoice_date": "2026-10-01",
                "invoice_line_ids": [
                    (0, 0, {"product_id": product.id, "quantity": 2, "price_unit": 500, "tax_ids": [(5,)]})
                ],
            }
        )
        bill.action_post()
        equipment = bill.invoice_line_ids.equipment_ids
        self.assertEqual(len(equipment), 2)
        self.assertEqual(equipment.current_location_id, self.stock)
        self.assertEqual(equipment.mapped("cost"), [500.0, 500.0])

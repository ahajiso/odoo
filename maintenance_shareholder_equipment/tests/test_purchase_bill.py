from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .common import EquipmentCommon


@tagged("post_install", "-at_install")
class TestPurchaseBill(EquipmentCommon):
    """Receipt and bill in either order, partial flows, one equipment per unit, both
    relations of maintenance_account consistent, one asset per unit."""

    def test_receipt_then_bill(self):
        po = self._order(self.drill, 3)
        received = self._receive(po, ["SN1", "SN2", "SN3"])
        bill = self._bill(po)
        self.assertEqual(len(bill.invoice_line_ids), 3, "split in units by asset_product_item")
        self.assertTrue(all(bill.invoice_line_ids.mapped("purchase_line_id")),
                        "split lines keep the order line")
        self.assertEqual(po.order_line.qty_invoiced, 3)
        self.assertEqual(self._equipment_of(bill), received, "no duplicate")
        self.assertLinksConsistent(bill)
        assets = bill.invoice_line_ids.asset_id
        self.assertEqual(len(assets), 3)
        self.assertEqual(received.asset_id, assets, "asset filled after posting")
        for equipment in received:
            self.assertEqual(equipment.asset_id, equipment.move_line_id.asset_id)

    def test_bill_then_receipt_creates_drafts(self):
        po = self._order(self.drill, 2)
        bill = self._bill(po)
        drafts = self._equipment_of(bill)
        self.assertEqual(len(drafts), 2)
        self.assertEqual(set(drafts.mapped("integration_state")), {"draft"})
        self.assertFalse(drafts.stock_lot_id)
        self.assertLinksConsistent(bill)

    def test_partial_receipt_full_bill(self):
        po = self._order(self.drill, 3)
        received = self._receive(po, ["P1"])
        bill = self._bill(po)
        equipment = self._equipment_of(bill)
        self.assertEqual(len(equipment), 3)
        self.assertIn(received, equipment)
        self.assertEqual(len(equipment.filtered(lambda e: not e.stock_lot_id)), 2)
        self.assertLinksConsistent(bill)

    def test_two_bills_for_one_order_line(self):
        po = self._order(self.small_tool, 3)
        first = self._bill(po, qty=2)
        second = self._bill(po, qty=1)
        self.assertEqual(len(self._equipment_of(first)), 2)
        self.assertEqual(len(self._equipment_of(second)), 1)
        self.assertFalse(self._equipment_of(first) & self._equipment_of(second))
        self.assertLinksConsistent(first)
        self.assertLinksConsistent(second)

    def test_received_equipment_shared_by_two_bills(self):
        po = self._order(self.drill, 3)
        received = self._receive(po, ["A1", "A2", "A3"])
        first = self._bill(po, post=False)
        # Keep 2 of the 3 unit lines on the first bill.
        first.invoice_line_ids[-1].unlink()
        first.action_post()
        second = self._bill(po)
        self.assertEqual(self._equipment_of(first) | self._equipment_of(second), received)
        self.assertFalse(self._equipment_of(first) & self._equipment_of(second))

    def test_reset_to_draft_and_lower_quantity_releases_excess(self):
        po = self._order(self.small_tool, 3)
        bill = self._bill(po)
        self.assertEqual(len(self._equipment_of(bill)), 3)
        bill.button_draft()
        bill.invoice_line_ids[:1].quantity = 2
        bill.action_post()
        self.assertEqual(len(self._equipment_of(bill)), 2)
        self.assertLinksConsistent(bill)
        released = self.env["maintenance.equipment"].with_context(active_test=False).search(
            [("product_id", "=", self.small_tool.id), ("active", "=", False)]
        )
        self.assertEqual(len(released), 1)

    def test_cancel_releases_links(self):
        po = self._order(self.drill, 1)
        received = self._receive(po, ["C1"])
        bill = self._bill(po)
        self.assertEqual(self._equipment_of(bill), received)
        bill.button_draft()
        bill.button_cancel()
        self.assertFalse(received.move_line_id)
        self.assertTrue(received.active)
        rebill = self._bill(po)
        self.assertEqual(self._equipment_of(rebill), received, "free again after cancel")

    def test_direct_api_writes_cannot_break_links(self):
        """As an ordinary accounting user (tests otherwise run as superuser)."""
        accountant = self.env["res.users"].create({
            "name": "Accountant", "login": "ladb_accountant", "email": "acc@example.com",
            "company_id": self.company.id, "company_ids": [(6, 0, self.company.ids)],
            "groups_id": [(6, 0, [self.env.ref("account.group_account_manager").id,
                                  self.env.ref("maintenance.group_equipment_manager").id])],
        })
        po = self._order(self.small_tool, 2)
        bill = self._bill(po)
        other_po = self._order(self.small_tool, 1)
        other_bill = self._bill(other_po)
        line = bill.invoice_line_ids[:1].with_user(accountant)
        equipment = line.equipment_ids
        other_line = other_bill.invoice_line_ids[:1].with_user(accountant)
        # Add an equipment of another line to a line.
        with self.assertRaises(ValidationError):
            other_line.write({"equipment_ids": [(4, equipment[0].id)]})
        # Remove one side only.
        with self.assertRaises(AccessError):
            line.write({"equipment_ids": [(3, equipment[0].id)]})
        # Point an equipment to a line while another line lists it.
        with self.assertRaises(ValidationError):
            equipment[0].write({"move_line_id": other_line.id})
        self.assertLinksConsistent(bill)

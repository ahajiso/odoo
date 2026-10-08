from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import EquipmentCommon


@tagged("post_install", "-at_install")
class TestSupplierRefund(EquipmentCommon):
    """Refunds on fixed-asset bills: characterisation first (setting on), then the test
    choice C8 (setting off, the default)."""

    def _direct_bill(self, product, qty, account):
        bill = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": self.vendor.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [Command.create({
                "product_id": product.id, "quantity": qty, "price_unit": 1000.0,
                "account_id": account.id, "tax_ids": [Command.clear()],
            })],
        })
        bill.action_post()
        return bill

    def _reverse(self, bill):
        wizard = self.env["account.move.reversal"].with_context(
            active_model="account.move", active_ids=bill.ids
        ).create({"journal_id": bill.journal_id.id, "date": fields.Date.today()})
        return self.env["account.move"].browse(wizard.refund_moves()["res_id"])

    def _assets(self):
        return self.env["account.asset"].search([("company_id", "=", self.company.id)])

    def test_characterise_reversal_and_manual_refund(self):
        """Measured behaviour with refunds allowed (docs/phase1/CHARACTERISATION.md)."""
        self.company.allow_asset_supplier_refund = True
        bill = self._direct_bill(self.drill, 2, self.acc_asset)
        originals = self._assets()
        equipment = self._equipment_of(bill)
        self.assertEqual(len(originals), 2)
        self.assertEqual(len(equipment), 2)
        self.assertEqual(equipment.asset_id, originals)

        refund = self._reverse(bill)
        self.assertFalse(refund.invoice_line_ids.equipment_ids, "copy=False on equipment_ids")
        refund.action_post()
        after = self._assets()
        new = after - originals
        self.assertEqual(len(new), 2)
        self.assertEqual(sorted(new.mapped("purchase_value")), [-1000.0, -1000.0])
        self.assertTrue(originals.exists(), "the original assets stay")
        self.assertEqual(equipment.asset_id, originals)
        self.assertFalse(refund.invoice_line_ids.equipment_ids, "no equipment from a refund")
        self.assertLinksConsistent(bill)

        manual = self.env["account.move"].create({
            "move_type": "in_refund", "partner_id": self.vendor.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [Command.create({
                "name": "Manual refund", "quantity": 1, "price_unit": 300.0,
                "account_id": self.acc_asset.id, "tax_ids": [Command.clear()],
            })],
        })
        manual.action_post()
        self.assertEqual((self._assets() - after).purchase_value, -300.0)

    def test_refund_on_asset_account_refused_by_default(self):
        bill = self._direct_bill(self.drill, 1, self.acc_asset)
        refund = self._reverse(bill)
        with self.assertRaises(UserError):
            refund.action_post()

    def test_refund_of_equipment_product_leaves_no_equipment(self):
        """maintenance_account creates equipment for refund lines (in_refund is a purchase
        document); our module removes them in the same transaction."""
        before = self.env["maintenance.equipment"].with_context(active_test=False).search_count([])
        refund = self.env["account.move"].create({
            "move_type": "in_refund", "partner_id": self.vendor.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [Command.create({
                "product_id": self.small_tool.id, "quantity": 2, "price_unit": 50.0,
                "account_id": self.acc_expense.id, "tax_ids": [Command.clear()],
            })],
        })
        refund.action_post()
        self.assertEqual(refund.state, "posted")
        self.assertFalse(refund.invoice_line_ids.equipment_ids)
        self.assertEqual(
            self.env["maintenance.equipment"].with_context(active_test=False).search_count([]), before
        )

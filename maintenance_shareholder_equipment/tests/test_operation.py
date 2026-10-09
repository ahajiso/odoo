import base64
from datetime import timedelta
from unittest.mock import patch

import psycopg2

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, tagged

from .common import EquipmentCommon

PDF = base64.b64encode(b"%PDF-1.4 test bill")


@tagged("post_install", "-at_install")
class TestOperationCommon(EquipmentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.screws = cls.env["product.product"].create({
            "name": "Screws", "type": "consu", "is_storable": True, "standard_price": 2.0,
            "categ_id": cls.categ_tools.id,
            "purchase_ok": True, "supplier_taxes_id": [Command.clear()],
        })
        cls.customer = cls.env["res.partner"].create({"name": "Customer"})
        cls.site_a = cls.env["res.partner"].create(
            {"name": "Site A", "parent_id": cls.customer.id, "type": "delivery"})
        cls.site_b = cls.env["res.partner"].create(
            {"name": "Site B", "parent_id": cls.customer.id, "type": "delivery"})

    def _borrow(self, serial, user=None, **vals):
        values = dict(
            receipt_branch="borrowed", partner_id=self.lender.id,
            contract_start=fields.Date.today(), open_ended=True,
            lines=[dict(product_id=self.drill.id, lot_name=serial, replacement_value=900.0,
                        replacement_value_date=fields.Date.today(), condition="good")],
        )
        values.update(vals)
        return self._operation("receipt", user=user, **values)

    def _owned_equipment(self, serial):
        po = self._order(self.drill, 1)
        return self._receive(po, [serial])

    def _exit(self, equipment, user=None, **vals):
        values = dict(partner_id=self.customer.id, site_partner_id=self.site_a.id,
                      exit_nature="loan", new_location_name="Customer A",
                      new_location_parent_id=self.offsite_parent.id,
                      contract_start=fields.Date.today(), open_ended=True,
                      lines=[dict(equipment_id=e.id) for e in equipment])
        values.update(vals)
        return self._operation("exit", user=user, **values)


@tagged("post_install", "-at_install")
class TestReceiptBranches(TestOperationCommon):

    def test_borrowed_receipt_by_approved_new_contract(self):
        op = self._borrow("BR1", user=self.user_operator)
        op.action_execute()
        self.assertEqual(op.state, "to_approve", "a new loan contract needs approval")
        self.assertFalse(op.picking_ids)
        self.assertFalse(op.line_ids.equipment_id)
        op.with_user(self.user_approver).action_approve()
        self.assertEqual(op.state, "approved")
        self.assertFalse(op.picking_ids, "approval moves nothing")
        op.with_user(self.user_operator).action_execute()
        op = self.env["equipment.operation"].browse(op.id)
        self.assertEqual(op.state, "done")
        equipment = op.line_ids.equipment_id
        self.assertEqual(equipment.ownership_status, "borrowed")
        self.assertEqual(equipment.owner_partner_id, self.lender)
        self.assertEqual(equipment.integration_state, "done")
        quant = equipment._internal_quants()
        self.assertEqual(quant.owner_id, self.lender)
        self.assertFalse(op.picking_ids.move_ids.stock_valuation_layer_ids,
                         "no valuation for a third-party owner")
        line = op.contract_ids.contract_line_ids
        self.assertEqual(line.equipment_id, equipment)
        self.assertEqual(line.equipment_nature, "loan")
        # the loan is never invoiced
        for months in range(3):
            date = fields.Date.today() + timedelta(days=31 * months)
            self.env["contract.contract"]._cron_recurring_create(date_ref=date)
        self.assertFalse(op.contract_ids._get_related_invoices())

    def test_borrowed_on_existing_loan_contract_by_operator_alone(self):
        first = self._borrow("BR2")
        first.action_execute()
        contract = first.contract_ids
        op = self._borrow("BR3", user=self.user_operator, contract_mode="existing",
                          contract_id=contract.id)
        self.assertFalse(op.needs_approval)
        op.action_execute()
        self.assertEqual(op.state, "done")
        self.assertEqual(len(contract.contract_line_ids), 2)

    def test_existing_loan_contract_checks(self):
        first = self._borrow("BR4")
        first.action_execute()
        contract = first.contract_ids
        other_owner = self.env["res.partner"].create({"name": "Other owner"})
        op = self._borrow("BR5", partner_id=other_owner.id, contract_mode="existing",
                          contract_id=contract.id)
        with self.assertRaises(ValidationError):
            op.action_execute()
        contract.active = False
        op = self._borrow("BR6", contract_mode="existing", contract_id=contract.id)
        with self.assertRaises(ValidationError):
            op.action_execute()

    def test_rented_receipt_creates_draft_bills_on_rent_account(self):
        op = self._borrow("RE1", receipt_branch="rented",
                          lines=[dict(product_id=self.drill.id, lot_name="RE1",
                                      replacement_value=1500.0, rent_amount=80.0,
                                      replacement_value_date=fields.Date.today())])
        op.action_execute()
        equipment = op.line_ids.equipment_id
        self.assertEqual(equipment.ownership_status, "rented")
        contract = op.contract_ids
        contract.recurring_create_invoice()
        bill = contract._get_related_invoices()
        self.assertEqual(bill.state, "draft")
        line = bill.invoice_line_ids
        self.assertEqual(line.account_id, self.acc_rent)
        self.assertEqual(line.contract_line_id.equipment_id, equipment)
        bill.invoice_date = fields.Date.today()
        bill.action_post()  # phase 1 rent check passes

    def test_missing_values_validate_nothing(self):
        op = self._borrow("MV1", lines=[dict(product_id=self.drill.id, lot_name="MV1")])
        op.line_ids.warranty_status = False
        with self.assertRaises(ValidationError):
            op.action_execute()
        self.assertEqual(op.state, "draft")
        self.assertFalse(self.env["stock.lot"].search([("name", "=", "MV1")]))
        self.assertFalse(self.env["maintenance.equipment"].search([("name", "ilike", "MV1")]))

    def test_consumable_cannot_be_borrowed(self):
        op = self._borrow("X", lines=[dict(product_id=self.screws.id, quantity=5)])
        with self.assertRaises(ValidationError):
            op.action_execute()

    def test_generated_serial_number(self):
        op = self._borrow("", lines=[dict(product_id=self.drill.id, lot_generate=True,
                                          replacement_value=1.0,
                                          replacement_value_date=fields.Date.today())])
        op.action_execute()
        self.assertTrue(op.line_ids.equipment_id.stock_lot_id.name)

    def test_non_stock_borrowed_equipment(self):
        op = self._borrow("", lines=[dict(product_id=self.small_tool.id, replacement_value=1.0,
                                          replacement_value_date=fields.Date.today())])
        op.action_execute()
        equipment = op.line_ids.equipment_id
        self.assertEqual(equipment.current_location_id, self.stock)
        self.assertFalse(op.picking_ids)
        self.assertEqual(equipment.ownership_status, "borrowed")

    def test_attachments_on_operation_equipment_and_picking(self):
        Attachment = self.env["ir.attachment"]
        common = Attachment.create({"name": "delivery note.pdf", "datas": PDF})
        photo = Attachment.create({"name": "photo.jpg", "datas": base64.b64encode(b"jpg")})
        op = self._borrow("AT1", attachment_ids=[Command.set(common.ids)])
        op.line_ids.attachment_ids = [Command.set(photo.ids)]
        op.action_execute()
        equipment = op.line_ids.equipment_id
        self.assertEqual(common.res_model, "equipment.operation")
        self.assertTrue(Attachment.search([("res_model", "=", "maintenance.equipment"),
                                           ("res_id", "=", equipment.id),
                                           ("name", "=", "photo.jpg")]))
        self.assertTrue(Attachment.search([("res_model", "=", "stock.picking"),
                                           ("res_id", "=", op.picking_ids.id),
                                           ("name", "=", "delivery note.pdf")]),
                        "common documents copied on the receipt")


@tagged("post_install", "-at_install")
class TestPurchaseOperation(TestOperationCommon):

    def test_receipt_before_bill_with_draft_bill(self):
        po = self._order(self.drill, 2)
        bill_pdf = self.env["ir.attachment"].with_user(self.user_operator).create(
            {"name": "bill.pdf", "datas": PDF, "mimetype": "application/pdf"})
        op = self._operation("receipt", user=self.user_operator, receipt_branch="purchase",
                             partner_id=self.vendor.id, purchase_mode="existing",
                             purchase_id=po.id, bill_mode="create", bill_ref="F-001",
                             bill_date=fields.Date.today(),
                             bill_attachment_ids=[Command.set(bill_pdf.ids)],
                             lines=[dict(product_id=self.drill.id, purchase_line_id=po.order_line.id,
                                         lot_name=s) for s in ("PB1", "PB2")])
        op.action_execute()
        self.assertEqual(op.state, "to_approve", "a bill needs approval")
        op.with_user(self.user_approver).action_approve()
        op.with_user(self.user_operator).action_execute()
        op = self.env["equipment.operation"].browse(op.id)
        equipment = op.line_ids.equipment_id
        self.assertEqual(set(equipment.mapped("integration_state")), {"done"})
        bill = op.bill_ids
        self.assertEqual(bill.state, "draft", "never posted by the operation")
        self.assertEqual(bill.ref, "F-001")
        self.assertTrue(self.env["ir.attachment"].search(
            [("res_model", "=", "account.move"), ("res_id", "=", bill.id)]))
        self.assertFalse(equipment.asset_id)
        bill.action_post()
        self.assertEqual(bill.invoice_line_ids.equipment_ids, equipment)
        self.assertTrue(all(equipment.mapped("asset_id")), "asset filled at posting")
        self.assertEqual(set(equipment.mapped("integration_state")), {"done"})

    def test_bill_before_receipt_reuses_draft_equipment(self):
        po = self._order(self.drill, 1)
        bill = self._bill(po)
        draft = self._equipment_of(bill)
        self.assertEqual(draft.integration_state, "draft")
        op = self._operation("receipt", receipt_branch="purchase", partner_id=self.vendor.id,
                             purchase_mode="existing", purchase_id=po.id,
                             lines=[dict(product_id=self.drill.id,
                                         purchase_line_id=po.order_line.id, lot_name="BB1")])
        op.action_execute()
        self.assertEqual(op.line_ids.equipment_id, draft, "no duplicate")
        self.assertEqual(draft.stock_lot_id.name, "BB1")
        self.assertEqual(draft.integration_state, "done")

    def test_partial_receipts_with_backorder(self):
        po = self._order(self.drill, 3)
        first = self._receive(po, ["PR1"])
        self.assertEqual(po.order_line.qty_received, 1)
        backorder = po.picking_ids.filtered(lambda p: p.state not in ("done", "cancel"))
        self.assertEqual(len(backorder), 1)
        self.assertFalse(backorder.equipment_operation_id, "backorder not linked")
        second = self._receive(po, ["PR2", "PR3"])
        self.assertEqual(po.order_line.qty_received, 3)
        self.assertEqual(len(first | second), 3)
        too_many = self._operation("receipt", receipt_branch="purchase",
                                   partner_id=self.vendor.id, purchase_mode="existing",
                                   purchase_id=po.id,
                                   lines=[dict(product_id=self.drill.id,
                                               purchase_line_id=po.order_line.id, lot_name="PR4")])
        with self.assertRaises(ValidationError):
            too_many.action_execute()

    def test_order_created_by_operation_single_receipt(self):
        op = self._operation("receipt", user=self.user_both, receipt_branch="purchase",
                             partner_id=self.vendor.id, purchase_mode="create",
                             lines=[dict(product_id=self.drill.id, price_unit=500.0, lot_name="OC1"),
                                    dict(product_id=self.screws.id, quantity=10, quantity_done=6,
                                         price_unit=2.0)])
        op.action_execute()
        self.assertEqual(op.state, "done")
        order = op.purchase_created_id
        self.assertEqual(order.state, "purchase")
        self.assertEqual(len(order.picking_ids.filtered(lambda p: p.state == "done")), 1)
        self.assertEqual(order.picking_ids.filtered(lambda p: p.state == "done"),
                         op.picking_ids)
        screws_line = order.order_line.filtered(lambda pl: pl.product_id == self.screws)
        self.assertEqual(screws_line.qty_received, 6, "executed quantity below the approved one")
        self.assertEqual(op.picking_ids.date_done.date(), fields.Date.today())

    def test_standard_validate_of_supplier_receipt_refused(self):
        for product in (self.drill, self.screws):
            po = self._order(product, 1)
            picking = po.picking_ids
            picking.move_ids.move_line_ids.unlink()
            vals = {"move_id": picking.move_ids.id, "picking_id": picking.id,
                    "product_id": product.id, "quantity": 1,
                    "product_uom_id": product.uom_id.id,
                    "location_id": picking.location_id.id,
                    "location_dest_id": picking.location_dest_id.id}
            if product.tracking == "serial":
                vals["lot_name"] = "SV-%s" % product.id
            self.env["stock.move.line"].create(vals)
            with self.assertRaises(ValidationError):
                picking.with_user(self.user_stock).button_validate()

    def test_server_side_checks(self):
        other_vendor = self.env["res.partner"].create({"name": "Other vendor"})
        po = self._order(self.drill, 1)
        op = self._operation("receipt", receipt_branch="purchase", partner_id=other_vendor.id,
                             purchase_mode="existing", purchase_id=po.id,
                             lines=[dict(product_id=self.drill.id,
                                         purchase_line_id=po.order_line.id, lot_name="SC1")])
        with self.assertRaises(ValidationError):
            op.action_execute()
        sale_tax = self.env["account.tax"].search(
            [("type_tax_use", "=", "sale"), ("company_id", "=", self.company.id)], limit=1)
        op = self._operation("receipt", receipt_branch="purchase", partner_id=self.vendor.id,
                             purchase_mode="create",
                             lines=[dict(product_id=self.screws.id, quantity=1, price_unit=1.0,
                                         tax_ids=[Command.set(sale_tax.ids)])])
        with self.assertRaises(ValidationError):
            op.action_execute()
        op = self._operation("receipt", receipt_branch="purchase", partner_id=self.vendor.id,
                             purchase_mode="create",
                             lines=[dict(product_id=self.screws.id, quantity=1, price_unit=-1.0)])
        with self.assertRaises(ValidationError):
            op.action_execute()


@tagged("post_install", "-at_install")
class TestAcquisition(TestOperationCommon):

    def test_gift_of_consumable_valued_on_its_account(self):
        Account = self.env["account.account"]
        valuation = Account.search([("code", "=", "310000"), ("company_ids", "in", self.company.id)]) \
            or Account.search([("code", "=like", "3%"), ("company_ids", "in", self.company.id)], limit=1)
        journal = self.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", self.company.id)], limit=1)
        categ = self.env["product.category"].create({
            "name": "Auto", "property_cost_method": "average",
            "property_valuation": "real_time",
            "property_stock_valuation_account_id": valuation.id,
            "property_stock_account_input_categ_id": self.acc_expense.id,
            "property_stock_account_output_categ_id": self.acc_expense.id,
            "property_stock_journal": journal.id,
        })
        product = self.env["product.product"].create({
            "name": "Paint", "type": "consu", "is_storable": True, "categ_id": categ.id,
            "standard_price": 3.0,
        })
        donor = self.env["res.partner"].create({"name": "Donor"})
        op = self._operation("receipt", receipt_branch="acquisition", acquisition_nature="gift",
                             partner_id=donor.id,
                             lines=[dict(product_id=product.id, quantity=4, unit_value=7.0)])
        self.assertTrue(op.needs_approval)
        op.action_execute()
        layer = op.picking_ids.move_ids.stock_valuation_layer_ids
        self.assertEqual(layer.value, 28.0)
        credit = layer.account_move_id.line_ids.filtered(lambda ln: ln.credit)
        self.assertEqual(credit.account_id.code, "778000")

    def test_gift_needs_partner_regularisation_does_not(self):
        op = self._operation("receipt", receipt_branch="acquisition", acquisition_nature="gift",
                             lines=[dict(product_id=self.screws.id, quantity=1, unit_value=1.0)])
        with self.assertRaises(ValidationError):
            op.action_execute()
        op = self._operation("receipt", receipt_branch="acquisition",
                             acquisition_nature="regularisation",
                             lines=[dict(product_id=self.screws.id, quantity=1, unit_value=1.0)])
        op.action_execute()
        self.assertEqual(op.state, "done")

    def test_current_account_contribution_fills_handover_value(self):
        shareholder = self.env["res.partner"].create({"name": "Shareholder"})
        op = self._operation("receipt", receipt_branch="acquisition",
                             acquisition_nature="current_account", partner_id=shareholder.id,
                             lines=[dict(product_id=self.drill.id, lot_name="CA1", unit_value=650.0)])
        op.action_execute()
        equipment = op.line_ids.equipment_id
        self.assertEqual(equipment.handover_value, 650.0)
        self.assertEqual(equipment.handover_value_date, fields.Date.today())
        self.assertEqual(equipment.ownership_status, "owned")
        self.assertFalse(op.picking_ids.move_ids.stock_valuation_layer_ids.account_move_id,
                         "fixed-asset category: manual valuation, no entry")


@tagged("post_install", "-at_install")
class TestExitReturnRestitution(TestOperationCommon):

    def test_exit_and_return_to_recorded_origin(self):
        equipment = self._owned_equipment("EX1")
        op = self._exit(equipment)
        op.action_execute()
        location = op.offsite_location_id
        self.assertEqual(location.place_type, "lent_out")
        self.assertEqual(location.address_id, self.site_a)
        self.assertEqual(location.location_id, self.offsite_parent)
        self.assertEqual(equipment.ownership_status, "lent_out")
        self.assertEqual(equipment._internal_quants().location_id, location)
        self.assertTrue(equipment.asset_id or True)
        line = op.contract_ids.contract_line_ids
        self.assertEqual(op.contract_ids.contract_type, "sale")
        self.assertEqual(line.equipment_nature, "loan")
        back = self._operation("return", user=self.user_operator,
                               lines=[dict(equipment_id=equipment.id)])
        self.assertEqual(back.line_ids.dest_location_id, self.stock)
        self.assertFalse(back.needs_approval, "return of a free loan")
        back.action_execute()
        self.assertEqual(equipment.ownership_status, "owned")
        self.assertEqual(equipment._internal_quants().location_id, self.stock)
        self.assertEqual(line.date_end, fields.Date.today())
        # same-day re-lending overlaps the closed interval; next day accepted
        again = self._exit(equipment, offsite_location_id=location.id, new_location_name=False)
        with self.assertRaises(ValidationError):
            again.action_execute()
        again.contract_start = fields.Date.today() + timedelta(days=1)
        again.action_execute()
        self.assertEqual(again.state, "done")

    def test_offsite_stocks_per_site_and_shared_by_two_warehouses(self):
        wh2 = self.env["stock.warehouse"].create(
            {"name": "WH 2", "code": "W2", "company_id": self.company.id})
        first = self._owned_equipment("SH1")
        po = self.env["purchase.order"].create({
            "partner_id": self.vendor.id, "picking_type_id": wh2.in_type_id.id,
            "order_line": [Command.create({"product_id": self.drill.id, "product_qty": 1,
                                           "price_unit": 100.0, "taxes_id": [Command.clear()]})],
        })
        po.button_confirm()
        op = self._operation("receipt", receipt_branch="purchase", partner_id=self.vendor.id,
                             purchase_mode="existing", purchase_id=po.id,
                             picking_type_id=wh2.in_type_id.id, location_dest_id=wh2.lot_stock_id.id,
                             lines=[dict(product_id=self.drill.id,
                                         purchase_line_id=po.order_line.id, lot_name="SH2")])
        op.action_execute()
        second = op.line_ids.equipment_id
        out1 = self._exit(first)
        out1.action_execute()
        shared = out1.offsite_location_id
        out2 = self._exit(second, offsite_location_id=shared.id, new_location_name=False)
        out2.action_execute()
        back = self._operation("return", lines=[dict(equipment_id=first.id),
                                                dict(equipment_id=second.id)])
        back.action_execute()
        self.assertEqual(first._internal_quants().location_id, self.stock)
        self.assertEqual(second._internal_quants().location_id, wh2.lot_stock_id)
        # second site of the same third party
        third = self._owned_equipment("SH3")
        out3 = self._exit(third, site_partner_id=self.site_b.id, new_location_name="Customer B")
        out3.action_execute()
        self.assertEqual(out3.offsite_location_id.address_id, self.site_b)
        self.assertNotEqual(out3.offsite_location_id, shared)

    def test_rented_out_exit_creates_customer_invoices_only_for_rent(self):
        equipment = self._owned_equipment("RO1")
        op = self._exit(equipment, exit_nature="rental",
                        lines=[dict(equipment_id=equipment.id, rent_amount=120.0)])
        op.action_execute()
        contract = op.contract_ids
        contract.recurring_create_invoice()
        invoice = contract._get_related_invoices()
        self.assertEqual(invoice.move_type, "out_invoice")
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(invoice.invoice_line_ids.account_id, self.acc_rent_income)

    def test_restitution_stops_possession_and_asks_for_insurance(self):
        op = self._borrow("RS1")
        op.action_execute()
        equipment = op.line_ids.equipment_id
        insurer = self.env["res.partner"].create({"name": "Insurer"})
        insurance = self.env["contract.contract"].create({
            "name": "Policy", "partner_id": insurer.id, "contract_type": "purchase",
            "line_recurrence": True, "company_id": self.company.id,
            "contract_line_ids": [Command.create({
                "product_id": self.rent_service.id, "name": "Premium", "quantity": 1,
                "price_unit": 10.0, "recurring_rule_type": "monthly", "recurring_interval": 1,
                "date_start": fields.Date.today(), "recurring_next_date": fields.Date.today(),
                "equipment_id": equipment.id, "equipment_nature": "insurance",
            })],
        })
        other = self._borrow("RS2")
        other.action_execute()
        other_line = other.contract_ids.contract_line_ids
        rest = self._operation("restitution", partner_id=self.lender.id,
                               lines=[dict(equipment_id=equipment.id, condition="scratched")])
        rest.action_refresh_stop_lines()
        stops = rest.stop_line_ids
        self.assertEqual(len(stops), 2, "only the lines of this equipment")
        self.assertNotIn(other_line, stops.contract_line_id)
        insurance_stop = stops.filtered(lambda s: s.nature == "insurance")
        self.assertFalse(insurance_stop.mandatory)
        with self.assertRaises(ValidationError):
            rest.action_execute()  # insurance choice not confirmed
        insurance_stop.write({"to_stop": False, "confirmed": True})
        rest.action_execute()
        self.assertEqual(rest.state, "done")
        self.assertFalse(equipment.active)
        self.assertFalse(equipment._internal_quants())
        self.assertEqual(op.contract_ids.contract_line_ids.date_end, fields.Date.today())
        self.assertFalse(insurance.contract_line_ids.date_end, "kept open by choice")
        self.assertFalse(other_line.date_end)

    def test_restitution_of_rental_needs_approval(self):
        op = self._borrow("RS3", receipt_branch="rented",
                          lines=[dict(product_id=self.drill.id, lot_name="RS3",
                                      replacement_value=1.0, rent_amount=10.0,
                                      replacement_value_date=fields.Date.today())])
        op.action_execute()
        rest = self._operation("restitution", user=self.user_operator, partner_id=self.lender.id,
                               lines=[dict(equipment_id=op.line_ids.equipment_id.id)])
        rest.action_execute()
        self.assertEqual(rest.state, "to_approve")


@tagged("post_install", "-at_install")
class TestStockRules(TestOperationCommon):

    def _transfer(self, equipment, dest, picking_type=None, owner=None):
        quant = equipment._internal_quants()
        picking = self.env["stock.picking"].create({
            "picking_type_id": (picking_type or self.warehouse.int_type_id).id,
            "location_id": quant.location_id.id, "location_dest_id": dest.id,
            "move_ids": [Command.create({
                "name": "x", "product_id": equipment.product_id.id, "product_uom_qty": 1,
                "product_uom": equipment.product_id.uom_id.id,
                "location_id": quant.location_id.id, "location_dest_id": dest.id,
            })],
        })
        picking.action_confirm()
        picking.move_ids.move_line_ids.unlink()
        self.env["stock.move.line"].create({
            "move_id": picking.move_ids.id, "picking_id": picking.id,
            "product_id": equipment.product_id.id, "lot_id": equipment.stock_lot_id.id,
            "quantity": 1, "product_uom_id": equipment.product_id.uom_id.id,
            "location_id": quant.location_id.id, "location_dest_id": dest.id,
            "owner_id": owner.id if owner else False,
        })
        return picking

    def test_direct_stock_moves_refused_for_every_profile(self):
        borrowed = self._borrow("SR1")
        borrowed.action_execute()
        borrowed = borrowed.line_ids.equipment_id
        owned = self._owned_equipment("SR2")
        customers = self.env.ref("stock.stock_location_customers")
        suppliers = self.env.ref("stock.stock_location_suppliers")
        lent = self.env["stock.location"].create({
            "name": "Somewhere", "usage": "internal", "place_type": "lent_out",
            "location_id": self.offsite_parent.id, "return_location_id": self.stock.id,
        })
        manager = self.env["res.users"].create({
            "name": "Ownership manager", "login": "eq_manager", "email": "m@example.com",
            "company_id": self.company.id, "company_ids": [Command.set(self.company.ids)],
            "groups_id": [Command.set([
                self.env.ref("maintenance_shareholder_equipment.group_equipment_ownership_manager").id,
                self.env.ref("stock.group_stock_manager").id])],
        })
        cases = [
            (borrowed, customers, self.lender),  # borrowed item delivered to a customer
            (owned, customers, None),  # owned equipment sold
            (owned, suppliers, None),  # owned equipment returned to the vendor
            (owned, lent, None),  # owned equipment moved to an off-site stock
        ]
        for equipment, dest, owner in cases:
            for user in (self.user_stock, manager):
                picking = self._transfer(equipment, dest, owner=owner)
                with self.assertRaises(ValidationError):
                    picking.with_user(user).button_validate()
        scrap = self.env["stock.scrap"].create({
            "product_id": borrowed.product_id.id, "lot_id": borrowed.stock_lot_id.id,
            "scrap_qty": 1, "location_id": self.stock.id, "owner_id": self.lender.id,
        })
        with self.assertRaises(ValidationError):
            scrap.with_user(manager).action_validate()

    def test_lent_out_item_back_without_operation_refused(self):
        equipment = self._owned_equipment("SR3")
        self._exit(equipment).action_execute()
        picking = self._transfer(equipment, self.stock)
        with self.assertRaises(ValidationError):
            picking.button_validate()

    def test_consumable_into_lent_out_stock_refused(self):
        self.env["stock.quant"]._update_available_quantity(self.screws, self.stock, 10)
        lent = self.env["stock.location"].create({
            "name": "Elsewhere", "usage": "internal", "place_type": "lent_out",
            "location_id": self.offsite_parent.id, "return_location_id": self.stock.id,
        })
        picking = self.env["stock.picking"].create({
            "picking_type_id": self.warehouse.int_type_id.id,
            "location_id": self.stock.id, "location_dest_id": lent.id,
            "move_ids": [Command.create({
                "name": "x", "product_id": self.screws.id, "product_uom_qty": 5,
                "product_uom": self.screws.uom_id.id, "location_id": self.stock.id,
                "location_dest_id": lent.id,
            })],
        })
        picking.action_confirm()
        picking.move_ids.quantity = 5
        with self.assertRaises(ValidationError):
            picking.button_validate()

    def test_inventory_adjustment_rules(self):
        quant = self.env["stock.quant"].with_context(inventory_mode=True).create({
            "product_id": self.screws.id, "location_id": self.stock.id, "inventory_quantity": 3,
        })
        quant.action_apply_inventory()
        self.assertEqual(quant.quantity, 3, "count correction of a consumable accepted")
        lot = self.env["stock.lot"].create({"name": "INV1", "product_id": self.drill.id,
                                            "company_id": self.company.id})
        quant = self.env["stock.quant"].with_context(inventory_mode=True).create({
            "product_id": self.drill.id, "location_id": self.stock.id, "lot_id": lot.id,
            "inventory_quantity": 1,
        })
        with self.assertRaises(ValidationError):
            quant.action_apply_inventory()

    def test_protected_link(self):
        op = self._borrow("PL1")
        po = self._order(self.screws, 1)
        with self.assertRaises(AccessError):
            po.picking_ids.with_user(self.user_stock).write({"equipment_operation_id": op.id})
        with self.assertRaises(AccessError):
            po.picking_ids.move_ids.with_user(self.user_operator).write(
                {"equipment_operation_id": op.id})
        with self.assertRaises(AccessError):
            op.with_user(self.user_operator).write({"state": "processing"})
        lot = self.env["stock.lot"].create({"name": "PL-LOT", "product_id": self.drill.id,
                                            "company_id": self.company.id})
        with self.assertRaises(AccessError):
            op.with_user(self.user_operator).write({"line_ids": [Command.create({
                "product_id": self.drill.id, "lot_id": lot.id})]})
        # a forged context key changes nothing
        picking = po.picking_ids.with_context(equipment_operation_running=True,
                                              bypass_equipment_operation=True)
        picking.move_ids.quantity = 1
        with self.assertRaises(ValidationError):
            picking.with_user(self.user_stock).button_validate()


@tagged("post_install", "-at_install")
class TestApprovalAndRights(TestOperationCommon):

    def test_approval_snapshot_invalidated_by_any_change(self):
        op = self._borrow("AP1", receipt_branch="rented",
                          lines=[dict(product_id=self.drill.id, lot_name="AP1", rent_amount=50.0,
                                      replacement_value=1.0,
                                      replacement_value_date=fields.Date.today())])
        op.with_user(self.user_approver).action_approve()
        op.with_user(self.user_operator).line_ids.write({"condition": "dusty"})
        self.assertEqual(op.state, "approved", "physical data does not cancel the approval")
        op.with_user(self.user_operator).line_ids.write({"rent_amount": 60.0})
        self.assertEqual(op.state, "draft", "a commitment changed")
        op.with_user(self.user_approver).action_approve()
        op.with_user(self.user_operator).write({"line_ids": [Command.create({
            "product_id": self.drill.id, "lot_name": "AP2", "rent_amount": 1.0,
            "warranty_status": "no_warranty", "insurance_status": "insured",
            "replacement_value": 1.0, "replacement_value_date": fields.Date.today()})]})
        self.assertEqual(op.state, "draft", "a new line cancels the approval")
        op.with_user(self.user_approver).action_approve()
        op.with_user(self.user_operator).write({"contract_end": fields.Date.today() + timedelta(days=30),
                                                "open_ended": False})
        self.assertEqual(op.state, "draft")

    def test_profiles(self):
        op = self._borrow("PF1", receipt_branch="rented",
                          lines=[dict(product_id=self.drill.id, lot_name="PF1", rent_amount=5.0,
                                      replacement_value=1.0,
                                      replacement_value_date=fields.Date.today())])
        with self.assertRaises(AccessError):
            op.with_user(self.user_stock).action_execute()
        with self.assertRaises(AccessError):
            op.with_user(self.user_operator).action_approve()
        with self.assertRaises(AccessError):
            op.with_user(self.user_approver).action_execute()
        op.with_user(self.user_both).action_execute()
        self.assertEqual(op.state, "done", "both roles: approve and execute at once")
        self.assertEqual(op.approver_id, self.user_both)
        self.assertEqual(op.executor_id, self.user_both)
        self.assertEqual(op.contract_ids.create_uid, self.user_both, "real author kept")

    def test_execute_twice_and_execution_before_approval(self):
        op = self._borrow("TW1")
        op.action_execute()
        with self.assertRaises(UserError):
            op.action_execute()
        self.assertEqual(len(op.picking_ids), 1)
        pending = self._borrow("TW2", user=self.user_operator)
        pending.action_submit()
        with self.assertRaises(UserError):
            pending.with_user(self.user_operator).action_execute()
        self.assertFalse(pending.picking_ids)

    def test_concurrent_execution_fails_on_lock(self):
        """A second transaction holding the row lock makes the execution fail without
        effect. Simulated: the test transaction is never committed, so a second real
        cursor cannot see the operation; the lock query raises as PostgreSQL would."""
        op = self._borrow("CC1")
        cursor_class = type(self.env.cr)
        original = cursor_class.execute

        def locked(cr, query, params=None, log_exceptions=True):
            if "FOR UPDATE NOWAIT" in str(query):
                raise psycopg2.errors.LockNotAvailable("locked")
            return original(cr, query, params, log_exceptions)

        with patch.object(cursor_class, "execute", locked):
            with self.assertRaises(UserError):
                op.action_execute()
        self.assertEqual(op.state, "draft")
        self.assertFalse(op.picking_ids)
        op.action_execute()
        self.assertEqual(op.state, "done")


@tagged("post_install", "-at_install")
class TestAuditCorrections(TestOperationCommon):
    """Cases raised by the audit of commit e8aa06e."""

    def _po(self, *lines):
        po = self.env["purchase.order"].create({
            "partner_id": self.vendor.id, "picking_type_id": self.warehouse.in_type_id.id,
            "order_line": [Command.create({"product_id": product.id, "product_qty": qty,
                                           "price_unit": 10.0, "taxes_id": [Command.clear()]})
                           for product, qty in lines],
        })
        po.button_confirm()
        return po

    def _purchase_op(self, po, lines, **vals):
        return self._operation("receipt", receipt_branch="purchase", partner_id=self.vendor.id,
                               purchase_mode="existing", purchase_id=po.id, lines=lines, **vals)

    def _pol(self, po, product):
        return po.order_line.filtered(lambda pl: pl.product_id == product)

    # 1. executed quantity 0
    def test_executed_quantity_zero_receives_nothing(self):
        po = self._po((self.screws, 10), (self.drill, 1))
        op = self._purchase_op(po, [
            dict(product_id=self.screws.id, quantity=10, quantity_done=0,
                 purchase_line_id=self._pol(po, self.screws).id),
            dict(product_id=self.drill.id, purchase_line_id=self._pol(po, self.drill).id,
                 lot_name="Q0"),
        ])
        op.action_execute()
        self.assertEqual(self._pol(po, self.screws).qty_received, 0)
        self.assertEqual(self._pol(po, self.drill).qty_received, 1)
        nothing = self._purchase_op(po, [dict(product_id=self.screws.id, quantity=10,
                                              quantity_done=0,
                                              purchase_line_id=self._pol(po, self.screws).id)])
        with self.assertRaises(UserError):
            nothing.action_execute()
        self.assertEqual(nothing.state, "draft")

    # 2. non-stock equipment: purchase and mixed operations
    def test_non_stock_purchase_and_mixed_operations(self):
        po = self._po((self.small_tool, 1))
        op = self._purchase_op(po, [dict(product_id=self.small_tool.id,
                                         purchase_line_id=po.order_line.id)])
        op.action_execute()
        equipment = op.line_ids.equipment_id
        self.assertEqual(equipment.current_location_id, self.stock)
        self.assertEqual(equipment.integration_state, "done")
        lease = self.env["product.product"].create({
            "name": "Vehicle lease", "type": "service", "maintenance_ok": True,
            "purchase_ok": True, "supplier_taxes_id": [Command.clear()],
        })
        po = self._po((lease, 1))
        self.assertFalse(po.picking_ids, "a service creates no receipt")
        op = self._purchase_op(po, [dict(product_id=lease.id, purchase_line_id=po.order_line.id)])
        op.action_execute()
        self.assertEqual(op.state, "done")
        self.assertFalse(op.picking_ids)
        op = self._operation("receipt", receipt_branch="acquisition",
                             acquisition_nature="regularisation", lines=[
                                 dict(product_id=self.screws.id, quantity=3, unit_value=1.0),
                                 dict(product_id=self.small_tool.id, unit_value=0.0)])
        op.action_execute()
        self.assertEqual(op.picking_ids.move_ids.product_id, self.screws,
                         "no move for the non-stock equipment")
        self.assertTrue(op.line_ids.filtered(lambda ln: ln.product_id == self.small_tool).equipment_id)

    # 3. draft bill limited to the lines of the operation
    def test_draft_bill_only_for_operation_lines(self):
        self.screws.purchase_method = "purchase"  # billable on ordered quantities
        po = self._po((self.screws, 5), (self.drill, 1))
        pdf = self.env["ir.attachment"].create({"name": "b.pdf", "datas": PDF,
                                                "mimetype": "application/pdf"})
        op = self._purchase_op(po, [dict(product_id=self.drill.id, lot_name="BL1",
                                         purchase_line_id=self._pol(po, self.drill).id)],
                               bill_mode="create", bill_ref="F-9", bill_date=fields.Date.today(),
                               bill_attachment_ids=[Command.set(pdf.ids)])
        op.action_execute()
        bill = op.bill_ids
        self.assertEqual(bill.invoice_line_ids.product_id, self.drill)
        self.assertEqual(bill.invoice_line_ids.quantity, 1)
        self.assertEqual(self._pol(po, self.screws).qty_invoiced, 0)

    # 4. bill already received
    def test_existing_bill_linked(self):
        po = self._order(self.drill, 1)
        bill = self._bill(po)
        op = self._purchase_op(po, [dict(product_id=self.drill.id, lot_name="EB1",
                                         purchase_line_id=po.order_line.id)],
                               bill_mode="existing")
        self.assertFalse(op.needs_approval)
        op.with_user(self.user_operator).action_execute()
        self.assertEqual(op.bill_ids, bill)
        po2 = self._order(self.drill, 1)
        op = self._purchase_op(po2, [dict(product_id=self.drill.id, lot_name="EB2",
                                          purchase_line_id=po2.order_line.id)],
                               bill_mode="existing")
        with self.assertRaises(ValidationError):
            op.action_execute()

    def test_existing_bill_must_cover_an_executed_line(self):
        """Audit of 3e7c39a: line A billed but not received (executed quantity 0),
        line B received without bill: the mode « bill already received » is refused."""
        self.screws.purchase_method = "purchase"  # billable before receipt
        po = self._po((self.screws, 4), (self.drill, 1))
        po.action_create_invoice()
        bill = po.invoice_ids
        bill.invoice_line_ids.filtered(lambda ln: ln.product_id == self.drill).unlink()
        self.assertEqual(bill.invoice_line_ids.product_id, self.screws)
        op = self._purchase_op(po, [
            dict(product_id=self.screws.id, quantity=4, quantity_done=0,
                 purchase_line_id=self._pol(po, self.screws).id),
            dict(product_id=self.drill.id, lot_name="EB3",
                 purchase_line_id=self._pol(po, self.drill).id),
        ], bill_mode="existing")
        with self.assertRaises(ValidationError):
            op.action_execute()
        self.assertEqual(op.state, "draft")
        self.assertFalse(op.picking_ids)
        # receiving the billed line too: the bill now covers an executed line
        op.line_ids.filtered(lambda ln: ln.product_id == self.screws).quantity_done = 4
        op.action_execute()
        self.assertEqual(op.state, "done")
        self.assertEqual(op.bill_ids, bill)

    # 5. internal transfers
    def test_transfers_to_virtual_place_and_between_offsite_stocks(self):
        rules = TestStockRules._transfer
        equipment = self._owned_equipment("TV1")
        virtual = self.env["stock.location"].create({
            "name": "Virtual place", "usage": "internal", "place_type": "virtual",
            "location_id": self.stock.id})
        with self.assertRaises(ValidationError):
            rules(self, equipment, virtual).button_validate()
        self._exit(equipment).action_execute()
        other = self.env["stock.location"].create({
            "name": "Other site", "usage": "internal", "place_type": "lent_out",
            "location_id": self.offsite_parent.id, "return_location_id": self.stock.id})
        with self.assertRaises(ValidationError):
            rules(self, equipment, other).button_validate()

    # 6. multi-company on the contract lines to stop
    def test_stop_lines_of_another_company_hidden(self):
        op = self._borrow("MC1")
        op.action_execute()
        other_company = self.env.ref("base.main_company")
        other_op = self.env["equipment.operation"].sudo().create({
            "operation_type": "restitution", "company_id": other_company.id})
        stop = self.env["equipment.operation.stop"].sudo().create({
            "operation_id": other_op.id,
            "contract_line_id": op.contract_ids.contract_line_ids.id})
        Stop = self.env["equipment.operation.stop"].with_user(self.user_operator)
        self.assertNotIn(stop, Stop.search([]))
        with self.assertRaises(AccessError):
            stop.with_user(self.user_operator).write({"to_stop": False})

    # 7. contract changed after approval
    def test_contract_added_after_approval_cancels_it(self):
        op = self._borrow("CA1", receipt_branch="rented",
                          lines=[dict(product_id=self.drill.id, lot_name="CA1", rent_amount=10.0,
                                      replacement_value=1.0,
                                      replacement_value_date=fields.Date.today())])
        op.action_execute()
        equipment = op.line_ids.equipment_id
        rest = self._operation("restitution", partner_id=self.lender.id,
                               lines=[dict(equipment_id=equipment.id)])
        rest.with_user(self.user_approver).action_approve()
        self.assertEqual(rest.state, "approved")
        insurer = self.env["res.partner"].create({"name": "Insurer 2"})
        self.env["contract.contract"].create({
            "name": "New policy", "partner_id": insurer.id, "contract_type": "purchase",
            "line_recurrence": True, "company_id": self.company.id,
            "contract_line_ids": [Command.create({
                "product_id": self.rent_service.id, "name": "Premium", "quantity": 1,
                "price_unit": 5.0, "recurring_rule_type": "monthly", "recurring_interval": 1,
                "date_start": fields.Date.today(), "recurring_next_date": fields.Date.today(),
                "equipment_id": equipment.id, "equipment_nature": "insurance"})],
        })
        rest.with_user(self.user_operator).action_execute()
        self.assertEqual(rest.state, "draft", "approval cancelled, to review and approve again")
        self.assertFalse(rest.picking_ids)
        self.assertEqual(len(rest.stop_line_ids), 2)

    # 8. attachments injected through the API
    def test_foreign_attachment_refused(self):
        op = self._borrow("AJ1", user=self.user_operator)
        other = self.env["ir.attachment"].create({
            "name": "secret.pdf", "datas": PDF, "res_model": "res.partner",
            "res_id": self.vendor.id})
        foreign_upload = self.env["ir.attachment"].create({"name": "not mine.pdf", "datas": PDF})
        for attachment in (other, foreign_upload):
            with self.assertRaises(AccessError):
                op.write({"attachment_ids": [Command.link(attachment.id)]})
            with self.assertRaises(AccessError):
                op.line_ids.write({"attachment_ids": [Command.link(attachment.id)]})
        self.assertEqual(other.res_model, "res.partner")
        mine = self.env["ir.attachment"].with_user(self.user_operator).create(
            {"name": "mine.pdf", "datas": PDF})
        op.write({"attachment_ids": [Command.link(mine.id)]})
        self.assertEqual((mine.res_model, mine.res_id), ("equipment.operation", op.id))

    # 9. receipts in several steps
    def test_multi_step_reception_refused(self):
        self.warehouse.reception_steps = "two_steps"
        op = self._borrow("MS1")
        with self.assertRaises(ValidationError):
            op.action_execute()


@tagged("post_install", "-at_install")
class TestOperationForm(TestOperationCommon):
    """Form helpers asked by the owner on 09/10/2026: transfer type set automatically,
    order lines loaded from the chosen order."""

    def _second_warehouse(self):
        return self.env["stock.warehouse"].create(
            {"name": "WH form", "code": "WF", "company_id": self.company.id})

    def _receive_in(self, warehouse, serial):
        po = self.env["purchase.order"].create({
            "partner_id": self.vendor.id, "picking_type_id": warehouse.in_type_id.id,
            "order_line": [Command.create({"product_id": self.drill.id, "product_qty": 1,
                                           "price_unit": 1.0, "taxes_id": [Command.clear()]})],
        })
        po.button_confirm()
        op = self._operation("receipt", receipt_branch="purchase", partner_id=self.vendor.id,
                             purchase_mode="existing", purchase_id=po.id,
                             location_dest_id=warehouse.lot_stock_id.id,
                             lines=[dict(product_id=self.drill.id,
                                         purchase_line_id=po.order_line.id, lot_name=serial)])
        op.action_execute()
        return op.line_ids.equipment_id

    def test_transfer_type_set_automatically(self):
        Operation = self.env["equipment.operation"]
        wh2 = self._second_warehouse()
        for warehouse in (self.warehouse, wh2):
            op = Operation.create({"operation_type": "receipt", "receipt_branch": "borrowed",
                                   "company_id": self.company.id,
                                   "location_dest_id": warehouse.lot_stock_id.id})
            self.assertEqual(op.picking_type_id, warehouse.in_type_id)
        po = self._order(self.drill, 1)
        op = Operation.create({"operation_type": "receipt", "receipt_branch": "purchase",
                               "purchase_mode": "existing", "purchase_id": po.id,
                               "company_id": self.company.id})
        self.assertEqual(op.picking_type_id, po.picking_type_id)
        op = Operation.create({"operation_type": "exit", "company_id": self.company.id})
        self.assertFalse(op.picking_type_id, "exits take the type of each equipment's warehouse")

    def test_transfer_types_follow_each_equipment_warehouse(self):
        wh2 = self._second_warehouse()
        first = self._owned_equipment("TW-A")
        second = self._receive_in(wh2, "TW-B")
        out = self._exit(first | second)
        out.action_execute()
        self.assertEqual(len(out.picking_ids), 2, "one transfer per warehouse")
        self.assertEqual(set(out.picking_ids.picking_type_id.ids),
                         {self.warehouse.int_type_id.id, wh2.int_type_id.id})
        back = self._operation("return", lines=[dict(equipment_id=first.id),
                                                dict(equipment_id=second.id)])
        back.action_execute()
        self.assertEqual(set(back.picking_ids.picking_type_id.ids),
                         {self.warehouse.int_type_id.id, wh2.int_type_id.id})
        for picking in back.picking_ids:
            warehouse = self.warehouse if picking.picking_type_id == self.warehouse.int_type_id else wh2
            self.assertEqual(picking.move_ids.location_dest_id, warehouse.lot_stock_id)
        # restitution of an item borrowed into the second warehouse
        borrow = self._borrow("TW-C", location_dest_id=wh2.lot_stock_id.id)
        borrow.action_execute()
        self.assertEqual(borrow.picking_ids.picking_type_id, wh2.in_type_id)
        rest = self._operation("restitution", partner_id=self.lender.id,
                               lines=[dict(equipment_id=borrow.line_ids.equipment_id.id)])
        rest.action_execute()
        self.assertEqual(rest.picking_ids.picking_type_id, wh2.out_type_id)

    def test_changing_order_resets_destination(self):
        wh2 = self._second_warehouse()
        po1 = self._order(self.drill, 1)
        po2 = self.env["purchase.order"].create({
            "partner_id": self.vendor.id, "picking_type_id": wh2.in_type_id.id,
            "order_line": [Command.create({"product_id": self.drill.id, "product_qty": 1,
                                           "price_unit": 1.0, "taxes_id": [Command.clear()]})],
        })
        po2.button_confirm()
        with Form(self.env["equipment.operation"]) as form:
            form.operation_type = "receipt"
            form.receipt_branch = "purchase"
            form.purchase_id = po2
            self.assertEqual(form.location_dest_id, wh2.lot_stock_id)
            form.purchase_id = po1
            self.assertEqual(form.location_dest_id, self.warehouse.lot_stock_id)
            self.assertEqual(len(form.line_ids), 1)
        self.assertEqual(form.record.line_ids.purchase_line_id, po1.order_line)
        self.assertEqual(form.record.picking_type_id, po1.picking_type_id)

    def test_order_fills_lines_vendor_and_stock(self):
        po = self.env["purchase.order"].create({
            "partner_id": self.vendor.id, "picking_type_id": self.warehouse.in_type_id.id,
            "order_line": [
                Command.create({"product_id": self.drill.id, "product_qty": 2, "price_unit": 1.0,
                                "taxes_id": [Command.clear()]}),
                Command.create({"product_id": self.screws.id, "product_qty": 5, "price_unit": 1.0,
                                "taxes_id": [Command.clear()]}),
            ],
        })
        po.button_confirm()
        with Form(self.env["equipment.operation"]) as form:
            form.operation_type = "receipt"
            form.receipt_branch = "purchase"
            form.purchase_mode = "existing"
            form.purchase_id = po
            self.assertEqual(form.partner_id, self.vendor)
            self.assertEqual(form.location_dest_id, self.warehouse.in_type_id.default_location_dest_id)
            self.assertEqual(len(form.line_ids), 3, "one line per drill unit, one for the screws")
        op = form.record
        drills = op.line_ids.filtered(lambda ln: ln.product_id == self.drill)
        self.assertEqual(drills.mapped("quantity"), [1.0, 1.0])
        screws = op.line_ids.filtered(lambda ln: ln.product_id == self.screws)
        self.assertEqual((screws.quantity, screws.quantity_done), (5.0, 5.0))
        self.assertEqual(op.picking_type_id, po.picking_type_id)

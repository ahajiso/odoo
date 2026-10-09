"""Phase 2f: responsible required (point 9) and equipment cost (A1, correction 1),
docs/phase2f/PLAN.md §1 and §2."""
import importlib.util
import os

from dateutil.relativedelta import relativedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.modules.module import get_module_path
from odoo.tests import tagged

from .common import EquipmentCommon

REPO = os.path.dirname(get_module_path("maintenance_shareholder_equipment"))


@tagged("post_install", "-at_install")
class TestPhase2fResponsible(EquipmentCommon):

    def _purchase_op(self, po, serial, **line):
        pol = po.order_line[:1]
        return self._operation("receipt", receipt_branch="purchase", partner_id=po.partner_id.id,
                               purchase_mode="existing", purchase_id=po.id, lines=[dict(
                                   dict(product_id=pol.product_id.id, purchase_line_id=pol.id,
                                        lot_name=serial), **line)])

    def test_receipt_refuses_missing_or_invalid_responsible(self):
        Users = self.env["res.users"].with_context(no_reset_password=True)
        portal = Users.create({"name": "Portal", "login": "eq_portal", "company_id": self.company.id,
                               "company_ids": [Command.set(self.company.ids)],
                               "groups_id": [Command.set(self.env.ref("base.group_portal").ids)]})
        archived = Users.create({"name": "Gone", "login": "eq_gone", "company_id": self.company.id,
                                 "company_ids": [Command.set(self.company.ids)]})
        archived.active = False
        other_company = self.env["res.company"].create({"name": "Other company"})
        foreign = Users.create({"name": "Foreign", "login": "eq_foreign",
                                "company_id": other_company.id,
                                "company_ids": [Command.set(other_company.ids)]})
        for index, user in enumerate((self.env["res.users"], portal, archived, foreign)):
            with self.subTest(user=user.login or "none"):
                op = self._purchase_op(self._order(self.drill, 1), "RESP-%s" % index,
                                       responsible_user_id=user.id)
                with self.assertRaisesRegex(ValidationError, "responsible"):
                    op.action_execute()

    def test_receipt_copies_responsible(self):
        equipment = self._receive(self._order(self.drill, 1), ["RESP-OK"])
        self.assertEqual(equipment.owner_user_id, self.user_responsible)
        self.assertEqual(equipment.integration_state, "done")

    def test_integration_refused_without_responsible(self):
        equipment = self.env["maintenance.equipment"].create({
            "name": "Van", "current_location_id": self.stock.id,
            "warranty_status": "no_warranty", "insurance_status": "insured",
        })
        with self.assertRaisesRegex(ValidationError, "responsible"):
            equipment.action_finalize_integration()
        equipment.owner_user_id = self.user_responsible
        equipment.action_finalize_integration()
        with self.assertRaisesRegex(ValidationError, "responsible"):
            equipment.owner_user_id = False

    def test_precheck_finds_legacy_data(self):
        """The precheck query of the deployment finds an integrated equipment without
        responsible, the case the constraint cannot catch on existing data."""
        equipment = self._receive(self._order(self.drill, 1), ["LEGACY-1"])
        # legacy data, as before phase 2f (no ORM write can create it any more)
        self.env.flush_all()
        self.env.cr.execute("UPDATE maintenance_equipment SET owner_user_id = NULL WHERE id = %s",
                            [equipment.id])
        with open(os.path.join(REPO, "docs", "phase2f", "precheck.sql")) as sql:
            self.env.cr.execute(sql.read())
        rows = self.env.cr.fetchall()
        self.assertIn(("responsible", equipment.id), [(row[0], row[1]) for row in rows])


@tagged("post_install", "-at_install")
class TestPhase2fCost(EquipmentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.grinder = cls._product("Grinder", cls.categ_tools, storable=True)
        cls.pair = cls.env["uom.uom"].create({
            "name": "Pair (test)", "category_id": cls.env.ref("uom.product_uom_unit").category_id.id,
            "uom_type": "bigger", "factor_inv": 2.0, "rounding": 1.0,
        })
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.accountant = Users.create({
            "name": "Accounting admin", "login": "eq_acc_admin", "email": "acc@example.com",
            "company_id": cls.company.id,
            "company_ids": [Command.set(cls.company.ids)],
            "groups_id": [Command.set([cls.env.ref("base.group_user").id,
                                       cls.env.ref("account.group_account_manager").id])],
        })
        cls.ownership_manager = Users.create({
            "name": "Ownership manager", "login": "eq_own_mgr", "email": "own@example.com",
            "company_id": cls.company.id,
            "company_ids": [Command.set(cls.company.ids)],
            "groups_id": [Command.set([cls.env.ref("base.group_user").id, cls.env.ref(
                "maintenance_shareholder_equipment.group_equipment_ownership_manager").id])],
        })

    def _po(self, product, qty, price, **line):
        po = self.env["purchase.order"].create({
            "partner_id": self.vendor.id, "picking_type_id": self.warehouse.in_type_id.id,
            **{k: line.pop(k) for k in ("currency_id",) if k in line},
            "order_line": [Command.create(dict({
                "product_id": product.id, "product_qty": qty, "price_unit": price,
                "taxes_id": [Command.clear()]}, **line))],
        })
        po.button_confirm()
        return po

    def _receive_units(self, po, serials):
        pol = po.order_line[:1]
        op = self._operation("receipt", receipt_branch="purchase", partner_id=po.partner_id.id,
                             purchase_mode="existing", purchase_id=po.id, lines=[
                                 dict(product_id=pol.product_id.id, purchase_line_id=pol.id,
                                      lot_name=serial) for serial in serials])
        op.action_execute()
        return op.line_ids.equipment_id

    def assertCost(self, equipment, cost, provisional, source, date=None, reference=None):
        self.assertTrue(equipment.cost_known)
        self.assertAlmostEqual(equipment.cost, cost, places=2)
        self.assertEqual(equipment.cost_provisional, provisional)
        self.assertEqual(equipment.cost_source, source)
        if date:
            self.assertEqual(equipment.cost_date, date)
        if reference:
            self.assertIn(reference, equipment.cost_reference)

    def test_order_estimate_with_discount_and_pack_unit_then_bill(self):
        """Discount and unit of the order line together; the bill in packs gives the
        real cost per unit of the product, and one equipment per unit."""
        po = self._po(self.grinder, 1, 300.0, product_uom=self.pair.id, discount=10.0)
        equipment = self._receive_units(po, ["PAIR-1", "PAIR-2"])
        self.assertEqual(len(equipment), 2)
        for item in equipment:
            self.assertCost(item, 135.0, True, "order", fields.Date.today(), po.name)
        bill = self._bill(po)
        self.assertEqual(bill.invoice_line_ids.product_uom_id, self.pair)
        self.assertEqual(len(bill.invoice_line_ids.equipment_ids), 2)
        for item in equipment:
            self.assertCost(item, 135.0, False, "bill", bill.date, bill.name)

    def test_order_price_different_from_bill_price(self):
        po = self._order(self.drill, 1)
        equipment = self._receive_units(po, ["PRICE-1"])
        self.assertCost(equipment, 100.0, True, "order")
        bill = self._bill(po, post=False)
        bill.invoice_line_ids.price_unit = 120.0
        bill.action_post()
        self.assertCost(equipment, 120.0, False, "bill", bill.date, bill.name)

    def test_bill_before_receipt_keeps_real_cost(self):
        po = self._order(self.drill, 1)
        bill = self._bill(po, post=False)
        bill.invoice_line_ids.price_unit = 110.0
        bill.action_post()
        draft = self._equipment_of(bill)
        self.assertCost(draft, 110.0, False, "bill", bill.date)
        equipment = self._receive_units(po, ["EARLY-1"])
        self.assertEqual(equipment, draft)
        self.assertCost(equipment, 110.0, False, "bill", bill.date)

    def test_foreign_currency_rates_at_receipt_and_bill(self):
        usd = self.env.ref("base.USD")
        usd.active = True
        today = fields.Date.today()
        older = today - relativedelta(months=3)
        self.env["res.currency.rate"].create([
            {"currency_id": usd.id, "name": older, "rate": 1.10, "company_id": self.company.id},
            {"currency_id": usd.id, "name": today, "rate": 1.25, "company_id": self.company.id},
        ])
        po = self._po(self.drill, 1, 100.0, currency_id=usd.id)
        equipment = self._receive_units(po, ["USD-1"])
        self.assertCost(equipment, 100.0 / 1.25, True, "order", today)
        po.action_create_invoice()
        bill = po.invoice_ids[:1]
        bill.invoice_date = older
        bill.date = older
        bill.action_post()
        self.assertCost(equipment, 100.0 / 1.10, False, "bill", older)

    def test_partial_bill(self):
        # a product without asset profile: a fixed-asset bill line is split per unit
        po = self._order(self.grinder, 2)
        equipment = self._receive_units(po, ["PART-1", "PART-2"])
        bill = self._bill(po, qty=1, post=False)
        bill.invoice_line_ids.price_unit = 130.0
        bill.action_post()
        billed = self._equipment_of(bill)
        self.assertEqual(len(billed), 1)
        self.assertCost(billed, 130.0, False, "bill")
        self.assertCost(equipment - billed, 100.0, True, "order")

    def test_bill_reset_to_draft_then_cancelled(self):
        po = self._order(self.drill, 1)
        equipment = self._receive_units(po, ["CANCEL-1"])
        bill = self._bill(po, post=False)
        bill.invoice_line_ids.price_unit = 120.0
        bill.action_post()
        name = bill.name
        bill.button_draft()
        self.assertCost(equipment, 120.0, True, "bill", reference=name)
        bill.button_cancel()
        # the order estimate comes back, explained, although the bill link is gone
        self.assertFalse(equipment.move_line_id)
        self.assertCost(equipment, 100.0, True, "order", reference=po.name)

    def test_cancelled_bill_without_order_keeps_amount(self):
        bill = self.env["account.move"].create({
            "move_type": "in_invoice", "partner_id": self.vendor.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [Command.create({
                "product_id": self.small_tool.id, "quantity": 1, "price_unit": 50.0,
                "tax_ids": [Command.clear()]})],
        })
        bill.action_post()
        equipment = self._equipment_of(bill)
        self.assertCost(equipment, 50.0, False, "bill", bill.date, bill.name)
        name = bill.name
        bill.button_draft()
        bill.button_cancel()
        equipment = equipment.with_context(active_test=False)
        self.assertCost(equipment, 50.0, True, "bill_cancelled", reference=name)
        self.assertIn("cancelled", equipment.cost_reference)

    def test_release_from_draft_bill_is_not_a_cancellation(self):
        po = self._order(self.small_tool, 2)
        bill = self._bill(po)
        self.assertEqual(len(self._equipment_of(bill)), 2)
        name = bill.name
        bill.button_draft()
        bill.invoice_line_ids.quantity = 1
        bill.action_post()
        released = self.env["maintenance.equipment"].with_context(active_test=False).search(
            [("cost_source", "=", "bill_released")])
        self.assertEqual(len(released), 1)
        self.assertCost(released, 100.0, True, "bill_released", reference=name)
        self.assertIn("released from", released.cost_reference)

    def test_acquisition_cost_and_unknown_cost(self):
        op = self._operation("receipt", receipt_branch="acquisition", acquisition_nature="gift",
                             partner_id=self.lender.id,
                             lines=[dict(product_id=self.drill.id, lot_name="GIFT-1",
                                         unit_value=250.0)])
        op.with_user(self.user_both).action_execute()
        self.assertCost(op.line_ids.equipment_id, 250.0, False, "acquisition",
                        fields.Date.today(), op.name)
        borrowed = self._operation(
            "receipt", receipt_branch="borrowed", partner_id=self.lender.id,
            contract_start=fields.Date.today(), open_ended=True,
            lines=[dict(product_id=self.drill.id, lot_name="LOAN-1", replacement_value=900.0,
                        replacement_value_date=fields.Date.today())])
        borrowed.with_user(self.user_both).action_execute()
        self.assertFalse(borrowed.line_ids.equipment_id.cost_known)

    def test_correction_wizard_rights_and_real_zero(self):
        equipment = self._receive_units(self._order(self.drill, 1), ["FIX-1"])
        with self.assertRaises(AccessError):
            equipment.with_user(self.accountant).write({"cost": 1.0})
        Wizard = self.env["equipment.cost.correction"]
        with self.assertRaises(AccessError):
            Wizard.with_user(self.ownership_manager).create(
                {"equipment_id": equipment.id, "cost": 0.0, "reason": "x"}).action_apply()
        wizard = Wizard.with_user(self.accountant).create(
            {"equipment_id": equipment.id, "cost": 0.0, "cost_date": fields.Date.today(),
             "reason": "Free sample"})
        wizard.action_apply()
        self.assertCost(equipment, 0.0, False, "manual")
        self.assertTrue(equipment.cost_known)
        self.assertIn("Free sample", equipment.message_ids[:1].body)
        Wizard.with_user(self.accountant).create(
            {"equipment_id": equipment.id, "cost_known": False, "reason": "Unknown"}).action_apply()
        self.assertFalse(equipment.cost_known)

    def test_migration_fills_legacy_costs(self):
        equipment = self._receive_units(self._order(self.drill, 1), ["MIG-1"])
        equipment.sudo().write({"cost_known": False, "cost": 0.0, "cost_source": False,
                                "cost_provisional": False})
        path = os.path.join(get_module_path("maintenance_shareholder_equipment"),
                            "migrations", "18.0.3.1.0", "post-migrate.py")
        spec = importlib.util.spec_from_file_location("phase2f_post_migrate", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, "18.0.3.0.0")
        equipment.invalidate_recordset()
        self.assertCost(equipment, 100.0, True, "order")


@tagged("post_install", "-at_install")
class TestPhase2fPurchaseUnit(EquipmentCommon):
    """Order created by the operation when the purchase unit differs from the product's
    unit (audit of bad8e9f)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pair = cls.env["uom.uom"].create({
            "name": "Pair (test)", "category_id": cls.env.ref("uom.product_uom_unit").category_id.id,
            "uom_type": "bigger", "factor_inv": 2.0, "rounding": 1.0,
        })
        cls.paired = cls._product("Paired grinder", cls.categ_tools, storable=True)
        cls.paired.uom_po_id = cls.pair

    def _create_order_op(self, count):
        return self._operation(
            "receipt", receipt_branch="purchase", partner_id=self.vendor.id,
            purchase_mode="create", bill_mode="none",
            lines=[dict(product_id=self.paired.id, lot_name="PO-UOM-%s" % i, price_unit=60.0)
                   for i in range(count)])

    def test_two_pieces_make_one_pair_order_receipt_and_bill(self):
        op = self._create_order_op(2)
        op.with_user(self.user_both).action_execute()
        line = op.purchase_created_id.order_line
        self.assertEqual(line.product_uom, self.pair)
        self.assertEqual(line.product_qty, 1.0)
        self.assertAlmostEqual(line.price_unit, 120.0)
        self.assertEqual(line.qty_received, 1.0)
        equipment = op.line_ids.equipment_id
        self.assertEqual(len(equipment), 2)
        for item in equipment:
            self.assertAlmostEqual(item.cost, 60.0)
            self.assertTrue(item.cost_provisional)
        self.assertEqual(sum(op.picking_ids.move_ids.move_line_ids.mapped("quantity")), 2.0)
        bill = self._bill(op.purchase_created_id)
        bill_line = bill.invoice_line_ids
        self.assertEqual(bill_line.product_uom_id, self.pair)
        self.assertEqual(bill_line.quantity, 1.0)
        self.assertEqual(bill_line.equipment_ids, equipment)
        for item in equipment:
            self.assertAlmostEqual(item.cost, 60.0)
            self.assertFalse(item.cost_provisional)

    def test_quantity_not_a_whole_number_of_purchase_units_refused(self):
        op = self._create_order_op(3)
        with self.assertRaisesRegex(ValidationError, "whole number of Pair"):
            op.with_user(self.user_both).action_execute()
        self.assertFalse(op.purchase_created_id)

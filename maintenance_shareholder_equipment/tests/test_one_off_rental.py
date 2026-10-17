"""One-off supplier rental: physical unit, timed package and a single draft bill."""
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import EquipmentCommon


@tagged("post_install", "-at_install")
class TestOneOffRental(EquipmentCommon):
    def _package(self, **values):
        start = fields.Datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        vals = dict(
            receipt_branch="rented", partner_id=self.lender.id,
            rental_billing_mode="one_off", rental_start=start,
            rental_end=start + timedelta(hours=4), rental_timezone="Europe/Paris",
            open_ended=False, periodicity=False,
            lines=[dict(product_id=self.drill.id, lot_name="TEST-4H", rent_amount=120,
                        replacement_value=25000, replacement_value_date=fields.Date.today())],
        )
        vals.update(values)
        return self._operation("receipt", user=self.user_operator, **vals)

    def _execute_package(self):
        op = self._package()
        op.action_submit()
        op.with_user(self.user_approver).action_approve()
        op.action_execute()
        return self.env["equipment.operation"].browse(op.id)

    def test_package_receipt_bill_return_and_no_recurrence(self):
        op = self._execute_package()
        self.assertEqual(op.state, "done")
        self.assertEqual(op.rental_hours, 4)
        equipment = op.line_ids.equipment_id
        self.assertEqual(equipment.ownership_status, "rented")
        self.assertEqual(equipment.owner_partner_id, self.lender)
        self.assertEqual(equipment._internal_quants().quantity, 1)
        cl = op.contract_ids.contract_line_ids
        self.assertEqual(cl.equipment_rental_hours, 4)
        self.assertEqual(cl._prepare_invoice_line()["name"], cl.name)
        self.assertEqual(cl.equipment_billing_mode, "one_off")
        self.assertFalse(cl.recurring_next_date)
        self.assertFalse(op.contract_ids.recurring_next_date)
        self.assertEqual(cl.monthly_recurring, 0)
        self.assertEqual(cl._get_contract_line_total_value(), 120)
        self.assertFalse(cl._can_be_invoiced(fields.Date.today()))
        self.assertFalse(cl.create_invoice_visibility)
        bill = op.bill_ids
        self.assertEqual(len(bill), 1)
        self.assertEqual(bill.state, "draft")
        self.assertEqual(bill.invoice_line_ids.contract_line_id, cl)
        self.assertEqual(bill.invoice_line_ids.quantity, 1)
        self.assertEqual(bill.amount_untaxed, 120)
        self.assertEqual(cl._create_equipment_one_off_bill(), bill)
        bill.action_post()
        self.assertFalse(bill.invoice_line_ids.equipment_ids,
                         "rent service must never create another physical equipment")
        for delta in (1, 31, 366):
            op.contract_ids._recurring_create_invoice(date_ref=fields.Date.today() + timedelta(days=delta))
        self.assertEqual(cl._equipment_one_off_bills(), bill)
        restitution = self._operation(
            "restitution", user=self.user_both, partner_id=self.lender.id,
            lines=[dict(equipment_id=equipment.id)])
        restitution.action_execute()
        self.assertEqual(restitution.state, "done")
        self.assertFalse(equipment.active)
        self.assertFalse(equipment._internal_quants())
        self.assertEqual(cl._equipment_one_off_bills(), bill)

    def test_invalid_times_and_missing_times_do_not_submit(self):
        for values in (dict(rental_end=False), dict(rental_start=False),
                       dict(rental_end=fields.Datetime.now() - timedelta(days=1)),
                       dict(rental_timezone="Not/AZone"), dict(open_ended=True)):
            with self.subTest(values=values), self.env.cr.savepoint():
                op = self._package(**values)
                with self.assertRaises(ValidationError):
                    op.action_submit()
                self.assertFalse(op.bill_ids)
                self.assertFalse(op.picking_ids)

    def test_time_and_package_price_changes_cancel_approval(self):
        op = self._package()
        op.action_submit()
        op.with_user(self.user_approver).action_approve()
        op.write({"rental_end": op.rental_end + timedelta(hours=1)})
        self.assertEqual(op.state, "draft")
        op.action_submit()
        op.with_user(self.user_approver).action_approve()
        op.line_ids.write({"rent_amount": 150})
        self.assertEqual(op.state, "draft")
        self.assertFalse(op.bill_ids)

    def test_duplicate_manual_bill_and_wrong_amount_cannot_post(self):
        op = self._execute_package()
        bill = op.bill_ids
        duplicate = bill.copy()
        self.assertEqual(duplicate.invoice_line_ids.contract_line_id, bill.invoice_line_ids.contract_line_id)
        with self.assertRaisesRegex(UserError, "only one"):
            duplicate.action_post()
        duplicate.button_cancel()
        bill.invoice_line_ids.price_unit = 121
        with self.assertRaisesRegex(UserError, "package amount"):
            bill.action_post()
        bill.invoice_line_ids.price_unit = 120
        bill.action_post()

    def test_rent_cannot_be_billed_as_the_physical_product(self):
        op = self._execute_package()
        bill = op.bill_ids
        bill.invoice_line_ids.write({"product_id": self.drill.id, "price_unit": 120,
                                     "account_id": self.acc_rent.id})
        with self.assertRaisesRegex(UserError, "rental service"):
            bill.action_post()
        self.assertFalse(bill.invoice_line_ids.equipment_ids)

    def test_cancelled_bill_can_be_replaced_but_refund_does_not_rebill(self):
        op = self._execute_package()
        cl = op.contract_ids.contract_line_ids
        old = op.bill_ids
        old.button_cancel()
        bill = cl._create_equipment_one_off_bill()
        self.assertNotEqual(old, bill)
        bill.action_post()
        refund = bill._reverse_moves(default_values_list=[{"invoice_date": fields.Date.today()}])
        refund.action_post()
        self.assertEqual(cl._create_equipment_one_off_bill(), bill)
        self.assertFalse(cl._can_be_invoiced(fields.Date.today() + timedelta(days=366)))

    def test_operator_and_approver_cannot_use_billing_action(self):
        op = self._execute_package()
        cl = op.contract_ids.contract_line_ids
        for user in (self.user_operator, self.user_approver):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                cl.with_user(user).action_create_equipment_one_off_bill()

    def test_hour_range_is_converted_to_contract_dates_in_explicit_zone(self):
        start = fields.Datetime.to_datetime("2026-10-17 22:30:00")
        op = self._package(rental_start=start, rental_end=start + timedelta(hours=4))
        self.assertEqual(tuple(map(str, op._one_off_dates())), ("2026-10-18", "2026-10-18"))
        self.assertEqual(op.rental_hours, 4)

    def test_package_cannot_be_renewed_or_changed_after_draft_bill(self):
        op = self._execute_package()
        cl = op.contract_ids.contract_line_ids
        for vals in ({"price_unit": 130}, {"equipment_billing_mode": "recurring"},
                     {"equipment_rental_end": cl.equipment_rental_end + timedelta(hours=1)}):
            with self.subTest(vals=vals), self.assertRaises(UserError):
                cl.write(vals)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            cl.write({"is_auto_renew": True})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            cl.contract_id.write({"line_recurrence": False})

    def test_billing_lock_updates_parent_revision_and_is_not_a_public_field(self):
        op = self._execute_package()
        cl = op.contract_ids.contract_line_ids
        before = cl.equipment_billing_revision
        cl._create_equipment_one_off_bill()
        self.assertGreater(cl.equipment_billing_revision, before)
        with self.assertRaises(AccessError):
            cl.with_user(self.user_operator).write({"equipment_billing_revision": 0})

    def test_cancelled_bill_does_not_reopen_approved_package_commitment(self):
        # 08:00–12:00 UTC = the approved 10:00–14:00 Europe/Paris slot.
        op = self._package(rental_start="2026-10-17 08:00:00",
                           rental_end="2026-10-17 12:00:00")
        op.action_submit()
        op.with_user(self.user_approver).action_approve()
        op.action_execute()
        op = self.env["equipment.operation"].browse(op.id)
        cl = op.contract_ids.contract_line_ids
        old = op.bill_ids
        self.assertEqual(old.amount_untaxed, 120)
        approved_product = cl.product_id
        approved_uom = cl.uom_id
        old.button_cancel()
        accountant = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "TEST cancelled package accountant", "login": "cancelled_package_accountant",
            "email": "cancelled_package_accountant@example.com",
            "company_id": self.company.id, "company_ids": [Command.set(self.company.ids)],
            "groups_id": [Command.set([self.env.ref("base.group_user").id,
                                       self.env.ref("account.group_account_manager").id])],
        })
        # Include the inverse price source and automatic pricing, not only its
        # computed display value. The server guard also applies to sudo callers.
        changes = [{"price_unit": 1200}, {"specific_price": 1200},
                   {"discount": 50}, {"quantity": 2}, {"product_id": self.drill.id},
                   {"uom_id": self.env.ref("uom.product_uom_dozen").id},
                   {"automatic_price": True},
                   {"equipment_rental_start": "2026-10-17 06:00:00"},
                   {"equipment_rental_end": "2026-10-17 16:00:00"},
                   {"price_unit": 1200, "equipment_rental_start": "2026-10-17 06:00:00",
                    "equipment_rental_end": "2026-10-17 16:00:00"}]
        for target in (cl.with_user(accountant), cl.sudo()):
            for values in changes:
                with self.subTest(sudo=target.env.su, values=values), \
                        self.assertRaisesRegex(UserError, "even after bill cancellation"), \
                        self.env.cr.savepoint():
                    target.write(values)
        self.assertEqual(cl.price_subtotal, 120)
        self.assertEqual(cl.equipment_rental_start, fields.Datetime.to_datetime("2026-10-17 08:00:00"))
        self.assertEqual(cl.equipment_rental_end, fields.Datetime.to_datetime("2026-10-17 12:00:00"))
        self.assertEqual(cl.equipment_rental_hours, 4)
        action = cl.with_user(accountant).action_create_equipment_one_off_bill()
        replacement = self.env["account.move"].browse(action["res_id"])
        self.assertNotEqual(replacement, old)
        self.assertEqual(replacement.amount_untaxed, 120)
        self.assertEqual(replacement.invoice_line_ids.product_id, approved_product)
        self.assertEqual(replacement.invoice_line_ids.product_uom_id, approved_uom)
        self.assertEqual(replacement.invoice_line_ids.quantity, 1)
        self.assertEqual(replacement.invoice_line_ids.discount, 0)
        self.assertEqual(op.bill_ids, old | replacement)
        # Accounting corrections do not amend the approved untaxed package.
        tax = self.env["account.tax"].create({
            "name": "TEST rental VAT 20%", "amount": 20, "type_tax_use": "purchase",
            "company_id": self.company.id,
        })
        replacement.with_user(accountant).write({"ref": "TEST corrected supplier reference"})
        replacement.invoice_line_ids.with_user(accountant).write({"tax_ids": [Command.set(tax.ids)]})
        attachment = self.env["ir.attachment"].with_user(accountant).create({
            "name": "TEST supplier supporting document.txt", "raw": b"TEST only",
            "res_model": "account.move", "res_id": replacement.id,
        })
        self.assertEqual(attachment.res_id, replacement.id)
        self.assertEqual(replacement.ref, "TEST corrected supplier reference")
        self.assertEqual(replacement.amount_untaxed, 120)
        self.assertEqual(replacement.amount_tax, 24)
        replacement.with_user(accountant).action_post()
        self.assertEqual(replacement.state, "posted")

    def test_accounting_administrator_can_recreate_a_cancelled_package_bill(self):
        op = self._execute_package()
        cl = op.contract_ids.contract_line_ids
        op.bill_ids.button_cancel()
        accountant = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "One-off accountant", "login": "oneoff_accountant",
            "email": "oneoff_accountant@example.com",
            "company_id": self.company.id, "company_ids": [Command.set(self.company.ids)],
            "groups_id": [Command.set([self.env.ref("base.group_user").id,
                                       self.env.ref("account.group_account_manager").id])],
        })
        action = cl.with_user(accountant).action_create_equipment_one_off_bill()
        bill = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(bill.amount_untaxed, 120)
        self.assertEqual(bill.state, "draft")
        self.assertIn(bill, op.bill_ids)
        self.assertEqual(set(op.bill_ids.mapped("state")), {"cancel", "draft"})
        self.assertEqual(cl.equipment_origin_operation_id, op)
        self.assertEqual(cl.with_user(accountant).action_create_equipment_one_off_bill()["res_id"], bill.id)

    def test_accountant_cannot_detach_package_then_bill_it_again(self):
        op = self._execute_package()
        bill = op.bill_ids
        cl = bill.invoice_line_ids.contract_line_id
        accountant = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "TEST package accountant", "login": "package_detach_accountant",
            "company_id": self.company.id, "company_ids": [Command.set(self.company.ids)],
            "groups_id": [Command.set([self.env.ref("base.group_user").id,
                                       self.env.ref("account.group_account_manager").id])],
        })
        line = bill.invoice_line_ids.with_user(accountant)
        # Exact audit exploit: detach the rental and leave account 613500, then post.
        with self.assertRaises(UserError), self.env.cr.savepoint():
            line.write({"contract_line_id": False, "account_id": self.acc_expense.id})
            bill.with_user(accountant).action_post()
        self.assertEqual(line.contract_line_id, cl)
        self.assertEqual(line.account_id, self.acc_rent)
        self.assertEqual(cl.with_user(accountant).action_create_equipment_one_off_bill()["res_id"], bill.id)
        self.assertEqual(len(cl._equipment_one_off_bills()), 1)
        bill.with_user(accountant).action_post()
        self.assertEqual(bill.state, "posted")

    def test_package_history_cannot_be_deleted_or_retyped_even_after_cancel(self):
        op = self._execute_package()
        bill = op.bill_ids
        line = bill.invoice_line_ids
        cl = line.contract_line_id
        other = self.env["account.move"].create({
            "move_type": "in_invoice", "partner_id": bill.partner_id.id,
            "company_id": self.company.id, "journal_id": bill.journal_id.id,
        })
        for cancel in (False, True):
            if cancel:
                bill.button_cancel()
            actions = [lambda: line.write({"contract_line_id": False}),
                       lambda: line.write({"move_id": other.id}),
                       lambda: line.write({"display_type": "line_note"}),
                       lambda: line.unlink(), lambda: bill.unlink(),
                       lambda: bill.write({"invoice_line_ids": [Command.clear()]}),
                       lambda: bill.write({"move_type": "in_refund"}),
                       lambda: bill.write({"equipment_operation_ids": [Command.clear()]}),
                       lambda: cl.write({"equipment_billing_mode": "recurring"}),
                       lambda: cl.unlink(), lambda: cl.contract_id.unlink()]
            for action in actions:
                with self.subTest(cancelled=cancel, action=action), self.assertRaises(UserError), self.env.cr.savepoint():
                    action()
        replacement = cl._create_equipment_one_off_bill()
        self.assertEqual(op.bill_ids, bill | replacement)
        replacement.action_post()
        self.assertEqual(op.bill_ids.filtered(lambda move: move.state == "posted"), replacement)
        self.assertEqual(op.bill_ids.filtered(lambda move: move.state == "cancel"), bill)
        replacement.button_cancel()
        third = cl._create_equipment_one_off_bill()
        self.assertEqual(op.bill_ids, bill | replacement | third)
        with self.assertRaises(AccessError):
            cl.write({"equipment_origin_operation_id": False})
        third.button_cancel()
        # Manual replacement and direct line APIs must preserve the same origin.
        manual = third.copy({"equipment_operation_ids": [Command.clear()],
                             "invoice_date": fields.Date.today()})
        self.assertIn(manual, op.bill_ids)
        self.assertEqual(manual.state, "draft")
        manual.action_post()
        self.assertIn(manual, op.bill_ids)
        manual.button_cancel()
        direct = self.env["account.move"].create({
            "move_type": "in_invoice", "partner_id": bill.partner_id.id,
            "company_id": self.company.id, "journal_id": bill.journal_id.id,
        })
        vals = cl._prepare_invoice_line()
        vals["move_id"] = direct.id
        self.env["account.move.line"].create(vals)
        self.assertIn(direct, op.bill_ids)

    def test_separate_delivery_collection_and_insurance_fees_total_295(self):
        op = self._execute_package()
        fee = self.env["product.product"].create({
            "name": "TEST ancillary rental fees", "type": "service",
            "property_account_expense_id": self.acc_expense.id,
            "supplier_taxes_id": [Command.clear()],
        })
        op.bill_ids.write({"invoice_line_ids": [Command.create({
            "name": label, "product_id": fee.id, "quantity": 1,
            "price_unit": amount, "account_id": self.acc_expense.id,
            "tax_ids": [Command.clear()],
        }) for label, amount in (("Delivery", 80), ("Collection", 80), ("Insurance", 15))]})
        self.assertEqual(op.bill_ids.amount_untaxed, 295)
        self.assertEqual(len(op.bill_ids.invoice_line_ids.filtered("contract_line_id")), 1)
        op.bill_ids.action_post()
        self.assertFalse(op.bill_ids.invoice_line_ids.equipment_ids)

    def test_one_off_labels_are_loaded_in_three_languages(self):
        for lang, title, choice in (("en_US", "Rental Billing", "One-off Package"),
                                    ("fr_FR", "Facturation de la location", "Forfait unique"),
                                    ("fa_IR", "صورتحساب اجاره", "مبلغ ثابت یک‌باره")):
            with self.subTest(lang=lang):
                field = self.env["equipment.operation"].with_context(lang=lang).fields_get(
                    ["rental_billing_mode"])["rental_billing_mode"]
                self.assertEqual(field["string"], title)
                self.assertEqual(dict(field["selection"])["one_off"], choice)

    def test_full_discount_cannot_turn_a_paid_package_into_a_zero_bill(self):
        op = self._execute_package()
        old = op.bill_ids
        cl = op.contract_ids.contract_line_ids
        old.button_cancel()
        with self.assertRaises(UserError):
            cl.write({"discount": 100})
        self.assertEqual(cl.price_subtotal, 120)
        manual = old.copy()
        manual.invoice_line_ids.discount = 100
        with self.assertRaisesRegex(UserError, "package amount"):
            manual.action_post()

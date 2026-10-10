"""Phase 2f: accounting treatment frozen in the approval (point 10, A2, correction 2)
and approver separated from the operator (point 11, A3, D8),
docs/phase2f/PLAN.md §3 and §4."""
import base64
from contextlib import contextmanager

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, tagged

from .common import EquipmentCommon

PDF = base64.b64encode(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF")


@tagged("post_install", "-at_install")
class TestPhase2fTreatment(EquipmentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.grinder = cls._product("Grinder", cls.categ_tools, storable=True)
        # a fixed-asset account carries the asset profile, as on artdubati_test
        cls.acc_asset.asset_profile_id = cls.profile

        def account(code):
            return env["account.account"].search(
                [("code", "=", code), ("company_ids", "in", cls.company.id)], limit=1)

        cls.acc_other = account("606800")

        def new_account(code, name):
            return env["account.account"].create({
                "code": code, "name": name, "account_type": "asset_current",
                "company_ids": [Command.set(cls.company.ids)]})

        cls.acc_stock_in = new_account("TSTIN", "Stock input (test)")
        cls.acc_stock_val = new_account("TSTVAL", "Stock valuation (test)")

    def _draft_purchase_op(self, product, qty=1, **vals):
        po = self._order(product, qty)
        pol = po.order_line
        op = self._operation("receipt", receipt_branch="purchase", partner_id=po.partner_id.id,
                             purchase_mode="existing", purchase_id=po.id,
                             lines=[dict(product_id=product.id, purchase_line_id=pol.id,
                                         lot_name="T-%s" % product.id)], **vals)
        return po, op

    def _real_bill_account(self, po):
        po.action_create_invoice()
        return po.invoice_ids[:1].invoice_line_ids[:1].account_id

    def test_plain_account_matches_real_bill(self):
        po, op = self._draft_purchase_op(self.grinder)
        line = op.line_ids
        self.assertEqual(line._treatment()["kind"], "account")
        self.assertIn(self.acc_expense.code, line.accounting_treatment)
        self.assertIn("current configuration", line.accounting_treatment)
        self.assertTrue(line.needs_no_asset_confirmation)
        self.assertEqual(line._planned_bill_account()[0], self._real_bill_account(po))

    def test_fiscal_position_maps_the_account(self):
        fpos = self.env["account.fiscal.position"].create({
            "name": "Map tools", "company_id": self.company.id,
            "account_ids": [Command.create({"account_src_id": self.acc_expense.id,
                                            "account_dest_id": self.acc_other.id})],
        })
        po, op = self._draft_purchase_op(self.grinder)
        po.fiscal_position_id = fpos
        line = op.line_ids
        self.assertEqual(line._planned_bill_account()[0], self.acc_other)
        self.assertEqual(self._real_bill_account(po), self.acc_other)

    def test_automated_valuation_gives_the_stock_input_account(self):
        self.company.anglo_saxon_accounting = True
        categ = self.env["product.category"].create({
            "name": "Auto tools", "property_cost_method": "average",
            "property_valuation": "real_time",
            "property_account_expense_categ_id": self.acc_expense.id,
            "property_stock_account_input_categ_id": self.acc_stock_in.id,
            "property_stock_account_output_categ_id": self.acc_stock_in.id,
            "property_stock_valuation_account_id": self.acc_stock_val.id,
        })
        product = self._product("Auto grinder", categ, storable=True)
        po, op = self._draft_purchase_op(product)
        line = op.line_ids
        self.assertEqual(line._treatment()["kind"], "stock")
        account = line._planned_bill_account()[0]
        self.assertEqual(account, self._real_bill_account(po))
        self.assertIn(account.code, line.accounting_treatment)

    def test_asset_profile_account_creates_asset_and_needs_no_confirmation(self):
        po, op = self._draft_purchase_op(self.drill)
        line = op.line_ids
        self.assertEqual(line._treatment()["kind"], "asset")
        self.assertFalse(line.needs_no_asset_confirmation)
        real = self._real_bill_account(po)
        self.assertEqual(line._planned_bill_account()[0], real)
        self.assertEqual(real, self.acc_asset)

    def test_new_order_uses_the_partner_fiscal_position(self):
        fpos = self.env["account.fiscal.position"].create({
            "name": "Map tools", "company_id": self.company.id, "auto_apply": False,
            "account_ids": [Command.create({"account_src_id": self.acc_expense.id,
                                            "account_dest_id": self.acc_other.id})],
        })
        self.vendor.with_company(self.company).property_account_position_id = fpos
        op = self._operation("receipt", receipt_branch="purchase", partner_id=self.vendor.id,
                             purchase_mode="create", bill_mode="none",
                             lines=[dict(product_id=self.grinder.id, lot_name="NEW-1",
                                         price_unit=80.0)])
        self.assertEqual(op.line_ids._planned_bill_account()[0], self.acc_other)
        op.with_user(self.user_both).action_execute()
        order = op.purchase_created_id
        self.assertEqual(order.fiscal_position_id, fpos)
        self.assertEqual(self._real_bill_account(order), self.acc_other)

    def test_confirmation_only_for_company_property(self):
        _po, op = self._draft_purchase_op(self.grinder)
        op.line_ids.no_asset_confirmed = False
        with self.assertRaisesRegex(ValidationError, "fixed asset"):
            op.action_execute()
        op.line_ids.no_asset_confirmed = True
        op.action_execute()
        self.assertEqual(op.state, "done")
        acquisition = self._operation(
            "receipt", receipt_branch="acquisition", acquisition_nature="gift",
            partner_id=self.lender.id,
            lines=[dict(product_id=self.drill.id, lot_name="GIFT-T", unit_value=10.0,
                        no_asset_confirmed=False)])
        self.assertTrue(acquisition.line_ids.needs_no_asset_confirmation)
        self.assertIn("manually", acquisition.line_ids.accounting_treatment)
        borrowed = self._operation(
            "receipt", receipt_branch="borrowed", partner_id=self.lender.id,
            lines=[dict(product_id=self.grinder.id, lot_name="LOAN-T", no_asset_confirmed=False)])
        self.assertFalse(borrowed.line_ids.needs_no_asset_confirmation)
        self.assertFalse(borrowed.line_ids.accounting_treatment)

    def _approved_op(self):
        po = self._order(self.grinder, 1)
        attachment = self.env["ir.attachment"].with_user(self.user_operator).create(
            {"name": "bill.pdf", "datas": PDF, "mimetype": "application/pdf"})
        op = self._operation("receipt", user=self.user_operator, receipt_branch="purchase",
                             partner_id=po.partner_id.id, purchase_mode="existing",
                             purchase_id=po.id, bill_mode="create", bill_ref="F-1",
                             bill_date=fields.Date.today(),
                             bill_attachment_ids=[Command.set(attachment.ids)],
                             lines=[dict(product_id=self.grinder.id, lot_name="APP-%s" % po.id,
                                         purchase_line_id=po.order_line.id)])
        op.with_user(self.user_operator).action_submit()
        op.with_user(self.user_approver).action_approve()
        self.assertEqual(op.state, "approved")
        return po, op

    def test_approval_cancelled_when_the_treatment_changes(self):
        def category_account(po, op):
            self.categ_tools.property_account_expense_categ_id = self.acc_other

        def account_profile(po, op):
            profile = self.profile.copy({"name": "Tools as assets (test)",
                                         "account_asset_id": self.acc_expense.id})
            self.acc_expense.asset_profile_id = profile

        def fiscal_position(po, op):
            po.fiscal_position_id = self.env["account.fiscal.position"].create({
                "name": "FP", "company_id": self.company.id,
                "account_ids": [Command.create({"account_src_id": self.acc_expense.id,
                                                "account_dest_id": self.acc_other.id})]})

        def valuation(po, op):
            self.categ_tools.write({
                "property_stock_account_input_categ_id": self.acc_stock_in.id,
                "property_stock_account_output_categ_id": self.acc_stock_in.id,
                "property_stock_valuation_account_id": self.acc_stock_val.id,
                "property_valuation": "real_time",
            })

        for change in (category_account, account_profile, fiscal_position, valuation):
            with self.subTest(change=change.__name__), self.env.cr.savepoint() as sp:
                po, op = self._approved_op()
                change(po, op)
                op.with_user(self.user_operator).action_execute()  # no error: kept
                self.assertEqual(op.state, "draft")
                self.assertIn("treatment", op.message_ids[:1].body)
                sp.rollback()

    def test_unchanged_treatment_executes(self):
        _po, op = self._approved_op()
        op.with_user(self.user_operator).action_execute()
        self.assertEqual(op.state, "done")

    def test_profile_name_only_for_users_who_can_read_it(self):
        _po, op = self._draft_purchase_op(self.drill)
        line = op.line_ids
        self.assertIn(self.profile.name, line.accounting_treatment)  # administrator
        text = line.with_user(self.user_operator).accounting_treatment
        self.assertIn(self.acc_asset.code, text)
        self.assertNotIn(self.profile.name, text)


@tagged("post_install", "-at_install")
class TestPhase2fApprover(EquipmentCommon):

    def _submitted(self):
        po = self._order(self.drill, 1)
        attachment = self.env["ir.attachment"].with_user(self.user_operator).create(
            {"name": "bill.pdf", "datas": PDF, "mimetype": "application/pdf"})
        op = self._operation("receipt", user=self.user_operator, receipt_branch="purchase",
                             partner_id=po.partner_id.id, purchase_mode="existing",
                             purchase_id=po.id, bill_mode="create", bill_ref="F-2",
                             bill_date=fields.Date.today(),
                             bill_attachment_ids=[Command.set(attachment.ids)],
                             lines=[dict(product_id=self.drill.id, lot_name="SCOPE-%s" % po.id,
                                         purchase_line_id=po.order_line.id)])
        op.with_user(self.user_operator).action_submit()
        return po, op

    def test_approver_reads_only_and_approves(self):
        _po, op = self._submitted()
        as_approver = op.with_user(self.user_approver)
        with self.assertRaises(AccessError):
            as_approver.write({"note": "changed by the approver"})
        as_approver.message_post(body="Checked the bill")
        as_approver.action_approve()
        self.assertEqual(op.state, "approved")
        with self.assertRaises(AccessError):
            op.with_user(self.user_operator).action_approve()
        op.with_user(self.user_operator).action_execute()
        self.assertEqual(op.state, "done")

    def test_both_roles(self):
        _po, op = self._submitted()
        op.with_user(self.user_both).action_approve()
        op.with_user(self.user_both).action_execute()
        self.assertEqual(op.state, "done")

    def test_approver_scope_limited_to_referenced_documents(self):
        po, op = self._submitted()
        op.with_user(self.user_approver).action_approve()
        op.with_user(self.user_operator).action_execute()
        other_po = self._order(self.drill, 1)
        other_picking = other_po.picking_ids
        Lot = self.env["stock.lot"]
        other_lot = Lot.create({"name": "NOT-REF", "product_id": self.drill.id,
                                "company_id": self.company.id})
        approver = self.user_approver
        checks = [
            ("purchase.order", po, other_po),
            ("purchase.order.line", po.order_line, other_po.order_line),
            ("stock.picking", op.picking_ids, other_picking),
            ("stock.move", op.picking_ids.move_ids, other_picking.move_ids),
            ("stock.lot", op.line_ids.lot_id, other_lot),
            ("account.move", op.bill_ids, False),
            ("account.move.line", op.bill_ids.line_ids, False),
            ("stock.move.line", op.picking_ids.move_line_ids, self._free_move_line()),
            # journals: only those of the referenced bills (D8, audit of 6cdc8b9)
            ("account.journal", op.bill_ids.journal_id,
             self.env["account.journal"].create({"name": "Unrelated (test)", "code": "UNRT",
                                                 "type": "general",
                                                 "company_id": self.company.id})),
        ]
        for model, referenced, other in checks:
            with self.subTest(model=model):
                self.assertTrue(referenced)
                Model = self.env[model].with_user(approver)
                self.assertEqual(Model.search([("id", "in", referenced.ids)]).ids, referenced.ids)
                if other:
                    self.assertFalse(Model.search([("id", "in", other.ids)]))
                    with self.assertRaises(AccessError):
                        other.with_user(approver).check_access("read")
        # other profiles keep their full scope
        self.assertTrue(self.env["stock.picking"].with_user(self.user_stock).search(
            [("id", "=", other_picking.id)]))
        self.assertTrue(self.env["purchase.order"].with_user(self.user_both).search(
            [("id", "=", other_po.id)]))

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

    def _free_move_line(self):
        """A move line no equipment operation refers to."""
        return self.env["stock.move.line"].create(self._move_line_values())

    def _move_line_values(self):
        if not getattr(self, "_free_move", None):
            product = self._product("Cement bag (test)", self.categ_tools, storable=True)
            self._free_move = self.env["stock.move"].create({
                "name": "Receipt (test)", "product_id": product.id, "product_uom_qty": 10.0,
                "product_uom": product.uom_id.id,
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": self.stock.id, "company_id": self.company.id})
            self._free_move._action_confirm()
        move = self._free_move
        return {"product_id": move.product_id.id, "location_id": move.location_id.id,
                "location_dest_id": move.location_dest_id.id, "quantity": 1.0,
                "product_uom_id": move.product_uom.id, "company_id": self.company.id,
                "move_id": move.id}

    def test_move_lines_approver_alone_reads_linked_writes_nothing(self):
        """Standard stock gives every internal user read, write, create and delete on
        all move lines (access_stock_move_line_all); the approver alone reads those of
        the operations and writes none (audit of 888d229)."""
        _po, op = self._submitted()
        op.with_user(self.user_approver).action_approve()
        op.with_user(self.user_operator).action_execute()
        linked = op.picking_ids.move_line_ids
        free = self._free_move_line()
        self.assertTrue(linked)
        MoveLine = self.env["stock.move.line"].with_user(self.user_approver)
        self.assertEqual(MoveLine.search([("id", "in", (linked | free).ids)]), linked)
        linked.with_user(self.user_approver).read(["quantity", "lot_id"])
        with self.assertRaises(AccessError):
            free.with_user(self.user_approver).read(["quantity"])
        # refused by the write rule itself, not by the read scope or a business check
        orphan = dict(self._move_line_values(), move_id=False)
        with self._denied_by_move_line_rule("create"):
            MoveLine.create(orphan)
        with self.assertRaises(AccessError):
            MoveLine.create(self._move_line_values())
        # lot_name: a field stock's write() does not act on, so the rule decides
        with self._denied_by_move_line_rule("write"):
            linked.with_user(self.user_approver).write({"lot_name": "CHANGED"})
        # quantity of a done line: also refused (stock first posts on the transfer)
        with self.assertRaises(AccessError):
            linked.with_user(self.user_approver).write({"quantity": 5.0})
        with self._denied_by_move_line_rule("unlink"):
            linked.with_user(self.user_approver).unlink()
        with self.assertRaises(AccessError):
            free.with_user(self.user_approver).write({"quantity": 5.0})
        with self.assertRaises(AccessError):
            free.with_user(self.user_approver).unlink()
        self.assertTrue((linked | free).exists() == linked | free)
        self.assertEqual(free.quantity, 1.0)
        self.assertEqual(linked.quantity, 1.0)

    def test_move_lines_standard_rights_kept_with_inventory(self):
        """Approver with Inventory / User (directly or through the operator group) and
        an ordinary Inventory user keep the standard rights on every move line."""
        approver_stock = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "eq_approver_stock", "login": "eq_approver_stock",
            "company_id": self.company.id, "company_ids": [Command.set(self.company.ids)],
            "groups_id": [Command.set([
                self.env.ref("base.group_user").id, self.env.ref("stock.group_stock_user").id,
                self.env.ref("maintenance_shareholder_equipment.group_equipment_approver").id])],
        })
        free = self._free_move_line()
        for user in (approver_stock, self.user_both, self.user_stock):
            with self.subTest(user=user.login):
                MoveLine = self.env["stock.move.line"].with_user(user)
                self.assertEqual(MoveLine.search([("id", "=", free.id)]), free)
                line = MoveLine.create(self._move_line_values())
                line.write({"quantity": 2.0})
                self.assertEqual(line.quantity, 2.0)
                line.unlink()
                self.assertFalse(line.exists())

    def test_contract_scope(self):
        op = self._operation("receipt", receipt_branch="borrowed", partner_id=self.lender.id,
                             contract_start=fields.Date.today(), open_ended=True,
                             lines=[dict(product_id=self.drill.id, lot_name="LOAN-S",
                                         replacement_value=500.0,
                                         replacement_value_date=fields.Date.today())])
        op.with_user(self.user_both).action_execute()
        contract = op.contract_ids
        other = self.env["contract.contract"].create({
            "name": "Unrelated", "partner_id": self.lender.id, "contract_type": "purchase",
            "company_id": self.company.id})
        Contract = self.env["contract.contract"].with_user(self.user_approver)
        self.assertEqual(Contract.search([("id", "in", (contract | other).ids)]), contract)
        Line = self.env["contract.line"].with_user(self.user_approver)
        self.assertEqual(Line.search([("contract_id", "=", contract.id)]).ids,
                         contract.contract_line_ids.ids)

    def test_unreadable_reference_blocks_every_step(self):
        """A record the real user cannot read stops submit, approve and execute."""
        _po, op = self._submitted()
        rule = self.env["ir.rule"].create({
            "name": "hide the destination (test)",
            "model_id": self.env.ref("stock.model_stock_location").id,
            "domain_force": "[('id', '!=', %s)]" % self.stock.id,
            "groups": [Command.set(self.env.ref(
                "maintenance_shareholder_equipment.group_equipment_approver").ids)],
        })
        with self.assertRaises(AccessError):
            op.with_user(self.user_approver).action_approve()
        rule.unlink()
        op.with_user(self.user_approver).action_approve()
        self.env["ir.rule"].create({
            "name": "hide the destination (test, operator)",
            "model_id": self.env.ref("stock.model_stock_location").id,
            "domain_force": "[('id', '!=', %s)]" % self.stock.id,
            "groups": [Command.set(self.env.ref(
                "maintenance_shareholder_equipment.group_equipment_operator").ids)],
        })
        with self.assertRaises(AccessError):
            op.with_user(self.user_operator).action_execute()

    def test_repair_and_sale_orders_empty_scope(self):
        """First phase 4 deployment attempt (10/10/2026): Repair and Sales add repair and
        sale order counters to the transfer and lot forms. The approver alone reads
        these models with an empty scope: no record, never a write; users with a real
        right keep their scope (an approver who is also a salesman included)."""
        partner = self.env["res.partner"].create({"name": "Customer (scope test)"})
        repair = self.env["repair.order"].create({
            "product_id": self.drill.id, "partner_id": partner.id,
            "company_id": self.company.id})
        sale = self.env["sale.order"].create({
            "partner_id": partner.id, "company_id": self.company.id,
            "order_line": [Command.create({"product_id": self.drill.id,
                                           "product_uom_qty": 1})]})
        records = {"repair.order": repair, "sale.order": sale,
                   "sale.order.line": sale.order_line}
        for model, record in records.items():
            with self.subTest(model=model, user="approver alone"):
                as_approver = self.env[model].with_user(self.user_approver)
                self.assertFalse(as_approver.search([("id", "in", record.ids)]))
                self.assertEqual(as_approver.search_count([]), 0)
                with self.assertRaises(AccessError):
                    record.with_user(self.user_approver).check_access("read")
                with self.assertRaises(AccessError):
                    record.with_user(self.user_approver).read(["display_name"])
                with self.assertRaises(AccessError):
                    record.with_user(self.user_approver).write({})
                with self.assertRaises(AccessError):
                    record.with_user(self.user_approver).unlink()
                with self.assertRaises(AccessError):
                    as_approver.check_access("create")
        salesman_approver = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "eq_approver_sales", "login": "eq_approver_sales",
            "company_id": self.company.id, "company_ids": [Command.set(self.company.ids)],
            "groups_id": [Command.set([
                self.env.ref("sales_team.group_sale_salesman_all_leads").id,
                self.env.ref("maintenance_shareholder_equipment.group_equipment_approver").id])],
        })
        for user, model in ((self.user_stock, "repair.order"),
                            (salesman_approver, "sale.order"),
                            (salesman_approver, "sale.order.line")):
            with self.subTest(model=model, user=user.login):
                record = records[model]
                self.assertEqual(self.env[model].with_user(user).search(
                    [("id", "in", record.ids)]), record)
                record.with_user(user).check_access("read")
        self.assertTrue(repair.exists() and sale.exists())

    def test_investor_without_inventory_rights_has_no_access(self):
        investor = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Investor", "login": "eq_investor", "company_id": self.company.id,
            "company_ids": [Command.set(self.company.ids)],
            "groups_id": [Command.set(self.env.ref("base.group_user").ids)],
        })
        _po, op = self._submitted()
        with self.assertRaises(AccessError):
            op.with_user(investor).check_access("read")
        with self.assertRaises(AccessError):
            self.env["equipment.operation"].with_user(investor).create(
                {"operation_type": "receipt", "company_id": self.company.id})


@tagged("post_install", "-at_install")
class TestPhase2fTours(EquipmentCommon, HttpCase):
    """Real interface: an approver alone opens and approves a complete purchase
    receipt (order, bill to create, lines with responsible and treatment); an operator
    alone opens it without the approve button (audit A3)."""

    def _complete_operation(self):
        po = self._order(self.drill, 1)
        attachment = self.env["ir.attachment"].with_user(self.user_operator).create(
            {"name": "bill.pdf", "datas": PDF, "mimetype": "application/pdf"})
        op = self._operation("receipt", user=self.user_operator, receipt_branch="purchase",
                             partner_id=po.partner_id.id, purchase_mode="existing",
                             purchase_id=po.id, bill_mode="create", bill_ref="F-T",
                             bill_date=fields.Date.today(),
                             bill_attachment_ids=[Command.set(attachment.ids)],
                             lines=[dict(product_id=self.drill.id, lot_name="TOUR-%s" % po.id,
                                         purchase_line_id=po.order_line.id)])
        op.with_user(self.user_operator).action_submit()
        return op

    def _url(self, op):
        return "/odoo/action-maintenance_shareholder_equipment.action_equipment_operation/%s" % op.id

    def test_approver_alone_opens_and_approves(self):
        self.user_approver.password = "eq_approver"  # start_tour logs in with login = password
        op = self._complete_operation()
        self.start_tour(self._url(op), "equipment_operation_approver_tour",
                        login="eq_approver")
        self.assertEqual(op.state, "approved")
        self.assertEqual(op.approver_id, self.user_approver)

    def test_operator_alone_cannot_approve(self):
        self.user_operator.password = "eq_operator"
        op = self._complete_operation()
        self.start_tour(self._url(op), "equipment_operation_operator_tour",
                        login="eq_operator")
        self.assertEqual(op.state, "to_approve")

    def test_approver_alone_opens_every_document_after_execution(self):
        """Order, receipt with its move lines and serial number, lot, bill with its
        lines and contract with its lines: each form opens for the approver alone."""
        self.user_approver.password = "eq_approver"
        # « Lots & Serial Numbers » is on in artdubati_test (phase 0): every internal
        # user sees the serial column of the move lines
        self.env.ref("base.group_user").implied_ids |= self.env.ref("stock.group_production_lot")
        op = self._complete_operation()
        op.with_user(self.user_approver).action_approve()
        op.with_user(self.user_operator).action_execute()
        self.assertEqual(op.state, "done")
        loan = self._operation("receipt", receipt_branch="borrowed", partner_id=self.lender.id,
                               contract_start=fields.Date.today(), open_ended=True,
                               lines=[dict(product_id=self.drill.id, lot_name="TOUR-LOAN",
                                           replacement_value=300.0,
                                           replacement_value_date=fields.Date.today())])
        loan.with_user(self.user_both).action_execute()
        documents = [
            ("purchase.order", op.purchase_id, "equipment_document_with_lines_tour"),
            ("stock.picking", op.picking_ids, "equipment_receipt_details_tour"),
            ("stock.lot", op.line_ids.lot_id, "equipment_document_tour"),
            ("account.move", op.bill_ids, "equipment_document_with_lines_tour"),
            ("contract.contract", loan.contract_ids, "equipment_document_with_lines_tour"),
        ]
        for model, record, tour in documents:
            with self.subTest(model=model):
                self.assertEqual(len(record), 1)
                self.start_tour("/odoo/%s/%s" % (model, record.id), tour, login="eq_approver")

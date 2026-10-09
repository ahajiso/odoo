from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import EquipmentCommon


@tagged("post_install", "-at_install")
class TestEquipment(EquipmentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group_user = cls.env.ref("base.group_user")
        equipment_manager = cls.env.ref("maintenance.group_equipment_manager")
        cls.maintenance_user = cls.env["res.users"].create({
            "name": "Maintenance user", "login": "ladb_maint_user", "email": "maint@example.com",
            "company_id": cls.company.id, "company_ids": [Command.set(cls.company.ids)],
            "groups_id": [Command.set((group_user | equipment_manager).ids)],
        })
        cls.ownership_manager = cls.env["res.users"].create({
            "name": "Ownership manager", "login": "ladb_owner_mgr", "email": "owner@example.com",
            "company_id": cls.company.id, "company_ids": [Command.set(cls.company.ids)],
            "groups_id": [Command.set((group_user | cls.env.ref(
                "maintenance_shareholder_equipment.group_equipment_ownership_manager")).ids)],
        })

    def _equipment(self, **vals):
        return self.env["maintenance.equipment"].create(
            dict({"name": "Eq", "owner_user_id": self.user_responsible.id}, **vals))

    # -------------------------------------------------------------- protection

    def test_defaults(self):
        equipment = self._equipment()
        self.assertEqual(equipment.ownership_status, "owned")
        self.assertEqual(equipment.owner_partner_id, self.company.partner_id)
        self.assertEqual(equipment.integration_state, "draft")

    def test_protected_fields_refused_by_api(self):
        equipment = self._equipment().with_user(self.maintenance_user)
        for vals in ({"ownership_status": "rented"}, {"owner_partner_id": self.lender.id},
                     {"integration_state": "done"}):
            with self.assertRaises(AccessError):
                equipment.write(vals)
        with self.assertRaises(AccessError):
            equipment.with_user(self.ownership_manager).write({"ownership_status": "borrowed"})
        with self.assertRaises(AccessError):
            self.env["maintenance.equipment"].with_user(self.maintenance_user).create(
                {"name": "x", "ownership_status": "borrowed", "owner_partner_id": self.lender.id}
            )

    def test_set_ownership_requires_manager_and_reason(self):
        equipment = self._equipment()
        with self.assertRaises(AccessError):
            equipment.with_user(self.maintenance_user)._set_ownership("borrowed", self.lender, "x")
        with self.assertRaises(ValidationError):
            equipment.with_user(self.ownership_manager)._set_ownership("borrowed", self.lender, "")
        equipment.with_user(self.ownership_manager)._set_ownership(
            "borrowed", self.lender, "Lent by the shareholder"
        )
        self.assertEqual(equipment.ownership_status, "borrowed")
        self.assertEqual(equipment.owner_partner_id, self.lender)
        self.assertIn("Lent by the shareholder", equipment.message_ids[:1].body)

    def test_correction_wizard(self):
        equipment = self._equipment()
        wizard = self.env["equipment.ownership.correction"].with_user(self.ownership_manager).create({
            "equipment_id": equipment.id, "ownership_status": "rented",
            "owner_partner_id": self.lender.id, "reason": "Rental contract signed",
        })
        wizard.action_apply()
        self.assertEqual(equipment.ownership_status, "rented")

    def test_owner_must_match_status(self):
        equipment = self._equipment()
        with self.assertRaises(ValidationError):
            equipment.sudo().write({"ownership_status": "borrowed"})  # owner still the company
        with self.assertRaises(ValidationError):
            equipment.sudo().write({"owner_partner_id": self.lender.id})  # owned by a third party

    # -------------------------------------------------------------- integration

    def test_finalize_requires_complete_information(self):
        equipment = self._equipment(product_id=self.small_tool.id)
        with self.assertRaises(ValidationError):
            equipment.action_finalize_integration()
        equipment.write({
            "current_location_id": self.stock.id,
            "warranty_status": "no_warranty",
            "insurance_status": "not_applicable",
        })
        equipment.action_finalize_integration()
        self.assertEqual(equipment.integration_state, "done")
        with self.assertRaises(ValidationError):
            equipment.warranty_status = False

    def test_borrowed_needs_replacement_value(self):
        equipment = self._equipment(current_location_id=self.stock.id,
                                    warranty_status="no_warranty", insurance_status="insured")
        equipment.sudo()._set_ownership("borrowed", self.lender, "loan")
        with self.assertRaises(ValidationError):
            equipment.action_finalize_integration()
        equipment.write({"replacement_value": 900.0,
                         "replacement_value_date": fields.Date.today()})
        equipment.action_finalize_integration()

    def test_category_defaults_applied_at_creation(self):
        self.categ_tools.write({"default_warranty_status": "not_applicable",
                                "default_insurance_status": "not_insured"})
        equipment = self._equipment(product_id=self.small_tool.id)
        self.assertEqual(equipment.warranty_status, "not_applicable")
        self.assertEqual(equipment.insurance_status, "not_insured")

    # ------------------------------------------------------------------ lots

    def test_lot_rules(self):
        po = self._order(self.drill, 2)
        first, second = self._receive(po, ["L1", "L2"])
        with self.assertRaises(ValidationError):
            first.current_location_id = self.stock  # lot and location are exclusive
        with self.assertRaises(Exception):  # unique(stock_lot_id)
            with self.cr.savepoint():
                second.stock_lot_id = first.stock_lot_id
                self.env.flush_all()
        with self.assertRaises(ValidationError):
            first.product_id = self.small_tool  # lot of another product

    # ----------------------------------------------------- consistency job

    def test_ownership_job_is_idempotent(self):
        po = self._order(self.drill, 1)
        equipment = self._receive(po, ["J1"])
        equipment.write({"warranty_status": "no_warranty", "insurance_status": "insured"})
        equipment.sudo().write({"integration_state": "done"})
        # Stock says company, equipment says borrowed: inconsistent.
        equipment.sudo().write({"ownership_status": "borrowed", "owner_partner_id": self.lender.id,
                                "replacement_value": 1.0,
                                "replacement_value_date": fields.Date.today()})
        Equipment = self.env["maintenance.equipment"]
        Equipment._cron_check_ownership_consistency()
        Equipment._cron_check_ownership_consistency()
        activity_type = self.env.ref("maintenance_shareholder_equipment.mail_activity_ownership_check")
        self.assertEqual(
            len(equipment.activity_ids.filtered(lambda a: a.activity_type_id == activity_type)), 1
        )


@tagged("post_install", "-at_install")
class TestStockOwner(EquipmentCommon):

    def _receive_with_owner(self, product, serial, owner):
        picking = self.env["stock.picking"].create({
            "picking_type_id": self.warehouse.in_type_id.id,
            "location_id": self.env.ref("stock.stock_location_suppliers").id,
            "location_dest_id": self.stock.id,
            "owner_id": owner.id,
            "move_ids": [Command.create({
                "name": product.name, "product_id": product.id, "product_uom_qty": 1,
                "product_uom": product.uom_id.id,
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": self.stock.id,
            })],
        })
        picking.action_confirm()
        move = picking.move_ids
        move.move_line_ids.unlink()
        self.env["stock.move.line"].create({
            "move_id": move.id, "picking_id": picking.id, "product_id": product.id,
            "lot_name": serial or False, "quantity": 1, "product_uom_id": product.uom_id.id,
            "owner_id": owner.id, "location_id": move.location_id.id,
            "location_dest_id": move.location_dest_id.id,
        })
        return picking

    def test_consumable_with_third_party_owner_refused(self):
        consumable = self.env["product.product"].create(
            {"name": "Screws", "type": "consu", "is_storable": True}
        )
        picking = self._receive_with_owner(consumable, None, self.lender)
        self._as_running_operation(picking)
        with self.assertRaises(ValidationError):
            picking.button_validate()

    def test_serial_of_borrowed_equipment_accepted(self):
        lot = self.env["stock.lot"].create({"name": "B1", "product_id": self.drill.id,
                                            "company_id": self.company.id})
        equipment = self.env["maintenance.equipment"].sudo().create({
            "name": "Borrowed drill", "product_id": self.drill.id, "stock_lot_id": lot.id,
            "ownership_status": "borrowed", "owner_partner_id": self.lender.id,
            "company_id": self.company.id,
        })
        picking = self._receive_with_owner(self.drill, "B1", self.lender)
        self._as_running_operation(picking)
        picking.button_validate()
        self.assertEqual(picking.state, "done")
        self.assertTrue(equipment._check_stock_owner_consistency())

    def test_serial_of_owned_equipment_refused_with_owner(self):
        lot = self.env["stock.lot"].create({"name": "O1", "product_id": self.drill.id,
                                            "company_id": self.company.id})
        self.env["maintenance.equipment"].create({
            "name": "Owned drill", "product_id": self.drill.id, "stock_lot_id": lot.id,
        })
        picking = self._receive_with_owner(self.drill, "O1", self.lender)
        self._as_running_operation(picking)
        with self.assertRaises(ValidationError):
            picking.button_validate()


@tagged("post_install", "-at_install")
class TestSetup(EquipmentCommon):

    def test_fixed_asset_category_checks(self):
        with self.assertRaises(ValidationError):
            self.env["product.category"].create({
                "name": "Bad", "property_valuation": "real_time",
                "property_account_expense_categ_id": self.acc_asset.id,
                "is_fixed_asset_stock": True,
            })
        with self.assertRaises(ValidationError):
            self.env["product.category"].create({
                "name": "Bad account", "property_valuation": "manual_periodic",
                "property_account_expense_categ_id": self.acc_expense.id,
                "is_fixed_asset_stock": True,
            })

    def test_storable_equipment_needs_serial(self):
        with self.assertRaises(ValidationError):
            self.env["product.product"].create({
                "name": "Untracked saw", "type": "consu", "is_storable": True,
                "maintenance_ok": True, "tracking": "none",
            })

    def test_lent_out_location_needs_return(self):
        Location = self.env["stock.location"]
        with self.assertRaisesRegex(ValidationError, "return location is required"):
            Location.create(self._lent_out_vals(
                name="At customer", location_id=self.warehouse.view_location_id.id,
                return_location_id=False))
        archived = Location.create({"name": "Old", "usage": "internal", "active": False,
                                    "location_id": self.warehouse.view_location_id.id,
                                    "place_type": "physical"})
        archived.place_type = "lent_out"  # archived: not checked
        Location.create(self._lent_out_vals(
            name="At customer", location_id=self.warehouse.view_location_id.id))


@tagged("post_install", "-at_install")
class TestContractAndRent(EquipmentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.equipment = cls.env["maintenance.equipment"].create(
            {"name": "Rented lift", "current_location_id": cls.stock.id}
        )

    def _contract(self, ctype, partner, lines):
        return self.env["contract.contract"].create({
            "name": "Contract", "partner_id": partner.id, "contract_type": ctype,
            "line_recurrence": True, "company_id": self.company.id,
            "contract_line_ids": [Command.create(dict({
                "product_id": self.rent_service.id, "name": "Line", "quantity": 1,
                "price_unit": 300.0, "recurring_rule_type": "monthly",
                "recurring_interval": 1, "date_start": "2026-01-01",
                "recurring_next_date": "2026-01-01",
            }, **vals)) for vals in lines],
        })

    def test_overlap_refused(self):
        self._contract("purchase", self.lender, [{
            "equipment_id": self.equipment.id, "equipment_nature": "rental",
            "date_end": "2026-06-30"}])
        with self.assertRaises(ValidationError):
            self._contract("purchase", self.lender, [{
                "equipment_id": self.equipment.id, "equipment_nature": "rental",
                "date_start": "2026-06-30", "recurring_next_date": "2026-06-30"}])
        # Next day is fine (closed intervals).
        self._contract("purchase", self.lender, [{
            "equipment_id": self.equipment.id, "equipment_nature": "rental",
            "date_start": "2026-07-01", "recurring_next_date": "2026-07-01"}])

    def test_line_rules(self):
        with self.assertRaises(ValidationError):
            self._contract("sale", self.lender, [{
                "equipment_id": self.equipment.id, "equipment_nature": "insurance"}])
        with self.assertRaises(ValidationError):
            self._contract("purchase", self.lender, [{
                "equipment_id": self.equipment.id, "equipment_nature": "rental",
                "product_id": self.small_tool.id}])
        with self.assertRaises(ValidationError):
            self._contract("purchase", self.lender, [{"equipment_id": self.equipment.id}])

    def test_free_loan_never_invoiced(self):
        contract = self._contract("purchase", self.lender, [{
            "equipment_id": self.equipment.id, "equipment_nature": "loan", "price_unit": 0.0}])
        self.assertFalse(contract.recurring_next_date)
        self.assertFalse(contract.contract_line_ids.create_invoice_visibility)
        for date_ref in ("2026-02-01", "2026-05-01", "2026-12-01"):
            self.env["contract.contract"].cron_recurring_create_invoice(
                date_ref=fields.Date.to_date(date_ref)
            )
        self.assertFalse(contract._get_related_invoices())

    def test_mixed_contract_invoices_only_rental(self):
        other = self.env["maintenance.equipment"].create(
            {"name": "Lent saw", "current_location_id": self.stock.id}
        )
        contract = self._contract("purchase", self.lender, [
            {"equipment_id": self.equipment.id, "equipment_nature": "rental",
             "recurring_next_date": "2026-03-01", "date_start": "2026-03-01"},
            {"equipment_id": other.id, "equipment_nature": "loan", "price_unit": 0.0},
        ])
        rental = contract.contract_line_ids.filtered(lambda ln: ln.equipment_nature == "rental")
        self.assertEqual(contract.recurring_next_date, rental.recurring_next_date)
        contract.recurring_create_invoice()
        invoices = contract._get_related_invoices()
        self.assertEqual(len(invoices), 1)
        self.assertEqual(invoices.invoice_line_ids.contract_line_id, rental)
        self.assertEqual(contract.recurring_next_date, rental.recurring_next_date)

    def test_rent_bill_lock_and_contract_line_check(self):
        contract = self._contract("purchase", self.lender, [{
            "equipment_id": self.equipment.id, "equipment_nature": "rental"}])
        rental = contract.contract_line_ids

        def bill(partner, contract_line):
            return self.env["account.move"].create({
                "move_type": "in_invoice", "partner_id": partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [Command.create({
                    "product_id": self.rent_service.id, "quantity": 1, "price_unit": 300.0,
                    "account_id": self.acc_rent.id, "tax_ids": [Command.clear()],
                    "contract_line_id": contract_line.id if contract_line else False,
                })],
            })

        with self.assertRaises(UserError):
            bill(self.lender, False).action_post()
        with self.assertRaises(UserError):
            bill(self.vendor, rental).action_post()
        ok = bill(self.lender, rental)
        ok.action_post()
        self.assertEqual(ok.state, "posted")

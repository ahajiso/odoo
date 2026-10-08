from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import EquipmentCommon


@tagged("post_install", "-at_install")
class TestAuditFixes(EquipmentCommon):
    """Cases raised by the audit of commit 504da4e."""

    def _receipt(self, product, serial, owner=None):
        suppliers = self.env.ref("stock.stock_location_suppliers")
        picking = self.env["stock.picking"].create({
            "picking_type_id": self.warehouse.in_type_id.id,
            "location_id": suppliers.id, "location_dest_id": self.stock.id,
            "owner_id": owner.id if owner else False,
            "move_ids": [Command.create({
                "name": product.name, "product_id": product.id, "product_uom_qty": 1,
                "product_uom": product.uom_id.id, "location_id": suppliers.id,
                "location_dest_id": self.stock.id,
            })],
        })
        picking.action_confirm()
        move = picking.move_ids
        move.move_line_ids.unlink()
        self.env["stock.move.line"].create({
            "move_id": move.id, "picking_id": picking.id, "product_id": product.id,
            "lot_name": serial, "quantity": 1, "product_uom_id": product.uom_id.id,
            "owner_id": owner.id if owner else False,
            "location_id": suppliers.id, "location_dest_id": self.stock.id,
        })
        return picking

    def _borrowed(self, serial):
        lot = self.env["stock.lot"].create(
            {"name": serial, "product_id": self.drill.id, "company_id": self.company.id}
        )
        return self.env["maintenance.equipment"].sudo().create({
            "name": serial, "product_id": self.drill.id, "stock_lot_id": lot.id,
            "ownership_status": "borrowed", "owner_partner_id": self.lender.id,
            "company_id": self.company.id,
        })

    # 1. borrowed equipment received without owner
    def test_borrowed_serial_without_owner_refused(self):
        self._borrowed("NB1")
        picking = self._receipt(self.drill, "NB1", owner=None)
        with self.assertRaises(ValidationError):
            picking.button_validate()

    # 2. integration checks the owner on stock
    def test_finalize_checks_stock_owner(self):
        equipment = self._borrowed("NB2")
        equipment.write({"warranty_status": "no_warranty", "insurance_status": "insured",
                         "replacement_value": 900.0,
                         "replacement_value_date": fields.Date.today()})
        # A quant of the serial number owned by the company (inconsistent with borrowed).
        self.env["stock.quant"].sudo()._update_available_quantity(
            self.drill, self.stock, 1, lot_id=equipment.stock_lot_id
        )
        with self.assertRaises(ValidationError):
            equipment.action_finalize_integration()
        self.assertEqual(equipment.integration_state, "draft")

    # 3. locations validated server-side
    def test_locations_validated(self):
        suppliers = self.env.ref("stock.stock_location_suppliers")
        with self.assertRaises(ValidationError):
            self.env["maintenance.equipment"].create(
                {"name": "x", "current_location_id": suppliers.id}
            )
        with self.assertRaises(ValidationError):
            self.env["maintenance.equipment"].create(
                {"name": "y", "current_location_id": self.warehouse.view_location_id.id}
            )
        Location = self.env["stock.location"]
        for bad in (suppliers, self.warehouse.view_location_id):
            with self.assertRaises(ValidationError):
                Location.create({
                    "name": "At customer", "usage": "internal",
                    "location_id": self.warehouse.view_location_id.id,
                    "place_type": "lent_out", "return_location_id": bad.id,
                })

    # 4. lowering a quantity never archives an integrated equipment
    def test_release_keeps_integrated_equipment(self):
        po = self._order(self.small_tool, 2)
        bill = self._bill(po)
        equipment = self._equipment_of(bill)
        equipment.write({"current_location_id": self.stock.id,
                         "warranty_status": "no_warranty", "insurance_status": "insured"})
        equipment.action_finalize_integration()
        bill.button_draft()
        bill.invoice_line_ids[:1].quantity = 1
        bill.action_post()
        self.assertEqual(len(self._equipment_of(bill)), 1)
        released = equipment - self._equipment_of(bill)
        self.assertEqual(len(released), 1)
        self.assertTrue(released.active, "integrated equipment is detached, not archived")
        self.assertFalse(released.move_line_id)

    # 5. rental account needs an equipment rental line
    def test_rent_account_with_ordinary_contract_line_refused(self):
        contract = self.env["contract.contract"].create({
            "name": "Ordinary", "partner_id": self.lender.id, "contract_type": "purchase",
            "line_recurrence": True, "company_id": self.company.id,
            "contract_line_ids": [Command.create({
                "product_id": self.rent_service.id, "name": "Service", "quantity": 1,
                "price_unit": 50.0, "recurring_rule_type": "monthly", "recurring_interval": 1,
                "date_start": "2026-01-01", "recurring_next_date": "2026-01-01",
            })],
        })
        bill = self.env["account.move"].create({
            "move_type": "in_invoice", "partner_id": self.lender.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [Command.create({
                "product_id": self.rent_service.id, "quantity": 1, "price_unit": 50.0,
                "account_id": self.acc_rent.id, "tax_ids": [Command.clear()],
                "contract_line_id": contract.contract_line_ids.id,
            })],
        })
        with self.assertRaises(UserError):
            bill.action_post()

    # 6. fixed-asset category guarantees stay true after configuration
    def test_fixed_asset_guarantees_after_configuration(self):
        with self.assertRaises(ValidationError):
            self.profile.asset_product_item = False
        with self.assertRaises(ValidationError):
            self.acc_asset.asset_profile_id = False
        with self.assertRaises(ValidationError):
            self.env["product.product"].create({
                "name": "Untracked asset", "type": "consu", "is_storable": True,
                "categ_id": self.categ_fixed.id, "tracking": "none",
            })

    # complements
    def test_equipment_contract_line_needs_service_product(self):
        equipment = self.env["maintenance.equipment"].create(
            {"name": "Lift", "current_location_id": self.stock.id}
        )
        with self.assertRaises(ValidationError):
            self.env["contract.contract"].create({
                "name": "C", "partner_id": self.lender.id, "contract_type": "purchase",
                "line_recurrence": True, "company_id": self.company.id,
                "contract_line_ids": [Command.create({
                    "name": "No product", "quantity": 1, "price_unit": 10.0,
                    "recurring_rule_type": "monthly", "recurring_interval": 1,
                    "date_start": "2026-01-01", "recurring_next_date": "2026-01-01",
                    "equipment_id": equipment.id, "equipment_nature": "rental",
                })],
            })

    def test_refund_carrying_equipment_refused(self):
        refund = self.env["account.move"].create({
            "move_type": "in_refund", "partner_id": self.vendor.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [Command.create({
                "product_id": self.small_tool.id, "quantity": 1, "price_unit": 50.0,
                "account_id": self.acc_expense.id, "tax_ids": [Command.clear()],
            })],
        })
        equipment = self.env["maintenance.equipment"].create({"name": "Linked"})
        refund.invoice_line_ids._link_equipment(equipment)
        with self.assertRaises(UserError):
            refund.action_post()

    def test_asset_of_another_company_refused(self):
        bill = self.env["account.move"].create({
            "move_type": "in_invoice", "partner_id": self.vendor.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [Command.create({
                "name": "Asset", "quantity": 1, "price_unit": 1000.0,
                "account_id": self.acc_asset.id, "tax_ids": [Command.clear()],
            })],
        })
        bill.action_post()
        asset = bill.invoice_line_ids.asset_id
        self.assertTrue(asset)
        other = self.env.ref("base.main_company")
        equipment = self.env["maintenance.equipment"].sudo().with_context(
            allowed_company_ids=[self.company.id, other.id]
        ).create({"name": "Other company", "company_id": other.id})
        with self.assertRaises(ValidationError):
            equipment.asset_id = asset

    def test_archived_unserialised_product_does_not_block_category(self):
        categ = self.env["product.category"].create({
            "name": "Fixed Assets 2", "property_cost_method": "average",
            "property_valuation": "manual_periodic",
            "property_account_expense_categ_id": self.acc_asset.id,
        })
        product = self.env["product.template"].create({
            "name": "Old saw", "type": "consu", "is_storable": True, "tracking": "none",
            "categ_id": categ.id,
        })
        with self.assertRaises(ValidationError):
            categ.is_fixed_asset_stock = True
        product.active = False
        categ.is_fixed_asset_stock = True
        self.assertTrue(categ.is_fixed_asset_stock)

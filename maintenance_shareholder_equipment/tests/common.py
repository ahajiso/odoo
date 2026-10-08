from odoo import Command, fields
from odoo.tests import TransactionCase


class EquipmentCommon(TransactionCase):
    """French company with its chart of accounts and the phase 0 test choices
    (docs/phase0/README.md), independent of the data of the database."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company = env["res.company"].create({
            "name": "LADB equipment tests",
            "country_id": env.ref("base.fr").id,
            "currency_id": env.ref("base.EUR").id,
        })
        env.user.company_ids |= cls.company
        env["account.chart.template"].try_loading("fr", cls.company, install_demo=False)
        cls.env = env(context=dict(env.context, allowed_company_ids=[cls.company.id],
                                   tracking_disable=True))
        cls.env.user.company_id = cls.company
        env = cls.env
        Account = env["account.account"]

        def account(code):
            return Account.search([("code", "=", code), ("company_ids", "in", cls.company.id)], limit=1)

        cls.acc_asset = account("215400")
        cls.acc_depr = account("281500")
        cls.acc_depr_exp = account("681120")
        cls.acc_rent = account("613500")
        cls.acc_expense = account("606300")
        cls.company.equipment_rent_account_id = cls.acc_rent
        misc = env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.profile = env["account.asset.profile"].create({
            "name": "Matériel et outillage (test)",
            "account_asset_id": cls.acc_asset.id,
            "account_depreciation_id": cls.acc_depr.id,
            "account_expense_depreciation_id": cls.acc_depr_exp.id,
            "journal_id": misc.id,
            "method": "linear",
            "method_time": "year",
            "method_number": 5,
            "method_period": "year",
            "prorata": True,
            "asset_product_item": True,
        })
        cls.categ_fixed = env["product.category"].create({
            "name": "Fixed Assets",
            "property_cost_method": "average",
            "property_valuation": "manual_periodic",
            "property_account_expense_categ_id": cls.acc_asset.id,
            "is_fixed_asset_stock": True,
        })
        cls.categ_tools = env["product.category"].create({
            "name": "Small tools",
            "property_cost_method": "average",
            "property_valuation": "manual_periodic",
            "property_account_expense_categ_id": cls.acc_expense.id,
        })
        cls.warehouse = env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        ) or env["stock.warehouse"].create({"name": "WH test", "code": "WT", "company_id": cls.company.id})
        cls.stock = cls.warehouse.lot_stock_id
        cls.vendor = env["res.partner"].create({"name": "Vendor"})
        cls.lender = env["res.partner"].create({"name": "Lender"})
        cls.drill = cls._product("Drill", cls.categ_fixed, storable=True)
        cls.small_tool = cls._product("Small tool", cls.categ_tools, storable=False)
        cls.rent_service = env["product.product"].create({
            "name": "Monthly rent", "type": "service", "purchase_ok": True,
            "property_account_expense_id": cls.acc_rent.id,
        })
        cls._setup_phase2()

    @classmethod
    def _setup_phase2(cls):
        """Settings of docs/phase2/setup_phase2.py and the four test profiles."""
        env = cls.env
        Account = env["account.account"]

        def account(code):
            return Account.search([("code", "=", code), ("company_ids", "in", cls.company.id)], limit=1)

        cls.acc_rent_income = account("708300")
        Product = env["product.product"]
        cls.loan_product = Product.create({"name": "Prêt de matériel", "type": "service"})
        cls.rent_received_product = Product.create({
            "name": "Location de matériel (facturée)", "type": "service", "sale_ok": True,
            "property_account_income_id": cls.acc_rent_income.id,
        })
        Location = env["stock.location"]
        inventory_parent = env.ref("stock.stock_location_locations_virtual")
        cls.acq_locations = {}
        for nature, code in (("gift", "778000"), ("current_account", "455100"),
                             ("regularisation", "603200")):
            cls.acq_locations[nature] = Location.create({
                "name": "Acquisitions / %s" % nature, "usage": "inventory",
                "location_id": inventory_parent.id, "company_id": cls.company.id,
                "valuation_out_account_id": account(code).id,
            })
        cls.company.write({
            "equipment_loan_product_id": cls.loan_product.id,
            "equipment_rent_paid_product_id": cls.rent_service.id,
            "equipment_rent_received_product_id": cls.rent_received_product.id,
            "equipment_gift_location_id": cls.acq_locations["gift"].id,
            "equipment_current_account_location_id": cls.acq_locations["current_account"].id,
            "equipment_regularisation_location_id": cls.acq_locations["regularisation"].id,
        })
        cls.offsite_parent = Location.create({
            "name": "Chez tiers", "usage": "internal", "is_offsite_parent": True,
            "location_id": cls.warehouse.view_location_id.id, "company_id": cls.company.id,
        })
        Users = env["res.users"].with_context(no_reset_password=True)
        operator = env.ref("maintenance_shareholder_equipment.group_equipment_operator")
        approver = env.ref("maintenance_shareholder_equipment.group_equipment_approver")
        stock_user = env.ref("stock.group_stock_user")

        def user(login, groups):
            return Users.create({
                "name": login, "login": login, "email": "%s@example.com" % login,
                "company_id": cls.company.id, "company_ids": [Command.set(cls.company.ids)],
                "groups_id": [Command.set([env.ref("base.group_user").id] + [g.id for g in groups])],
            })

        cls.user_operator = user("eq_operator", [operator])
        cls.user_approver = user("eq_approver", [approver])
        cls.user_both = user("eq_both", [operator, approver])
        cls.user_stock = user("eq_stock", [stock_user])

    @classmethod
    def _product(cls, name, categ, storable):
        vals = {
            "name": name,
            "type": "consu",
            "maintenance_ok": True,
            "categ_id": categ.id,
            "standard_price": 100.0,
            "purchase_method": "purchase",
            "supplier_taxes_id": [Command.clear()],
        }
        if storable:
            vals.update(is_storable=True, tracking="serial")
        return cls.env["product.product"].create(vals)

    # ------------------------------------------------------------ purchase helpers

    def _order(self, product, qty):
        po = self.env["purchase.order"].create({
            "partner_id": self.vendor.id,
            "picking_type_id": self.warehouse.in_type_id.id,
            "order_line": [Command.create({
                "product_id": product.id, "product_qty": qty, "price_unit": 100.0,
                "taxes_id": [Command.clear()],
            })],
        })
        po.button_confirm()
        return po

    def _receive(self, po, serials):
        """Receive the given serial numbers through a purchase operation (phase 2):
        the equipment are created once, at receipt, and integrated."""
        po_line = po.order_line[:1]
        op = self._operation("receipt", receipt_branch="purchase", partner_id=po.partner_id.id,
                             purchase_mode="existing", purchase_id=po.id, lines=[
                                 dict(product_id=po_line.product_id.id, purchase_line_id=po_line.id,
                                      lot_name=serial)
                                 for serial in serials])
        op.action_execute()
        return op.line_ids.equipment_id

    def _operation(self, operation_type, lines=(), user=None, **vals):
        """Draft operation with sensible defaults for the tests."""
        defaults = {
            "receipt": {"picking_type_id": self.warehouse.in_type_id.id,
                        "location_dest_id": self.stock.id},
            "exit": {"picking_type_id": self.warehouse.int_type_id.id},
            "return": {"picking_type_id": self.warehouse.int_type_id.id},
            "restitution": {"picking_type_id": self.warehouse.out_type_id.id},
        }[operation_type]
        line_defaults = {"warranty_status": "no_warranty", "insurance_status": "insured"}
        Operation = self.env["equipment.operation"]
        if user:
            Operation = Operation.with_user(user)
        return Operation.create(dict(
            defaults, operation_type=operation_type, company_id=self.company.id,
            line_ids=[Command.create(dict(line_defaults, **line)) for line in lines],
            **vals,
        ))

    def _as_running_operation(self, picking, operation_type="receipt"):
        """Link a hand-made picking to an operation being executed (tests of the
        phase 1 rules in isolation)."""
        op = self.env["equipment.operation"].sudo().create({
            "operation_type": operation_type, "company_id": self.company.id,
            "receipt_branch": "borrowed" if operation_type == "receipt" else False,
        })
        op.write({"state": "processing"})
        picking.sudo().write({"equipment_operation_id": op.id})
        return op

    def _bill(self, po, qty=None, post=True):
        po.action_create_invoice()
        bill = po.invoice_ids.filtered(lambda m: m.state == "draft")[:1]
        bill.invoice_date = fields.Date.today()
        if qty is not None:
            line = bill.invoice_line_ids[:1]
            line.quantity = qty
        if post:
            bill.action_post()
        return bill

    def _equipment_of(self, bill):
        return bill.invoice_line_ids.equipment_ids

    def assertLinksConsistent(self, bill):
        for line in bill.invoice_line_ids:
            for equipment in line.equipment_ids:
                self.assertEqual(equipment.move_line_id, line)
        pointing = self.env["maintenance.equipment"].with_context(active_test=False).search(
            [("move_line_id", "in", bill.line_ids.ids)]
        )
        self.assertEqual(pointing, bill.invoice_line_ids.equipment_ids)

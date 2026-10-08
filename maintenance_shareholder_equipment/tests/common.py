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
        """Receive the given serial numbers and create their equipment, as the phase 2
        receiving action will (equipment created once, at receipt)."""
        picking = po.picking_ids.filtered(lambda p: p.state not in ("done", "cancel"))[:1]
        move = picking.move_ids[:1]
        move.move_line_ids.unlink()
        for serial in serials:
            self.env["stock.move.line"].create({
                "move_id": move.id, "picking_id": picking.id, "product_id": move.product_id.id,
                "lot_name": serial, "quantity": 1, "product_uom_id": move.product_uom.id,
                "location_id": move.location_id.id, "location_dest_id": move.location_dest_id.id,
            })
        res = picking.button_validate()
        if isinstance(res, dict) and res.get("res_model") == "stock.backorder.confirmation":
            self.env["stock.backorder.confirmation"].with_context(res["context"]).process()
        lots = self.env["stock.lot"].search([("name", "in", serials), ("product_id", "=", move.product_id.id)])
        return self.env["maintenance.equipment"].sudo().create([
            {"name": lot.name, "product_id": lot.product_id.id, "stock_lot_id": lot.id,
             "company_id": self.company.id}
            for lot in lots
        ]).sudo(False)

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

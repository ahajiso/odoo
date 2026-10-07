from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _prepare_equipment_vals(self):
        """Equipment created from a vendor bill (OCA maintenance_account) gets a
        stock (the company's main warehouse stock, to be moved afterwards if
        needed) and its purchase cost (untaxed, company currency)."""
        vals = super()._prepare_equipment_vals()
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.move_id.company_id.id)], limit=1
        )
        vals["current_location_id"] = warehouse.lot_stock_id.id
        if self.quantity:
            vals["cost"] = abs(self.balance) / self.quantity
        return vals

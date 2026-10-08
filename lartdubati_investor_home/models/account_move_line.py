from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _prepare_equipment_vals(self):
        """Equipment created from a vendor bill (OCA maintenance_account) gets its
        purchase cost (untaxed, company currency). It is created to complete; its
        serial number or location is set when it is received or integrated."""
        vals = super()._prepare_equipment_vals()
        if self.quantity:
            vals["cost"] = abs(self.balance) / self.quantity
        return vals

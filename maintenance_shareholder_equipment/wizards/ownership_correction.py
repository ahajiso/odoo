from odoo import fields, models

from ..models.maintenance_equipment import OWNERSHIP_STATUS


class EquipmentOwnershipCorrection(models.TransientModel):
    _name = "equipment.ownership.correction"
    _description = "Correct the ownership of an equipment"

    equipment_id = fields.Many2one("maintenance.equipment", required=True, readonly=True)
    ownership_status = fields.Selection(OWNERSHIP_STATUS, required=True)
    owner_partner_id = fields.Many2one("res.partner", string="Legal Owner", required=True)
    reason = fields.Text(required=True)

    def action_apply(self):
        self.ensure_one()
        self.equipment_id._set_ownership(self.ownership_status, self.owner_partner_id, self.reason)
        return {"type": "ir.actions.act_window_close"}

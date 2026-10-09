from odoo import api, fields, models


class EquipmentCostCorrection(models.TransientModel):
    """Manual correction of an equipment cost (phase 2f, D7): Accounting /
    Administrator only, with a reason, traced in the equipment's chatter."""

    _name = "equipment.cost.correction"
    _description = "Correct the cost of an equipment"

    equipment_id = fields.Many2one("maintenance.equipment", required=True, readonly=True)
    currency_id = fields.Many2one(related="equipment_id.company_id.currency_id")
    cost_known = fields.Boolean(string="Cost Known", default=True)
    cost = fields.Float(help="Unit cost in company currency.")
    cost_date = fields.Date(string="Cost Date", default=fields.Date.context_today)
    cost_provisional = fields.Boolean(string="Provisional")
    reason = fields.Text(required=True)

    @api.model
    def default_get(self, field_names):
        res = super().default_get(field_names)
        equipment = self.env["maintenance.equipment"].browse(res.get("equipment_id"))
        if equipment.exists() and equipment.cost_known:
            res.update(cost=equipment.cost, cost_date=equipment.cost_date,
                       cost_provisional=equipment.cost_provisional)
        return res

    def action_apply(self):
        self.ensure_one()
        self.equipment_id._set_cost(
            self.cost if self.cost_known else None, self.cost_date, self.cost_provisional,
            "manual", self.env.user.name, reason=self.reason)
        return {"type": "ir.actions.act_window_close"}

from odoo import api, fields, models

from .ownership import OWNERSHIP_SELECTION, RENT_PERIOD_SELECTION

ACQUISITION_TO_OWNERSHIP = {
    "rental": "rented",
    "borrowed": "borrowed",
    "loaned_out": "lent_out",
}


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    # Derived from the existing acquisition_mode / owner_type values.
    # Not labelled "Ownership Status": that label is used by ownership_state.
    ownership = fields.Selection(
        OWNERSHIP_SELECTION,
        compute="_compute_ownership",
        store=True,
        index=True,
    )
    rent_amount = fields.Monetary(currency_field="rent_currency_id")
    rent_currency_id = fields.Many2one(
        "res.currency", compute="_compute_rent_currency_id"
    )
    rent_period = fields.Selection(RENT_PERIOD_SELECTION)
    rent_start_date = fields.Date()

    @api.depends("acquisition_mode", "owner_type")
    def _compute_ownership(self):
        for equipment in self:
            ownership = ACQUISITION_TO_OWNERSHIP.get(equipment.acquisition_mode)
            if not ownership:
                ownership = "owned" if equipment.owner_type == "company" else "borrowed"
            equipment.ownership = ownership

    @api.depends("current_location_id.currency_id", "company_id")
    def _compute_rent_currency_id(self):
        for equipment in self:
            equipment.rent_currency_id = (
                equipment.current_location_id.currency_id
                or (equipment.company_id or self.env.company).currency_id
            )

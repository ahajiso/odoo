from odoo import _, api, models
from odoo.exceptions import ValidationError


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    @api.constrains("current_location_id", "active")
    def _check_current_location_stock(self):
        """Every active equipment is in a stock, so the stock monitor sees it."""
        for equipment in self.filtered("active"):
            if equipment.current_location_id.usage != "internal":
                raise ValidationError(
                    _(
                        "Equipment %(name)s must have a Current Location that is an "
                        "internal stock.",
                        name=equipment.name,
                    )
                )

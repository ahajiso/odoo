from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .maintenance_equipment import THIRD_PARTY_OWNED


class StockLocation(models.Model):
    _inherit = "stock.location"

    # Moved from lartdubati_investor_home (same name and values, column kept).
    place_type = fields.Selection(
        [
            ("physical", "Physical"),
            ("lent_out", "Lent Out"),
            ("virtual", "Virtual"),
        ],
        default="physical",
        required=True,
        help="Lent Out: the stock that lent-out items belong to and return to.",
    )
    return_location_id = fields.Many2one(
        "stock.location",
        string="Return Location",
        domain="[('usage', '=', 'internal'), ('place_type', '=', 'physical')]",
        help="Stock in a real warehouse where items held by the third party come back.",
    )

    @api.constrains("place_type", "return_location_id", "active")
    def _check_return_location(self):
        for location in self.filtered(lambda loc: loc.active and loc.place_type == "lent_out"):
            if not location.return_location_id:
                raise ValidationError(
                    _("%(name)s is a lent-out stock: its return location is required.",
                      name=location.complete_name)
                )
            if location.return_location_id == location:
                raise ValidationError(
                    _("%(name)s cannot be its own return location.", name=location.complete_name)
                )


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _action_done(self):
        res = super()._action_done()
        self.exists()._check_third_party_owner()
        return res

    def _check_third_party_owner(self):
        """A third-party owner on stock only for a serial number linked to exactly one
        borrowed or rented equipment of that owner. Consumables are owned only (v1)."""
        Equipment = self.env["maintenance.equipment"].sudo().with_context(active_test=False)
        # Called right after super()._action_done(): the move itself is set to done
        # only afterwards, so the line state cannot be used as a filter here.
        for line in self.filtered("owner_id"):
            equipments = Equipment.search([("stock_lot_id", "=", line.lot_id.id)]) if line.lot_id else Equipment
            ok = (
                line.product_id.tracking == "serial"
                and line.lot_id
                and len(equipments) == 1
                and equipments.ownership_status in THIRD_PARTY_OWNED
                and equipments.owner_partner_id == line.owner_id
            )
            if not ok:
                raise ValidationError(
                    _("%(product)s %(lot)s: an owner other than the company is only "
                      "allowed for a serial number of a borrowed or rented equipment of "
                      "that owner (%(owner)s).",
                      product=line.product_id.display_name, lot=line.lot_id.name or "",
                      owner=line.owner_id.display_name)
                )

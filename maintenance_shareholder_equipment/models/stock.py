from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

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
    is_offsite_parent = fields.Boolean(
        string="Parent of Off-Site Stocks",
        help="Off-site stocks (held by third parties) are created under this location, "
        "outside the warehouse stock (e.g. WH/Chez tiers).",
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
            ret = location.return_location_id
            if not (
                ret.active
                and ret.usage == "internal"
                and ret.place_type == "physical"
                and (not ret.company_id or not location.company_id
                     or ret.company_id == location.company_id)
            ):
                raise ValidationError(
                    _("%(name)s: the return location must be an active internal physical "
                      "stock of the same company.", name=location.complete_name)
                )


def _refuse_link_from_client(env, vals_list):
    """The link to an equipment operation is written only by server code (superuser
    mode, not reachable by RPC), never by a client."""
    if not env.su and any("equipment_operation_id" in vals for vals in vals_list):
        raise AccessError(_("The equipment operation link is set by the operation only."))


class StockPicking(models.Model):
    _inherit = "stock.picking"

    equipment_operation_id = fields.Many2one(
        "equipment.operation", string="Equipment Operation", readonly=True, copy=False,
        index="btree_not_null",
    )

    @api.model_create_multi
    def create(self, vals_list):
        _refuse_link_from_client(self.env, vals_list)
        return super().create(vals_list)

    def write(self, vals):
        _refuse_link_from_client(self.env, [vals])
        return super().write(vals)


class StockMove(models.Model):
    _inherit = "stock.move"

    equipment_operation_id = fields.Many2one(
        "equipment.operation", string="Equipment Operation", readonly=True, copy=False,
        index="btree_not_null",
    )

    @api.model_create_multi
    def create(self, vals_list):
        _refuse_link_from_client(self.env, vals_list)
        return super().create(vals_list)

    def write(self, vals):
        _refuse_link_from_client(self.env, [vals])
        return super().write(vals)


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _action_done(self):
        res = super()._action_done()
        lines = self.exists()
        lines._check_equipment_operation()
        lines._check_third_party_owner()
        return res

    def _running_operation(self):
        """Operation type of the equipment operation being executed that this line
        belongs to, or False."""
        self.ensure_one()
        operation = (self.move_id.equipment_operation_id
                     or self.picking_id.equipment_operation_id).sudo()
        return operation.operation_type if operation.state == "processing" else False

    def _check_equipment_operation(self):
        """Stock movements governed by phase 2 (docs/phase2/PLAN.md, section 8):
        - supplier receipts and acquisitions, consumables included, only through a
          receipt operation;
        - a maintainable product tracked in stock never enters or leaves the internal
          locations without its operation (receipt in, restitution out); owned
          equipment never leaves the company (until the disposal operation);
        - entering or leaving an off-site (lent-out) stock: exit / return operations;
        - consumables never enter an off-site stock (v1)."""
        Equipment = self.env["maintenance.equipment"].sudo().with_context(active_test=False)
        companies = self.env["res.company"].sudo().search([])
        acquisition = (companies.equipment_gift_location_id
                       | companies.equipment_current_account_location_id
                       | companies.equipment_regularisation_location_id)
        by_lot = {}
        if self.lot_id:
            for equipment in Equipment.search([("stock_lot_id", "in", self.lot_id.ids)]):
                by_lot.setdefault(equipment.stock_lot_id.id, equipment)

        def refuse(line, message):
            raise ValidationError(_("%(product)s %(lot)s: %(message)s",
                                    product=line.product_id.display_name,
                                    lot=line.lot_id.name or "", message=message))

        for line in self:
            running = line._running_operation()
            src, dst = line.location_id, line.location_dest_id
            src_in, dst_in = src.usage == "internal", dst.usage == "internal"
            product = line.product_id
            equipment = by_lot.get(line.lot_id.id) if line.lot_id else None
            if dst_in and not src_in and (src.usage == "supplier" or src in acquisition) \
                    and running != "receipt":
                refuse(line, _("receipts from suppliers and acquisitions go through an "
                               "equipment operation (Receipt)."))
            if equipment or (product.maintenance_ok and product.is_storable):
                if dst_in and not src_in and running != "receipt":
                    refuse(line, _("an equipment enters the stock only through a receipt "
                                   "operation."))
                if src_in and not dst_in:
                    if equipment and equipment.ownership_status in THIRD_PARTY_OWNED:
                        if running != "restitution":
                            refuse(line, _("property of a third party: it leaves only "
                                           "through a restitution to its owner."))
                    else:
                        refuse(line, _("an equipment of the company cannot leave the "
                                       "company (sale, scrap, return, loss) until the "
                                       "disposal operation exists."))
                if src_in and dst_in and src != dst:
                    kinds = (src.place_type, dst.place_type)
                    if dst.place_type == "virtual":
                        refuse(line, _("an equipment cannot be moved to a virtual place."))
                    if "lent_out" in kinds:
                        if kinds == ("physical", "lent_out"):
                            if running != "exit":
                                refuse(line, _("only an exit operation moves equipment to "
                                               "an off-site stock."))
                        elif kinds == ("lent_out", "physical"):
                            if running != "return":
                                refuse(line, _("only a return operation brings equipment "
                                               "back from an off-site stock."))
                        else:
                            refuse(line, _("an equipment goes from one off-site stock to "
                                           "another only through a return and a new exit."))
            elif dst_in and dst.place_type == "lent_out" and src.place_type != "lent_out":
                refuse(line, _("consumables are always owned and never lent out (v1)."))

    def _check_third_party_owner(self):
        """Owner on stock and equipment ownership must agree, in both directions:
        - a line with an owner other than the company needs a serial number linked to
          exactly one borrowed or rented equipment of that owner (consumables are owned
          only, v1);
        - a line carrying the serial number of an equipment needs the owner expected by
          that equipment: the third party for borrowed / rented, none for owned /
          lent-out."""
        Equipment = self.env["maintenance.equipment"].sudo().with_context(active_test=False)
        # Called right after super()._action_done(): the move itself is set to done
        # only afterwards, so the line state cannot be used as a filter here.
        lots = self.lot_id
        by_lot = {}
        if lots:
            for equipment in Equipment.search([("stock_lot_id", "in", lots.ids)]):
                by_lot.setdefault(equipment.stock_lot_id.id, equipment)
        for line in self:
            equipment = by_lot.get(line.lot_id.id) if line.lot_id else None
            if line.owner_id:
                ok = (
                    line.product_id.tracking == "serial"
                    and equipment
                    and Equipment.search_count([("stock_lot_id", "=", line.lot_id.id)]) == 1
                    and equipment.ownership_status in THIRD_PARTY_OWNED
                    and equipment.owner_partner_id == line.owner_id
                )
                if not ok:
                    raise ValidationError(
                        _("%(product)s %(lot)s: an owner other than the company is only "
                          "allowed for a serial number of a borrowed or rented equipment "
                          "of that owner (%(owner)s).",
                          product=line.product_id.display_name, lot=line.lot_id.name or "",
                          owner=line.owner_id.display_name)
                    )
            elif equipment and equipment.ownership_status in THIRD_PARTY_OWNED:
                raise ValidationError(
                    _("%(product)s %(lot)s belongs to %(owner)s (%(status)s equipment): "
                      "the stock move must carry that owner.",
                      product=line.product_id.display_name, lot=line.lot_id.name,
                      owner=equipment.owner_partner_id.display_name,
                      status=equipment.ownership_status)
                )

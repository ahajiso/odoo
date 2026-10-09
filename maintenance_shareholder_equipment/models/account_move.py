from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare, float_round


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # OCA maintenance_account field, redeclared: a reversal is built with copy() and
    # must not start with the equipment of the original bill.
    equipment_ids = fields.Many2many(copy=False)

    # ------------------------------------------------------- link, both relations

    @api.constrains("equipment_ids")
    def _check_equipment_links(self):
        """Side 2 of the link (side 1: maintenance.equipment._check_single_bill_line):
        every equipment of the line points to it, and none is listed by another line of
        a non-cancelled bill."""
        for line in self.filtered("equipment_ids"):
            wrong = line.equipment_ids.filtered(lambda e: e.move_line_id != line)
            if wrong:
                raise ValidationError(
                    _("Bill line %(line)s lists equipment linked to another line: %(eq)s",
                      line=line.display_name, eq=", ".join(wrong.mapped("display_name")))
                )
            other = self.sudo().search_count([
                ("equipment_ids", "in", line.equipment_ids.ids),
                ("id", "!=", line.id),
                ("parent_state", "!=", "cancel"),
            ])
            if other:
                raise ValidationError(
                    _("Bill line %(line)s: an equipment is already listed by another bill "
                      "line.", line=line.display_name)
                )

    def write(self, vals):
        if "equipment_ids" in vals and not self.env.su:
            before = {line.id: line.equipment_ids for line in self}
            res = super().write(vals)
            for line in self:
                removed = before[line.id] - line.equipment_ids
                if removed.filtered(lambda e: e.move_line_id == line):
                    raise AccessError(
                        _("An equipment linked to bill line %s cannot be removed from it "
                          "directly.", line.display_name)
                    )
            return res
        return super().write(vals)

    def _link_equipment(self, equipments):
        """Link equipment to this line, both relations, in the order compatible with the
        constraints (and with maintenance_account): move_line_id first, then the
        many2many. Private: not callable by RPC."""
        self.ensure_one()
        line = self.sudo()
        equipments = equipments.sudo()
        equipments.write({"move_line_id": line.id})
        line.write({"equipment_ids": [(4, e.id) for e in equipments]})
        line._check_link_invariant()

    def _unlink_equipment(self, equipments):
        """Reverse order: many2many first, then move_line_id."""
        self.ensure_one()
        line = self.sudo()
        equipments = equipments.sudo()
        line.write({"equipment_ids": [(3, e.id) for e in equipments]})
        equipments.filtered(lambda e: e.move_line_id == line).write({"move_line_id": False})
        line._check_link_invariant()

    def _check_link_invariant(self):
        Equipment = self.env["maintenance.equipment"].sudo().with_context(active_test=False)
        for line in self.sudo():
            pointing = Equipment.search([("move_line_id", "=", line.id)])
            if pointing != line.equipment_ids:
                raise ValidationError(
                    _("Bill line %s: equipment links are inconsistent.", line.display_name)
                )

    # --------------------------------------------- asset split keeps the order link

    def _expand_asset_line(self):
        """account_asset_management splits a line in quantity-1 copies; Odoo copies
        purchase_line_id only with include_business_fields. Without it the purchase
        order counts one unit invoiced instead of all (docs/phase1/CHARACTERISATION.md)."""
        return super(
            AccountMoveLine, self.with_context(include_business_fields=True)
        )._expand_asset_line()

    # ------------------------------------------------------------------- helpers

    def _is_equipment_line(self):
        self.ensure_one()
        return (
            self.display_type == "product"
            and self.product_id
            and self.product_id.product_tmpl_id.maintenance_ok
        )

    def _equipment_units(self):
        self.ensure_one()
        qty = self.quantity
        if self.product_uom_id and self.product_uom_id != self.product_id.uom_id:
            # one equipment per unit of the product, also for a bill in packs
            qty = self.product_uom_id._compute_quantity(qty, self.product_id.uom_id)
        if float_compare(qty, float_round(qty, precision_digits=0), precision_digits=6) or qty <= 0:
            raise UserError(
                _("Bill line %s: an equipment line must have a whole, positive number of "
                  "units.", self.display_name)
            )
        return int(round(qty))


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        self._check_asset_supplier_refunds()
        self._check_rent_lines()
        refund_lines = self._equipment_refund_lines()
        linked_refunds = self.filtered(lambda m: m.move_type == "in_refund").invoice_line_ids.filtered(
            "equipment_ids"
        )
        if linked_refunds:
            raise UserError(
                _("A supplier refund cannot carry equipment (%s): returns of equipment go "
                  "through the stock return.",
                  ", ".join(linked_refunds.equipment_ids.mapped("display_name")))
            )
        refund_before = {line.id: line.equipment_ids for line in refund_lines}
        for move in self.filtered(lambda m: m.move_type == "in_invoice"):
            move._reconcile_equipment()
        res = super().action_post()
        # maintenance_account creates equipment for refund lines too
        # (is_purchase_document() includes in_refund): remove what it just created.
        for line in refund_lines.exists():
            created = line.equipment_ids - refund_before[line.id]
            if created:
                line._unlink_equipment(created)
                created.sudo().unlink()
        posted = self.filtered(lambda m: m.move_type == "in_invoice" and m.state == "posted")
        posted._check_equipment_counts()
        posted._fill_equipment_assets()
        posted._fill_equipment_costs()
        return res

    # ------------------------------------------------------------- reconciliation

    def _reconcile_equipment(self):
        """Each supplier bill line of an equipment product bought on a purchase order
        gets exactly one equipment per unit, reusing the received or free equipment of
        the order line, then creating the missing ones (to complete). maintenance_account
        skips any line that already has equipment, so the whole line is handled here."""
        self.ensure_one()
        for line in self.invoice_line_ids.filtered(
            lambda ln: ln._is_equipment_line() and ln.purchase_line_id
        ):
            units = line._equipment_units()
            linked = line.equipment_ids
            if len(linked) > units:
                self._release_excess(line, linked, len(linked) - units)
            elif len(linked) < units:
                need = units - len(linked)
                free = self._free_equipment(line.purchase_line_id)[:need]
                if free:
                    line._link_equipment(free)
                missing = need - len(free)
                if missing:
                    self._create_draft_equipment(line, missing)

    def _free_equipment(self, purchase_line):
        """Equipment of the purchase line not linked to a non-cancelled bill line:
        received ones (their serial number came in on the order) first, receipt order."""
        Equipment = self.env["maintenance.equipment"].sudo()
        moves = purchase_line.move_ids.filtered(
            lambda m: m.state == "done" and not m.origin_returned_move_id
        )
        lots = moves.move_line_ids.lot_id
        candidates = Equipment.search(
            [("stock_lot_id", "in", lots.ids)], order="id"
        ) if lots else Equipment
        return candidates.filtered(
            lambda e: not e.move_line_id or e.move_line_id.parent_state == "cancel"
        ).with_env(self.env)

    def _create_draft_equipment(self, line, count):
        """Same values as maintenance_account, one equipment per missing unit."""
        if not line.equipment_category_id:
            line._set_equipment_category()
        vals = line._prepare_equipment_vals()
        Equipment = self.env["maintenance.equipment"].sudo().with_company(self.company_id)
        equipments = Equipment.create([dict(vals, move_line_id=False) for _i in range(count)])
        line._link_equipment(equipments)

    def _release_excess(self, line, linked, count):
        """Bill reset to draft and quantity lowered. Released first: equipment still to
        complete without serial number (created for the bill, archived); then any other
        equipment (received or integrated: link removed only, equipment kept, never
        archived); newest first in each group."""
        drafts = linked.filtered(
            lambda e: e.integration_state == "draft" and not e.stock_lot_id
        ).sorted("id", reverse=True)
        others = (linked - drafts).sorted("id", reverse=True)
        to_release = (drafts + others)[:count]
        # the cost is explained before the link to the bill disappears (not a cancellation)
        to_release.sudo()._cost_after_bill_unlink(self, "bill_released")
        line._unlink_equipment(to_release)
        (to_release & drafts).sudo().write({"active": False})
        self.message_post(
            body=_("Equipment released from line %(line)s: %(eq)s",
                   line=line.display_name, eq=", ".join(to_release.mapped("display_name")))
        )

    def _check_equipment_counts(self):
        """After posting: every equipment line bought on an order has exactly one
        equipment per unit, and no equipment points to a line that does not list it."""
        Equipment = self.env["maintenance.equipment"].sudo().with_context(active_test=False)
        for move in self:
            lines = move.invoice_line_ids.filtered(
                lambda ln: ln._is_equipment_line() and ln.purchase_line_id
            )
            for line in lines:
                if len(line.equipment_ids) != line._equipment_units():
                    raise ValidationError(
                        _("Bill line %(line)s: %(n)s equipment for %(units)s units.",
                          line=line.display_name, n=len(line.equipment_ids),
                          units=line._equipment_units())
                    )
            move.invoice_line_ids._check_link_invariant()
            orphans = Equipment.search([("move_line_id", "in", move.line_ids.ids)]).filtered(
                lambda e: e not in e.move_line_id.equipment_ids
            )
            if orphans:
                raise ValidationError(
                    _("Equipment linked to this bill but not listed by its line: %s",
                      ", ".join(orphans.mapped("display_name")))
                )

    def _fill_equipment_costs(self):
        """Real cost from the posted bill line (phase 2f): untaxed company-currency
        balance per unit of the product, at the accounting date; it replaces the
        estimate of the order."""
        for move in self:
            for line in move.invoice_line_ids.filtered(
                lambda ln: ln.display_type == "product" and ln.equipment_ids
            ):
                qty = line.quantity
                if line.product_uom_id and line.product_id and \
                        line.product_uom_id != line.product_id.uom_id:
                    qty = line.product_uom_id._compute_quantity(qty, line.product_id.uom_id)
                if qty <= 0:
                    continue
                line.equipment_ids.sudo()._set_cost(
                    abs(line.balance) / qty, move.date, False, "bill", move.name)

    def button_draft(self):
        """A bill reset to draft makes the cost it gave provisional again, until it is
        posted again."""
        for move in self.filtered(lambda m: m.move_type == "in_invoice" and m.state == "posted"):
            equipment = move.invoice_line_ids.equipment_ids.sudo().filtered(
                lambda e: e.cost_known and e.cost_source == "bill"
                and e.cost_reference == move.name and not e.cost_provisional)
            for item in equipment:
                item._set_cost(item.cost, item.cost_date, True, "bill", move.name)
        return super().button_draft()

    def _fill_equipment_assets(self):
        for line in self.invoice_line_ids.filtered("asset_id"):
            line.equipment_ids.filtered(lambda e: not e.asset_id).sudo().write(
                {"asset_id": line.asset_id.id}
            )

    # ------------------------------------------------------------------ refunds

    def _equipment_refund_lines(self):
        return self.filtered(lambda m: m.move_type == "in_refund").invoice_line_ids.filtered(
            lambda ln: ln.product_id and ln.product_id.product_tmpl_id.maintenance_ok
        )

    def _check_asset_supplier_refunds(self):
        """Test choice C8: refused unless the company allows it, because the asset module
        creates a negative asset and keeps the original (CHARACTERISATION.md)."""
        for move in self.filtered(lambda m: m.move_type == "in_refund"):
            if move.company_id.allow_asset_supplier_refund:
                continue
            lines = move.invoice_line_ids.filtered(
                lambda ln: ln.asset_profile_id or ln.account_id.asset_profile_id
            )
            if lines:
                raise UserError(
                    _("Supplier refund %(move)s has lines on a fixed-asset account "
                      "(%(accounts)s). Its treatment of the fixed asset must be decided by "
                      "the accountant; refunds on these accounts are not allowed by the "
                      "company settings.",
                      move=move.display_name,
                      accounts=", ".join(lines.account_id.mapped("code")))
                )

    # --------------------------------------------------------------------- rent

    def _check_rent_lines(self):
        """Server-side check of contract_line_id (not only the screen domain), and the
        lock on the equipment rental account (C10): a line on that account needs an
        equipment rental line of a supplier contract of the same partner and company."""
        for move in self.filtered(lambda m: m.move_type in ("in_invoice", "in_refund")):
            rent_account = move.company_id.equipment_rent_account_id
            for line in move.invoice_line_ids.filtered(lambda ln: ln.display_type == "product"):
                cl = line.contract_line_id
                on_rent_account = rent_account and line.account_id == rent_account
                if not cl:
                    if on_rent_account:
                        raise UserError(
                            _("Line %(line)s is an equipment rent (account %(account)s): "
                              "link it to the rental contract line of the equipment before "
                              "posting.", line=line.display_name, account=rent_account.code)
                        )
                    continue
                if not (on_rent_account or cl.equipment_id):
                    continue  # ordinary contract line, outside the equipment rules
                contract = cl.contract_id
                if not (
                    cl.equipment_id
                    and cl.equipment_nature == "rental"
                    and contract.contract_type == "purchase"
                    and contract.company_id == move.company_id
                    and contract.partner_id.commercial_partner_id
                    == move.partner_id.commercial_partner_id
                ):
                    raise UserError(
                        _("Line %(line)s: the contract line must be an equipment rental line "
                          "of a supplier contract of %(partner)s in %(company)s.",
                          line=line.display_name, partner=move.partner_id.display_name,
                          company=move.company_id.name)
                    )

    # ------------------------------------------------------------- cancellation

    def button_cancel(self):
        """A cancelled bill releases its equipment links; draft equipment without serial
        number it created are archived, not deleted."""
        for move in self.filtered(lambda m: m.move_type == "in_invoice"):
            for line in move.invoice_line_ids.filtered("equipment_ids"):
                linked = line.equipment_ids
                # recorded before the link disappears
                linked.sudo()._cost_after_bill_unlink(move, "bill_cancelled")
                line._unlink_equipment(linked)
                linked.filtered(
                    lambda e: not e.stock_lot_id and e.integration_state == "draft"
                ).sudo().write({"active": False})
        return super().button_cancel()

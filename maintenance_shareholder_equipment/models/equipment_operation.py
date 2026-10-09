import json

import psycopg2

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .maintenance_equipment import INSURANCE_STATUS, THIRD_PARTY_OWNED, WARRANTY_STATUS

OPERATION_TYPES = [
    ("receipt", "Receipt"),
    ("exit", "Exit to a Third Party"),
    ("return", "Return from a Third Party"),
    ("restitution", "Restitution to the Owner"),
]
RECEIPT_BRANCHES = [
    ("purchase", "Purchase"),
    ("acquisition", "Acquisition without Purchase"),
    ("borrowed", "Borrowed"),
    ("rented", "Rented"),
]
ACQUISITION_NATURES = [
    ("gift", "Gift"),
    ("current_account", "Contribution to a Shareholder Current Account"),
    ("regularisation", "Regularisation"),
]
STATES = [
    ("draft", "Draft"),
    ("to_approve", "To Approve"),
    ("approved", "Approved"),
    ("processing", "Processing"),
    ("done", "Done"),
    ("cancel", "Cancelled"),
]
PERIODICITY = [
    ("monthly", "Month(s)"),
    ("quarterly", "Quarter(s)"),
    ("yearly", "Year(s)"),
]
OPERATOR_GROUP = "maintenance_shareholder_equipment.group_equipment_operator"
APPROVER_GROUP = "maintenance_shareholder_equipment.group_equipment_approver"
# Written only by the operation's own methods (superuser mode), never directly.
PROTECTED_FIELDS = {
    "state", "approver_id", "approval_date", "approval_snapshot", "executor_id",
    "execution_date", "picking_ids", "purchase_created_id", "bill_ids", "contract_ids",
}


class EquipmentOperation(models.Model):
    """Business document of every entry, exit, return and restitution of equipment and
    consumables (phase 2, docs/phase2/PLAN.md). Approval and execution are separate:
    the approver authorises the commitments, the operator executes the physical
    movement; both run in one transaction each."""

    _name = "equipment.operation"
    _description = "Equipment Operation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(readonly=True, copy=False, default="/")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    operation_type = fields.Selection(OPERATION_TYPES, required=True, default="receipt", tracking=True)
    receipt_branch = fields.Selection(RECEIPT_BRANCHES, string="Receipt Type", tracking=True)
    acquisition_nature = fields.Selection(ACQUISITION_NATURES, tracking=True)
    state = fields.Selection(STATES, default="draft", required=True, readonly=True,
                             copy=False, tracking=True, index=True)
    date = fields.Date(
        string="Planned Date", default=fields.Date.context_today, required=True,
        help="Date of the physical event. The stock is recorded at execution, on the "
        "execution date.",
    )
    requester_id = fields.Many2one("res.users", string="Requester", required=True,
                                   default=lambda self: self.env.user)
    approver_id = fields.Many2one("res.users", readonly=True, copy=False)
    approval_date = fields.Datetime(readonly=True, copy=False)
    approval_snapshot = fields.Text(readonly=True, copy=False, groups="base.group_system")
    executor_id = fields.Many2one("res.users", string="Executed by", readonly=True, copy=False)
    execution_date = fields.Datetime(readonly=True, copy=False)
    note = fields.Text()
    attachment_ids = fields.Many2many(
        "ir.attachment", "equipment_operation_attachment_rel", "operation_id",
        "attachment_id", string="Documents",
    )

    partner_id = fields.Many2one(
        "res.partner", string="Partner", check_company=True,
        help="Vendor, donor or contributor, owner, lessor or third party, according "
        "to the operation.",
    )
    company_partner_id = fields.Many2one(related="company_id.partner_id",
                                         string="Company Partner")
    site_partner_id = fields.Many2one(
        "res.partner", string="Site Address",
        help="Address of the third party where the equipment is held.",
    )
    picking_type_id = fields.Many2one(
        "stock.picking.type", string="Transfer Type", check_company=True,
        compute="_compute_picking_type_id", store=True, readonly=False, precompute=True,
        help="Set automatically: the order's receipt type, otherwise the receipt type "
        "of the warehouse delivering the destination stock, the internal transfer for an "
        "exit or a return, the delivery for a restitution.",
    )
    location_dest_id = fields.Many2one(
        "stock.location", string="Destination Stock", check_company=True,
        help="Receipt: internal stock receiving the items (non-stock equipment: its "
        "location).",
    )

    # purchase
    purchase_mode = fields.Selection([("existing", "Existing Order"), ("create", "Create the Order")],
                                     default="existing")
    purchase_id = fields.Many2one("purchase.order", string="Purchase Order", check_company=True)
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id,
    )
    bill_mode = fields.Selection(
        [("none", "No Bill"), ("existing", "Bill Already Received"),
         ("create", "Create a Draft Bill")], default="none",
        help="Bill Already Received: the bills of the order lines received (posted before "
        "the receipt) are linked to the operation; at least one is required.",
    )
    bill_ref = fields.Char(string="Vendor Bill Reference")
    bill_date = fields.Date(string="Bill Date")
    bill_attachment_ids = fields.Many2many(
        "ir.attachment", "equipment_operation_bill_attachment_rel", "operation_id",
        "attachment_id", string="Bill (PDF)",
    )

    # contract (borrowed, rented, exit)
    contract_mode = fields.Selection([("existing", "Existing Contract"), ("new", "New Contract")],
                                     default="new")
    contract_id = fields.Many2one("contract.contract", string="Contract", check_company=True)
    exit_nature = fields.Selection([("loan", "Free Loan"), ("rental", "Rented Out")])
    contract_start = fields.Date()
    contract_end = fields.Date(string="Planned End")
    open_ended = fields.Boolean(string="Open-Ended")
    periodicity = fields.Selection(PERIODICITY, default="monthly")
    contract_attachment_ids = fields.Many2many(
        "ir.attachment", "equipment_operation_contract_attachment_rel", "operation_id",
        "attachment_id", string="Contract Documents",
    )

    # exit
    offsite_location_id = fields.Many2one(
        "stock.location", string="Off-Site Stock", check_company=True,
        domain="[('place_type', '=', 'lent_out'), ('usage', '=', 'internal')]",
    )
    new_location_name = fields.Char(
        string="New Off-Site Stock",
        help="Fill to create the off-site stock at execution, instead of choosing one.",
    )
    new_location_parent_id = fields.Many2one(
        "stock.location", string="Parent of the New Stock", check_company=True,
        domain="[('is_offsite_parent', '=', True)]",
    )

    line_ids = fields.One2many("equipment.operation.line", "operation_id", string="Lines",
                               copy=True)
    stop_line_ids = fields.One2many("equipment.operation.stop", "operation_id",
                                    string="Contract Lines to Stop")
    picking_ids = fields.One2many("stock.picking", "equipment_operation_id", readonly=True)
    purchase_created_id = fields.Many2one("purchase.order", readonly=True, copy=False)
    bill_ids = fields.Many2many("account.move", string="Bills", readonly=True, copy=False,
                                help="Draft bill created by the operation, or bills already "
                                "received for the lines it received.")
    contract_ids = fields.Many2many("contract.contract", string="Contracts", readonly=True,
                                    copy=False)
    needs_approval = fields.Boolean(compute="_compute_needs_approval")

    # ------------------------------------------------------------ form helpers

    PICKING_CODES = {"receipt": "incoming", "exit": "internal", "return": "internal",
                     "restitution": "outgoing"}

    @api.depends("operation_type", "receipt_branch", "purchase_mode", "purchase_id",
                 "location_dest_id", "company_id")
    def _compute_picking_type_id(self):
        Type = self.env["stock.picking.type"]
        for op in self:
            if op.operation_type == "receipt" and op.receipt_branch == "purchase" \
                    and op.purchase_mode == "existing" and op.purchase_id:
                op.picking_type_id = op.purchase_id.picking_type_id
                continue
            # active types first; Odoo archives the internal type when storage
            # locations are off, it still works for the operation's transfers
            types = Type.with_context(active_test=False).search(
                [("code", "=", self.PICKING_CODES[op.operation_type]),
                 ("company_id", "=", op.company_id.id)], order="active desc, sequence, id")
            dest = op.location_dest_id if op.operation_type == "receipt" else False
            match = types.filtered(
                lambda t: dest and t.default_location_dest_id
                and dest.parent_path.startswith(t.default_location_dest_id.parent_path)
            )
            # keep a type chosen by hand when it is still of the right kind
            if op.picking_type_id in types and not match:
                continue
            op.picking_type_id = (match or types)[:1]

    @api.onchange("purchase_id")
    def _onchange_purchase_id(self):
        """Choosing an order fills the vendor, the destination and one line per unit of
        equipment (one line per product otherwise) for what is left to receive."""
        order = self.purchase_id
        if not order:
            return
        self.partner_id = order.partner_id
        if not self.location_dest_id:
            self.location_dest_id = order.picking_type_id.default_location_dest_id
        commands = [Command.clear()]
        for pol in order.order_line.filtered(lambda pl: not pl.display_type):
            product = pol.product_id
            left = pol.product_qty - pol.qty_received
            if left <= 0 or (product.type == "service" and not product.maintenance_ok):
                continue
            base = {"product_id": product.id, "purchase_line_id": pol.id,
                    "warranty_status": product.categ_id.default_warranty_status,
                    "insurance_status": product.categ_id.default_insurance_status}
            if product.maintenance_ok:
                commands += [Command.create(dict(base, quantity=1, quantity_done=1))
                             for _i in range(int(left))]
            else:
                commands.append(Command.create(dict(base, quantity=left, quantity_done=left)))
        self.line_ids = commands

    # --------------------------------------------------------------- protection

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if PROTECTED_FIELDS.intersection(vals) and not self.env.su:
                raise AccessError(_("This field is set by the operation itself."))
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code("equipment.operation") or "/"
        operations = super().create(vals_list)
        operations._attach_documents()
        return operations

    def write(self, vals):
        if PROTECTED_FIELDS.intersection(vals) and not self.env.su:
            raise AccessError(_("This field is set by the operation itself."))
        if not self.env.su and any(op.state in ("processing", "done", "cancel") for op in self):
            raise UserError(_("An executed or cancelled operation cannot be changed."))
        res = super().write(vals)
        self._attach_documents()
        self._invalidate_changed_approvals()
        return res

    def unlink(self):
        if any(op.state not in ("draft", "cancel") for op in self):
            raise UserError(_("Only draft or cancelled operations can be deleted."))
        return super().unlink()

    def _attach_documents(self):
        """Uploaded files belong to the operation, so that the access rules of the
        operation protect them. A client may only bring files it uploaded itself for
        this operation (or not yet attached to anything) and can read: any other
        attachment id sent through the API is refused before the elevated write."""
        for op in self:
            op_su = op.sudo()
            files = (op_su.attachment_ids | op_su.bill_attachment_ids
                     | op_su.contract_attachment_ids | op_su.line_ids.attachment_ids)
            new = files.filtered(lambda a: a.res_model != op._name or a.res_id != op.id)
            if not new:
                continue
            if not self.env.su:
                own_ids = {op._name: {op.id}, "equipment.operation.line": set(op_su.line_ids.ids)}
                for attachment in new:
                    if attachment.res_id:
                        allowed = attachment.res_id in own_ids.get(attachment.res_model, ())
                    else:  # fresh upload: only by the current user, for this model or none
                        allowed = attachment.create_uid == self.env.user and (
                            attachment.res_model in (False, op._name, "equipment.operation.line"))
                    if not allowed:
                        raise AccessError(_("Attachment %s cannot be added to this operation.",
                                            attachment.name))
                    attachment.with_env(self.env).check_access("read")
            new.write({"res_model": op._name, "res_id": op.id})

    # ------------------------------------------------------------------ approval

    @api.depends("operation_type", "receipt_branch", "purchase_mode", "bill_mode",
                 "contract_mode", "stop_line_ids.to_stop", "stop_line_ids.nature")
    def _compute_needs_approval(self):
        for op in self:
            op.needs_approval = op._needs_approval()

    def _needs_approval(self):
        """Financial or legal commitments (PLAN.md, section 7)."""
        self.ensure_one()
        if self.operation_type == "receipt":
            if self.receipt_branch == "purchase":
                return self.purchase_mode == "create" or self.bill_mode == "create"
            if self.receipt_branch == "borrowed":
                return self.contract_mode != "existing"
            return self.receipt_branch in ("acquisition", "rented")
        if self.operation_type == "exit":
            return True
        # return, restitution: stopping anything else than a free loan
        return any(
            stop.nature != "loan" for stop in self.stop_line_ids if stop._will_stop()
        )

    def _commitment_snapshot(self):
        """Everything the approver authorises. Any difference afterwards, through the
        header, the lines or the API, cancels the approval."""
        self.ensure_one()
        op = self.sudo()

        def ids(records):
            return sorted(records.ids)

        data = {
            "type": op.operation_type, "branch": op.receipt_branch,
            "nature": op.acquisition_nature, "company": op.company_id.id,
            "partner": op.partner_id.id, "site": op.site_partner_id.id,
            "purchase_mode": op.purchase_mode, "purchase": op.purchase_id.id,
            "currency": op.currency_id.id, "bill_mode": op.bill_mode,
            "bill_ref": op.bill_ref, "bill_date": str(op.bill_date or ""),
            "contract_mode": op.contract_mode, "contract": op.contract_id.id,
            "exit_nature": op.exit_nature, "start": str(op.contract_start or ""),
            "end": str(op.contract_end or ""), "open_ended": op.open_ended,
            "periodicity": op.periodicity, "offsite": op.offsite_location_id.id,
            "new_location": op.new_location_name or "",
            "lines": sorted(
                [
                    [line.product_id.id, line.quantity, line.price_unit, ids(line.tax_ids),
                     line.purchase_line_id.id, line.purchase_line_id.price_unit,
                     ids(line.purchase_line_id.taxes_id), line.unit_value, line.replacement_value,
                     line.replacement_currency_id.id, str(line.replacement_value_date or ""),
                     line.rent_amount, line.equipment_id.id if op.operation_type != "receipt" else 0]
                    for line in op.line_ids
                ],
                key=lambda row: json.dumps(row),
            ),
            "stops": sorted(
                [[stop.contract_line_id.id, stop._will_stop()] for stop in op.stop_line_ids]
            ),
        }
        return json.dumps(data, sort_keys=True)

    def _invalidate_changed_approvals(self):
        for op in self.filtered(lambda o: o.state == "approved"):
            if op._commitment_snapshot() != op.sudo().approval_snapshot:
                op.sudo().write({"state": "draft", "approver_id": False,
                                 "approval_date": False, "approval_snapshot": False})
                op.message_post(body=_("Approval cancelled: the commitments changed."))

    def _is_operator(self):
        return self.env.su or self.env.user.has_group(OPERATOR_GROUP)

    def _is_approver(self):
        return self.env.su or self.env.user.has_group(APPROVER_GROUP)

    def action_submit(self):
        self._lock()
        for op in self:
            if not op._is_operator():
                raise AccessError(_("Only equipment operators can submit an operation."))
            if op.state != "draft":
                raise UserError(_("%s is not a draft.", op.name))
            op._refresh_stop_lines()
            op._check_values()
            if not op._needs_approval():
                raise UserError(_("%s needs no approval: execute it.", op.name))
            op.sudo().write({"state": "to_approve"})
            op._notify_approvers()
        return True

    def action_approve(self):
        self._lock()
        for op in self:
            if not op._is_approver():
                raise AccessError(_("Only equipment operation approvers can approve."))
            if op.state not in ("draft", "to_approve"):
                raise UserError(_("%s cannot be approved in its current state.", op.name))
            op._refresh_stop_lines()
            op._check_values()
            op.sudo().write({
                "state": "approved", "approver_id": self.env.user.id,
                "approval_date": fields.Datetime.now(),
                "approval_snapshot": op._commitment_snapshot(),
            })
            op.activity_unlink(["mail.mail_activity_data_todo"])
            op.message_post(body=_("Approved by %s.", self.env.user.name))
        return True

    def action_reset_draft(self):
        for op in self:
            if op.state not in ("to_approve", "approved"):
                raise UserError(_("%s cannot go back to draft.", op.name))
            if not (op._is_operator() or op._is_approver()):
                raise AccessError(_("Not allowed."))
            op.sudo().write({"state": "draft", "approver_id": False, "approval_date": False,
                             "approval_snapshot": False})
        return True

    def action_cancel(self):
        for op in self:
            if op.state not in ("draft", "to_approve", "approved"):
                raise UserError(_("%s cannot be cancelled.", op.name))
            if not (op._is_operator() or op._is_approver()):
                raise AccessError(_("Not allowed."))
            op.sudo().write({"state": "cancel"})
        return True

    def _notify_approvers(self):
        approvers = self.env.ref(APPROVER_GROUP).sudo().users.filtered(
            lambda u: self.company_id in u.company_ids
        )
        for user in approvers:
            self.activity_schedule(
                "mail.mail_activity_data_todo", user_id=user.id,
                summary=_("Equipment operation to approve"),
            )

    def _lock(self):
        """Row lock on the operations: a concurrent approval or execution of the same
        operation fails instead of running twice (read lock, no SQL write)."""
        if not self.ids:
            return
        try:
            self.env.cr.execute(
                "SELECT id FROM equipment_operation WHERE id IN %s FOR UPDATE NOWAIT",
                [tuple(self.ids)],
            )
        except psycopg2.errors.LockNotAvailable:
            raise UserError(_("This operation is being processed by someone else.")) from None
        self.invalidate_recordset()

    # ----------------------------------------------------------------- execution

    def action_execute(self):
        """One transaction: any failure rolls everything back (PLAN.md, section 3)."""
        self._lock()
        for op in self:
            if not op._is_operator():
                raise AccessError(_("Only equipment operators can execute an operation."))
            if op.state not in ("draft", "approved"):
                raise UserError(_("%s is already executed or being executed.", op.name))
            was_approved = op.state == "approved"
            op._refresh_stop_lines()
            if was_approved and op.state == "draft":
                # the contract lines changed since the approval: stop here (no error, so
                # that the cancellation of the approval is kept), to be reviewed again
                continue
            op._check_values()
            op._check_user_access()
            if op.state == "draft" and op._needs_approval():
                if not op._is_approver():
                    op.sudo().write({"state": "to_approve"})
                    op._notify_approvers()
                    continue
                op.action_approve()
            if op.state == "approved" and op._commitment_snapshot() != op.sudo().approval_snapshot:
                raise UserError(_("%s changed since its approval.", op.name))
            op.sudo()._execute()
        return True

    def _execute(self):
        self.ensure_one()
        self.write({"state": "processing", "executor_id": self.env.uid,
                    "execution_date": fields.Datetime.now()})
        getattr(self, "_execute_%s" % self.operation_type)()
        self._check_final_consistency()
        self.write({"state": "done"})
        self.message_post(body=_("Executed by %s.", self.env.user.name))

    @property
    def _today(self):
        return fields.Date.context_today(self)

    # receipt -------------------------------------------------------------------

    def _execute_receipt(self):
        if self.receipt_branch == "purchase" and self.purchase_mode == "create":
            self._create_purchase_order()
        lines = self.line_ids.filtered(lambda ln: ln._qty_executed() > 0)
        if not lines:
            raise UserError(_("Nothing to execute: every executed quantity is 0."))
        equipment_lines = lines.filtered(lambda ln: ln.family in ("equipment", "non_stock"))
        for line in lines.filtered(lambda ln: ln.family == "equipment"):
            line._ensure_lot()
        for line in equipment_lines:
            line._prepare_equipment()
        moved = lines.filtered(lambda ln: ln._needs_move())
        if moved:
            picking = (self._take_over_purchase_receipt(moved) if self.receipt_branch == "purchase"
                       else self._new_incoming_picking(moved))
            self._fill_and_validate(picking, moved)
        for line in equipment_lines:
            line.equipment_id.action_finalize_integration()
        if self.receipt_branch == "purchase" and self.bill_mode == "create":
            self._create_draft_bill(lines)
        if self.receipt_branch == "purchase" and self.bill_mode == "existing":
            bills = self._received_bills(lines)
            if not bills:
                raise UserError(_("No bill already received for the lines executed by %s.",
                                  self.name))
            self.write({"bill_ids": [Command.link(bill.id) for bill in bills]})
        if self.receipt_branch in ("borrowed", "rented"):
            nature = "loan" if self.receipt_branch == "borrowed" else "rental"
            product = self._contract_product(nature, "purchase")
            self._add_contract_lines("purchase", equipment_lines, nature, product)

    def _received_bills(self, lines):
        """Supplier bills (not cancelled) already carrying the order lines received."""
        return self.env["account.move"].search([
            ("move_type", "=", "in_invoice"), ("state", "!=", "cancel"),
            ("company_id", "=", self.company_id.id),
            ("invoice_line_ids.purchase_line_id", "in", lines.purchase_line_id.ids),
        ])

    def _purchase(self):
        return self.purchase_created_id or self.purchase_id

    def _create_purchase_order(self):
        groups = {}
        for line in self.line_ids:
            key = (line.product_id.id, line.price_unit, tuple(sorted(line.tax_ids.ids)))
            groups.setdefault(key, self.env["equipment.operation.line"])
            groups[key] |= line
        order = self.env["purchase.order"].create({
            "partner_id": self.partner_id.id,
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "picking_type_id": self.picking_type_id.id,
            "origin": self.name,
            "order_line": [
                Command.create({
                    "product_id": product_id, "product_qty": sum(group.mapped("quantity")),
                    "price_unit": price, "taxes_id": [Command.set(list(taxes))],
                })
                for (product_id, price, taxes), group in groups.items()
            ],
        })
        order.button_confirm()
        if order.state != "purchase":
            raise UserError(_("The purchase order %s could not be confirmed.", order.name))
        for (product_id, price, taxes), group in groups.items():
            po_line = order.order_line.filtered(
                lambda pl: pl.product_id.id == product_id and pl.price_unit == price
                and tuple(sorted(pl.taxes_id.ids)) == taxes
            )[:1]
            group.write({"purchase_line_id": po_line.id})
        self.write({"purchase_created_id": order.id})
        self.message_post(body=_("Purchase order %s created and confirmed.",
                                 order._get_html_link()))

    def _take_over_purchase_receipt(self, lines):
        """The receipt generated by the order: never a second one."""
        order = self._purchase()
        moves = order.order_line.move_ids.filtered(
            lambda m: m.state not in ("done", "cancel") and m.picking_id
            and m.picking_code == "incoming"
        )
        if moves.move_dest_ids:
            raise UserError(_("The receipt of %s is chained to other transfers (receipt in "
                              "several steps): not supported.", order.name))
        wanted = lines.purchase_line_id
        pickings = moves.filtered(lambda m: m.purchase_line_id in wanted).picking_id
        if len(pickings) != 1:
            raise UserError(_("Exactly one open receipt of %(order)s is expected for these "
                              "lines, found %(count)s.", order=order.name, count=len(pickings)))
        return pickings

    def _new_incoming_picking(self, lines):
        if self.receipt_branch == "acquisition":
            source = self._acquisition_location()
        else:
            source = self.partner_id.with_company(self.company_id).property_stock_supplier
        owner = self.partner_id if self.receipt_branch in ("borrowed", "rented") else False
        picking = self.env["stock.picking"].create({
            "picking_type_id": self.picking_type_id.id,
            "location_id": source.id,
            "location_dest_id": self.location_dest_id.id,
            "partner_id": self.partner_id.id,
            "owner_id": owner and owner.id,
            "origin": self.name,
            "company_id": self.company_id.id,
            "move_ids": [
                Command.create({
                    "name": line.product_id.display_name, "product_id": line.product_id.id,
                    "product_uom_qty": line.quantity, "product_uom": line.product_id.uom_id.id,
                    "location_id": source.id, "location_dest_id": self.location_dest_id.id,
                    "price_unit": line.unit_value if self.receipt_branch == "acquisition" else 0.0,
                    "company_id": self.company_id.id,
                })
                for line in lines
            ],
        })
        picking.action_confirm()
        return picking

    def _fill_and_validate(self, picking, lines):
        """Link the picking to the operation, set its move lines from the operation
        lines (serial numbers, owner, quantities executed), then validate it."""
        picking.write({"equipment_operation_id": self.id, "scheduled_date": fields.Datetime.now()})
        dest = self.location_dest_id
        if picking.picking_type_code == "incoming" and dest:
            picking.write({"location_dest_id": dest.id})
            picking.move_ids.filtered(lambda m: m.state not in ("done", "cancel")).write(
                {"location_dest_id": dest.id})
        picking.move_ids.write({"equipment_operation_id": self.id})
        picking.move_ids.move_line_ids.unlink()
        MoveLine = self.env["stock.move.line"]
        for line in lines:
            move = line._find_move(picking)
            qty = 1 if line.family != "consumable" else line._qty_executed()
            if not qty:
                continue
            MoveLine.create({
                "move_id": move.id, "picking_id": picking.id, "product_id": line.product_id.id,
                "lot_id": (line.lot_id or line.equipment_id.stock_lot_id).id or False,
                "quantity": qty,
                "product_uom_id": move.product_uom.id,
                "location_id": line._source_location(move).id,
                "location_dest_id": line._destination_location(move).id,
                "owner_id": picking.owner_id.id or False,
                "picked": True,
            })
            move.picked = True
        res = picking.with_context(skip_backorder=True, skip_sms=True).button_validate()
        if res is not True and picking.state != "done":
            raise UserError(_("The transfer %s could not be validated.", picking.name))
        for attachment in self.attachment_ids:
            attachment.copy({"res_model": "stock.picking", "res_id": picking.id})
        self.message_post(body=_("Transfer %s validated.", picking._get_html_link()))
        return picking

    def _create_draft_bill(self, lines):
        """Draft bill of the lines and quantities of this operation only, never of
        other billable lines of the order (they were not approved here)."""
        order = self._purchase()
        bill_lines = []
        for pol in lines.purchase_line_id:
            executed = sum(ln._qty_executed() for ln in lines if ln.purchase_line_id == pol)
            basis = pol.qty_received if pol.product_id.purchase_method == "receive" \
                else pol.product_qty
            qty = min(executed, basis - pol.qty_invoiced)
            if qty <= 0:
                continue
            vals = pol._prepare_account_move_line()
            vals["quantity"] = qty
            bill_lines.append(Command.create(vals))
        if not bill_lines:
            raise UserError(_("No bill could be created from %s.", order.name))
        vals = order.with_company(self.company_id)._prepare_invoice()
        vals.update(ref=self.bill_ref, invoice_date=self.bill_date, invoice_line_ids=bill_lines)
        bill = self.env["account.move"].with_company(self.company_id).with_context(
            default_move_type="in_invoice").create(vals)
        for attachment in self.bill_attachment_ids:
            attachment.copy({"res_model": "account.move", "res_id": bill.id})
        self.write({"bill_ids": [Command.link(bill.id)]})
        bill.message_post(body=_("Draft bill created by %s, to be checked and posted by the "
                                 "accountant.", self._get_html_link()))

    # exit / return / restitution ----------------------------------------------

    def _execute_exit(self):
        offsite = self.offsite_location_id or self._create_offsite_location()
        for line in self.line_ids:
            line.origin_location_id = line._current_location()
        for line in self.line_ids:
            line.equipment_id._set_ownership(
                "lent_out", self.company_id.partner_id, _("%s (exit)", self.name)
            )
        stock_lines = self.line_ids.filtered(lambda ln: ln.equipment_id.stock_lot_id)
        for line in self.line_ids - stock_lines:
            line.equipment_id.write({"current_location_id": offsite.id})
        if stock_lines:
            picking = self._new_internal_picking(stock_lines, offsite)
            self._fill_and_validate(picking, stock_lines)
        nature = self.exit_nature
        self._add_contract_lines("sale", self.line_ids, nature, self._contract_product(nature, "sale"))
        self._copy_line_documents()

    def _create_offsite_location(self):
        first = self.line_ids[:1]._current_location()
        location = self.env["stock.location"].create({
            "name": self.new_location_name,
            "location_id": self.new_location_parent_id.id,
            "usage": "internal",
            "place_type": "lent_out",
            "address_id": self.site_partner_id.id,
            "return_location_id": first.id,
            "company_id": self.company_id.id,
        })
        self.write({"offsite_location_id": location.id})
        return location

    def _execute_return(self):
        for line in self.line_ids:
            line.origin_location_id = line._current_location()
            line.equipment_id._set_ownership(
                "owned", self.company_id.partner_id, _("%s (return)", self.name)
            )
        stock_lines = self.line_ids.filtered(lambda ln: ln.equipment_id.stock_lot_id)
        for line in self.line_ids - stock_lines:
            line.equipment_id.write({"current_location_id": line.dest_location_id.id})
        if stock_lines:
            picking = self._new_internal_picking(stock_lines, None)
            self._fill_and_validate(picking, stock_lines)
        self._stop_contract_lines()
        self._copy_line_documents()

    def _execute_restitution(self):
        stock_lines = self.line_ids.filtered(lambda ln: ln.equipment_id.stock_lot_id)
        for line in self.line_ids:
            line.origin_location_id = line._current_location()
        if stock_lines:
            owner = self.partner_id
            dest = owner.with_company(self.company_id).property_stock_supplier
            picking = self.env["stock.picking"].create({
                "picking_type_id": self.picking_type_id.id,
                "location_id": stock_lines[0].origin_location_id.id,
                "location_dest_id": dest.id,
                "partner_id": owner.id, "owner_id": owner.id, "origin": self.name,
                "company_id": self.company_id.id,
                "move_ids": [Command.create(line._move_vals(line.origin_location_id, dest))
                             for line in stock_lines],
            })
            picking.action_confirm()
            self._fill_and_validate(picking, stock_lines)
        self._stop_contract_lines()
        self._copy_line_documents()
        for line in self.line_ids:
            equipment = line.equipment_id
            if equipment._internal_quants():
                raise UserError(_("%s is still in an internal stock.", equipment.display_name))
            equipment.message_post(body=_("Returned to its owner by %s.", self._get_html_link()))
            equipment.write({"active": False})

    def _new_internal_picking(self, lines, dest):
        moves = []
        for line in lines:
            target = dest or line.dest_location_id
            moves.append(Command.create(line._move_vals(line.origin_location_id, target)))
        picking = self.env["stock.picking"].create({
            "picking_type_id": self.picking_type_id.id,
            "location_id": lines[0].origin_location_id.id,
            "location_dest_id": (dest or lines[0].dest_location_id).id,
            "partner_id": self.partner_id.id, "origin": self.name,
            "company_id": self.company_id.id,
            "move_ids": moves,
        })
        picking.action_confirm()
        return picking

    def _stop_contract_lines(self):
        date = self._today
        for stop in self.stop_line_ids.filtered(lambda s: s._will_stop()):
            contract_line = stop.contract_line_id
            if contract_line.date_end and contract_line.date_end <= date:
                continue
            contract_line.stop(date)
            contract_line.contract_id.message_post(
                body=_("Line %(line)s stopped by %(op)s.", line=contract_line.display_name,
                       op=self._get_html_link())
            )

    def _copy_line_documents(self):
        for line in self.line_ids:
            line._post_on_equipment()

    # contracts ------------------------------------------------------------------

    def _contract_product(self, nature, contract_type):
        company = self.company_id
        if nature == "loan":
            return company.equipment_loan_product_id
        if contract_type == "purchase":
            return company.equipment_rent_paid_product_id
        return company.equipment_rent_received_product_id

    def _contract_line_vals(self, line, nature, product):
        start = self.contract_start or self._today
        return {
            "product_id": product.id,
            "name": "%s – %s" % (product.display_name, line.equipment_id.display_name),
            "quantity": 1,
            "uom_id": product.uom_id.id,
            "price_unit": line.rent_amount if nature == "rental" else 0.0,
            "recurring_rule_type": self.periodicity or "monthly",
            "recurring_interval": 1,
            "date_start": start,
            "date_end": False if self.open_ended else self.contract_end,
            "recurring_next_date": start,
            "equipment_id": line.equipment_id.id,
            "equipment_nature": nature,
        }

    def _add_contract_lines(self, contract_type, lines, nature, product):
        if not lines:
            return
        vals = [Command.create(self._contract_line_vals(line, nature, product)) for line in lines]
        if self.contract_mode == "existing" and self.contract_id and contract_type == "purchase":
            contract = self.contract_id
            contract.write({"contract_line_ids": vals})
        else:
            contract = self.env["contract.contract"].create({
                "name": "%s – %s" % (self.name, self.partner_id.display_name),
                "partner_id": self.partner_id.commercial_partner_id.id,
                "contract_type": contract_type,
                "company_id": self.company_id.id,
                "line_recurrence": True,
                "contract_line_ids": vals,
            })
        for attachment in self.contract_attachment_ids:
            attachment.copy({"res_model": "contract.contract", "res_id": contract.id})
        self.write({"contract_ids": [Command.link(contract.id)]})
        contract.message_post(body=_("Lines added by %(op)s (operator %(user)s).",
                                     op=self._get_html_link(), user=self.env.user.name))

    # ------------------------------------------------------------------- checks

    def _check_values(self):
        """Server-side checks of everything the client sent (PLAN.md, section 6)."""
        self.ensure_one()
        op = self.sudo()
        company = op.company_id
        errors = []

        def need(value, label):
            if not value:
                errors.append(label)

        def same_company(record, label):
            for rec in record:
                if "company_id" in rec._fields and rec.company_id and rec.company_id != company:
                    raise ValidationError(_("%(label)s %(name)s belongs to another company.",
                                            label=label, name=rec.display_name))

        if not op.line_ids:
            errors.append(_("at least one line"))
        same_company(op.partner_id, _("Partner"))
        same_company(op.picking_type_id, _("Operation type"))
        same_company(op.location_dest_id, _("Stock"))
        same_company(op.line_ids.product_id, _("Product"))
        if op.partner_id and not op.partner_id.active:
            raise ValidationError(_("The partner is archived."))
        own = op.partner_id and op.partner_id.commercial_partner_id == company.partner_id
        if own and (op.operation_type != "receipt" or op.receipt_branch != "acquisition"):
            raise ValidationError(_("The partner cannot be the company itself."))
        for line in op.line_ids:
            if not line.product_id.active:
                raise ValidationError(_("Product %s is archived.", line.product_id.display_name))
            if line.quantity <= 0 or line.quantity_done < 0 or line.quantity_done > line.quantity:
                raise ValidationError(_("Line %s: quantities must be positive and the quantity "
                                        "executed cannot exceed the quantity approved.",
                                        line.product_id.display_name))
            if op.operation_type != "receipt" and line.quantity_done != line.quantity:
                raise ValidationError(_("Line %s: an exit, return or restitution moves the "
                                        "whole equipment.", line.product_id.display_name))
            for amount in (line.price_unit, line.unit_value, line.replacement_value, line.rent_amount):
                if amount < 0:
                    raise ValidationError(_("Line %s: amounts cannot be negative.",
                                            line.product_id.display_name))
            if line.family in ("equipment", "non_stock") and line.quantity != 1:
                raise ValidationError(_("One line per equipment unit (quantity 1)."))
            if line.replacement_currency_id and not line.replacement_currency_id.active:
                raise ValidationError(_("Currency %s is not active.", line.replacement_currency_id.name))
        getattr(op, "_check_values_%s" % op.operation_type)(errors, need)
        if errors:
            raise ValidationError(_("%(op)s cannot be validated, missing or invalid: %(list)s",
                                    op=op.name, list=", ".join(str(e) for e in errors)))

    def _check_values_receipt(self, errors, need):
        need(self.receipt_branch, _("receipt type"))
        need(self.picking_type_id, _("operation type"))
        need(self.location_dest_id, _("destination stock"))
        if self.picking_type_id and self.picking_type_id.code != "incoming":
            raise ValidationError(_("Choose a receipt operation type."))
        warehouse = self.picking_type_id.warehouse_id
        if warehouse and warehouse.reception_steps != "one_step":
            raise ValidationError(_("Warehouse %s receives in several steps: not supported by "
                                    "the equipment operations (one-step receipts only).",
                                    warehouse.name))
        dest = self.location_dest_id
        if dest and not (dest.active and dest.usage == "internal" and dest.place_type == "physical"):
            raise ValidationError(_("The destination must be an active internal physical stock."))
        branch = self.receipt_branch
        third_party = branch in ("borrowed", "rented")
        if branch in ("purchase", "borrowed", "rented"):
            need(self.partner_id, _("partner"))
        if branch == "acquisition":
            need(self.acquisition_nature, _("nature of the acquisition"))
            if self.acquisition_nature in ("gift", "current_account"):
                need(self.partner_id, _("donor or contributor"))
            if self.acquisition_nature and not self._acquisition_location():
                errors.append(_("acquisition location in the settings"))
        if branch == "purchase":
            self._check_purchase(errors, need)
        if third_party:
            self._check_third_party_contract(errors, need)
        for line in self.line_ids:
            label = line.product_id.display_name
            if third_party and line.family == "consumable":
                raise ValidationError(_("%s: consumables are always owned (v1).", label))
            if line.family == "consumable" and branch == "acquisition" \
                    and not line.product_id.is_storable:
                raise ValidationError(_("%s: only storable consumables.", label))
            if line.family in ("equipment", "non_stock"):
                need(line.warranty_status, _("%s: warranty status", label))
                need(line.insurance_status, _("%s: insurance status", label))
                if third_party:
                    need(line.replacement_value and line.replacement_currency_id
                         and line.replacement_value_date, _("%s: replacement value, currency and date", label))
                if line.family == "equipment":
                    need(line.lot_name or line.lot_generate or line.equipment_id.stock_lot_id,
                         _("%s: serial number", label))
                    line._check_serial_free()
                if line.equipment_id:
                    line._check_receipt_equipment()
            if branch == "acquisition":
                need(line.unit_value or line.family == "non_stock", _("%s: unit value", label))
            if branch == "rented":
                need(line.rent_amount, _("%s: rent", label))

    def _check_purchase(self, errors, need):
        need(self.purchase_mode, _("existing or new purchase order"))
        if self.purchase_mode == "existing":
            order = self.purchase_id
            need(order, _("purchase order"))
            if order:
                if order.state != "purchase":
                    raise ValidationError(_("The purchase order must be confirmed."))
                if order.partner_id.commercial_partner_id != self.partner_id.commercial_partner_id:
                    raise ValidationError(_("The purchase order belongs to another vendor."))
                for line in self.line_ids:
                    pol = line.purchase_line_id
                    if pol.order_id != order or pol.product_id != line.product_id:
                        raise ValidationError(_("%s: choose a line of the purchase order.",
                                                line.product_id.display_name))
                for pol in self.line_ids.purchase_line_id:
                    lines = self.line_ids.filtered(lambda ln: ln.purchase_line_id == pol)
                    left = pol.product_qty - pol.qty_received
                    if sum(lines.mapped("quantity")) > left + 1e-6:
                        raise ValidationError(_("%(product)s: more than the %(left)s left to "
                                                "receive.", product=pol.product_id.display_name,
                                                left=left))
        elif self.purchase_mode == "create":
            need(self.currency_id, _("currency"))
            if self.currency_id and not self.currency_id.active:
                raise ValidationError(_("The currency is not active."))
            for line in self.line_ids:
                if not line.product_id.purchase_ok:
                    raise ValidationError(_("%s cannot be purchased.", line.product_id.display_name))
                for tax in line.tax_ids:
                    if tax.type_tax_use != "purchase" or tax.company_id != self.company_id:
                        raise ValidationError(_("%(product)s: tax %(tax)s is not a purchase tax "
                                                "of the company.", product=line.product_id.display_name,
                                                tax=tax.name))
        if self.bill_mode == "existing":
            # only the lines really received count (an executed quantity of 0 receives
            # nothing, so its bill cannot justify the mode)
            executed = self.line_ids.filtered(lambda ln: ln._qty_executed() > 0)
            if not executed.purchase_line_id or not self._received_bills(executed):
                errors.append(_("bill already received for these order lines"))
        if self.bill_mode == "create":
            need(self.bill_ref, _("vendor bill reference"))
            need(self.bill_date, _("bill date"))
            if not self.bill_attachment_ids.filtered(lambda a: a.mimetype == "application/pdf"):
                errors.append(_("bill PDF"))

    def _check_third_party_contract(self, errors, need):
        need(self.contract_start, _("contract start"))
        need(self.open_ended or self.contract_end, _("planned end (or open-ended)"))
        if self.contract_end and self.contract_start and self.contract_end < self.contract_start:
            raise ValidationError(_("The planned end is before the start."))
        nature = "loan" if self.receipt_branch == "borrowed" or self.exit_nature == "loan" else "rental"
        contract_type = "sale" if self.operation_type == "exit" else "purchase"
        product = self._contract_product(nature, contract_type)
        if not product:
            errors.append(_("contract product in the settings"))
        elif product.type != "service" or product.maintenance_ok:
            raise ValidationError(_("The contract product of the settings must be a service."))
        if self.operation_type == "receipt" and self.contract_mode == "existing":
            contract = self.contract_id
            need(contract, _("contract"))
            if contract:
                self._check_existing_contract(contract, nature)

    def _check_existing_contract(self, contract, nature):
        """An existing supplier contract of the owner, active, same company; for a loan
        received by an operator alone, a loan contract (PLAN.md, audit criteria)."""
        if not contract.active:
            raise ValidationError(_("The contract %s is archived.", contract.display_name))
        if contract.contract_type != "purchase":
            raise ValidationError(_("The contract %s is not a supplier contract.", contract.display_name))
        if contract.company_id != self.company_id:
            raise ValidationError(_("The contract %s belongs to another company.", contract.display_name))
        if contract.partner_id.commercial_partner_id != self.partner_id.commercial_partner_id:
            raise ValidationError(_("The contract %s belongs to another partner.", contract.display_name))
        lines = contract.contract_line_ids.filtered(lambda ln: not ln.is_canceled)
        start = self.contract_start or self._today
        if lines and all(ln.date_end and ln.date_end < start for ln in lines):
            raise ValidationError(_("The contract %s has ended.", contract.display_name))
        if nature == "loan":
            equipment_lines = lines.filtered("equipment_id")
            if not equipment_lines or any(ln.equipment_nature != "loan" for ln in equipment_lines):
                raise ValidationError(_("%s is not a loan contract.", contract.display_name))

    def _check_values_exit(self, errors, need):
        need(self.partner_id, _("third party"))
        need(self.site_partner_id, _("site address"))
        need(self.exit_nature, _("free loan or rented out"))
        need(self.picking_type_id, _("operation type"))
        if self.picking_type_id and self.picking_type_id.code != "internal":
            raise ValidationError(_("Choose an internal transfer operation type."))
        partner = self.partner_id.commercial_partner_id
        if self.site_partner_id and self.site_partner_id.commercial_partner_id != partner:
            raise ValidationError(_("The site address belongs to another partner."))
        if self.offsite_location_id:
            loc = self.offsite_location_id
            if not (loc.active and loc.place_type == "lent_out" and loc.usage == "internal"):
                raise ValidationError(_("Choose an active lent-out stock."))
            if loc.address_id.commercial_partner_id != partner:
                raise ValidationError(_("The off-site stock belongs to another third party."))
        else:
            need(self.new_location_name, _("off-site stock (existing or new)"))
            need(self.new_location_parent_id, _("parent of the new off-site stock"))
            if self.new_location_parent_id and not self.new_location_parent_id.is_offsite_parent:
                raise ValidationError(_("The parent must be flagged as parent of off-site stocks."))
        self._check_third_party_contract(errors, need)
        for line in self.line_ids:
            equipment = line.equipment_id
            need(equipment, _("equipment"))
            if not equipment:
                continue
            if equipment.ownership_status != "owned" or equipment.integration_state != "done" \
                    or not equipment.active:
                raise ValidationError(_("%s must be owned and integrated.", equipment.display_name))
            location = line._current_location()
            if not location or location.place_type != "physical":
                raise ValidationError(_("%s must be in an internal physical stock.",
                                        equipment.display_name))
            if self.exit_nature == "rental":
                need(line.rent_amount, _("%s: rent", equipment.display_name))
            if self.exit_nature:
                line._check_contract_start_free("sale", self.exit_nature)

    def _check_values_return(self, errors, need):
        need(self.picking_type_id, _("operation type"))
        if self.picking_type_id and self.picking_type_id.code != "internal":
            raise ValidationError(_("Choose an internal transfer operation type."))
        for line in self.line_ids:
            equipment = line.equipment_id
            need(equipment, _("equipment"))
            if equipment and equipment.ownership_status != "lent_out":
                raise ValidationError(_("%s is not lent out.", equipment.display_name))
            need(line.dest_location_id, _("%s: return destination", equipment.display_name))
            dest = line.dest_location_id
            if dest and not (dest.active and dest.usage == "internal" and dest.place_type == "physical"):
                raise ValidationError(_("The return destination must be an internal physical stock."))

    def _check_values_restitution(self, errors, need):
        need(self.partner_id, _("owner"))
        if any(line.equipment_id.stock_lot_id for line in self.line_ids):
            need(self.picking_type_id, _("operation type"))
            if self.picking_type_id and self.picking_type_id.code != "outgoing":
                raise ValidationError(_("Choose a delivery operation type."))
        for line in self.line_ids:
            equipment = line.equipment_id
            need(equipment, _("equipment"))
            if equipment and (equipment.ownership_status not in THIRD_PARTY_OWNED
                              or equipment.owner_partner_id.commercial_partner_id
                              != self.partner_id.commercial_partner_id):
                raise ValidationError(_("%s is not borrowed or rented from this owner.",
                                        equipment.display_name))
        for stop in self.stop_line_ids.filtered(lambda s: not s.mandatory):
            if not stop.confirmed:
                errors.append(_("confirmation of %s", stop.contract_line_id.display_name))

    def _check_user_access(self):
        """The records referenced must be readable by the real user, before any
        elevation."""
        if self.env.su:
            return
        records = [self.partner_id, self.site_partner_id, self.picking_type_id,
                   self.location_dest_id, self.purchase_id, self.contract_id,
                   self.offsite_location_id, self.line_ids.product_id,
                   self.line_ids.equipment_id, self.line_ids.dest_location_id]
        for record in records:
            if record:
                record.check_access("read")

    def _check_final_consistency(self):
        for line in self.line_ids.filtered("equipment_id"):
            equipment = line.equipment_id.with_context(active_test=False)
            if not equipment._check_stock_owner_consistency():
                raise ValidationError(_("%s: owner on stock inconsistent after the operation.",
                                        equipment.display_name))
            location = line._current_location()
            if equipment.active and location:
                lent = location.place_type == "lent_out"
                if lent != (equipment.ownership_status == "lent_out"):
                    raise ValidationError(_("%s: location and ownership status disagree.",
                                            equipment.display_name))

    def _acquisition_location(self):
        company = self.company_id
        return {
            "gift": company.equipment_gift_location_id,
            "current_account": company.equipment_current_account_location_id,
            "regularisation": company.equipment_regularisation_location_id,
        }.get(self.acquisition_nature) or self.env["stock.location"]

    # ------------------------------------------------------------- stop lines

    def _refresh_stop_lines(self):
        """Contract lines of the equipment of a return or restitution, and no other."""
        for op in self.filtered(lambda o: o.operation_type in ("return", "restitution")
                                and o.state in ("draft", "to_approve", "approved")):
            today = op._today
            domain = [("equipment_id", "in", op.line_ids.equipment_id.ids),
                      ("is_canceled", "=", False),
                      "|", ("date_end", "=", False), ("date_end", ">=", today)]
            if op.operation_type == "return":
                domain += [("contract_id.contract_type", "=", "sale"),
                           ("equipment_nature", "in", ("loan", "rental"))]
            lines = self.env["contract.line"].sudo().search(domain)
            existing = op.stop_line_ids
            obsolete = existing.filtered(lambda s: s.contract_line_id not in lines)
            if obsolete:
                obsolete.sudo().unlink()
            for contract_line in lines - existing.contract_line_id:
                mandatory = op.operation_type == "return" or contract_line.equipment_nature in (
                    "loan", "rental")
                self.env["equipment.operation.stop"].sudo().create({
                    "operation_id": op.id, "contract_line_id": contract_line.id,
                    "mandatory": mandatory, "to_stop": True,
                })
            # a contract line added or ended after the approval cancels it
            op._invalidate_changed_approvals()

    def action_refresh_stop_lines(self):
        self._refresh_stop_lines()
        return True


class EquipmentOperationLine(models.Model):
    _name = "equipment.operation.line"
    _description = "Equipment Operation Line"
    _check_company_auto = True

    operation_id = fields.Many2one("equipment.operation", required=True, ondelete="cascade",
                                   index=True)
    company_id = fields.Many2one(related="operation_id.company_id", store=True)
    operation_type = fields.Selection(related="operation_id.operation_type")
    product_id = fields.Many2one("product.product", check_company=True)
    family = fields.Selection(
        [("equipment", "Equipment in Stock"), ("non_stock", "Non-Stock Equipment"),
         ("consumable", "Consumable")],
        compute="_compute_family", store=True,
    )
    quantity = fields.Float(string="Approved Quantity", default=1.0, digits="Product Unit of Measure",
                            help="Maximum quantity, part of the approval.")
    quantity_done = fields.Float(
        string="Executed Quantity", digits="Product Unit of Measure",
        help="Quantity actually received or moved; at most the approved quantity. "
        "Defaults to the approved quantity; 0 means nothing executed for this line.",
    )
    price_unit = fields.Float(string="Unit Price", digits="Product Price")
    tax_ids = fields.Many2many("account.tax", string="Taxes", check_company=True)
    purchase_line_id = fields.Many2one("purchase.order.line", string="Order Line")
    unit_value = fields.Float(digits="Product Price",
                              help="Acquisition without purchase: unit value of entry (C17).")
    lot_name = fields.Char(string="Serial Number")
    lot_generate = fields.Boolean(string="No Manufacturer Serial Number")
    lot_id = fields.Many2one("stock.lot", readonly=True)
    equipment_id = fields.Many2one("maintenance.equipment", string="Equipment",
                                   check_company=True)
    equipment_name = fields.Char()
    responsible_user_id = fields.Many2one("res.users", string="Responsible / Holder")
    warranty_status = fields.Selection(WARRANTY_STATUS)
    insurance_status = fields.Selection(INSURANCE_STATUS)
    replacement_value = fields.Float()
    replacement_currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id)
    replacement_value_date = fields.Date()
    rent_amount = fields.Float(string="Rent per Period")
    condition = fields.Text(string="Condition")
    attachment_ids = fields.Many2many("ir.attachment", "equipment_operation_line_attachment_rel",
                                      "line_id", "attachment_id", string="Photos and Documents")
    origin_location_id = fields.Many2one("stock.location", string="Origin Stock", readonly=True)
    dest_location_id = fields.Many2one("stock.location", string="Return Destination",
                                       check_company=True)

    @api.depends("product_id.maintenance_ok", "product_id.is_storable", "equipment_id")
    def _compute_family(self):
        for line in self:
            product = line.product_id or line.equipment_id.product_id
            if line.equipment_id and not line.equipment_id.stock_lot_id \
                    and line.operation_type != "receipt":
                line.family = "non_stock"
            elif product.maintenance_ok:
                line.family = "equipment" if product.is_storable else "non_stock"
            else:
                line.family = "consumable"

    @api.onchange("product_id")
    def _onchange_product_id(self):
        categ = self.product_id.categ_id
        if categ.default_warranty_status and not self.warranty_status:
            self.warranty_status = categ.default_warranty_status
        if categ.default_insurance_status and not self.insurance_status:
            self.insurance_status = categ.default_insurance_status
        if not self.unit_value:
            self.unit_value = self.product_id.standard_price

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            op = self.env["equipment.operation"].browse(vals.get("operation_id"))
            self._check_editable(op)
            if not self.env.su and ({"lot_id", "origin_location_id"} & set(vals)):
                raise AccessError(_("This field is set by the operation itself."))
            if "quantity_done" not in vals:
                vals["quantity_done"] = vals.get("quantity", 1.0)
        lines = super().create(vals_list)
        lines._fill_defaults()
        lines.operation_id._attach_documents()
        lines.operation_id._invalidate_changed_approvals()
        return lines

    def write(self, vals):
        self._check_editable(self.operation_id)
        if "lot_id" in vals or "origin_location_id" in vals:
            if not self.env.su:
                raise AccessError(_("This field is set by the operation itself."))
        if "quantity" in vals and "quantity_done" not in vals:
            # the executed quantity follows the approved one unless set apart
            following = self.filtered(lambda ln: ln.quantity_done == ln.quantity)
            if following and following != self:
                return (following.write(dict(vals, quantity_done=vals["quantity"]))
                        and (self - following).write(vals))
            if following:
                vals = dict(vals, quantity_done=vals["quantity"])
        res = super().write(vals)
        self.operation_id._attach_documents()
        self.operation_id._invalidate_changed_approvals()
        return res

    def unlink(self):
        ops = self.operation_id
        self._check_editable(ops)
        res = super().unlink()
        ops._invalidate_changed_approvals()
        return res

    def _check_editable(self, operations):
        if not self.env.su and any(op.state in ("processing", "done", "cancel") for op in operations):
            raise UserError(_("An executed or cancelled operation cannot be changed."))

    def _fill_defaults(self):
        for line in self:
            if not line.product_id and line.equipment_id:
                line.product_id = line.equipment_id.product_id
            categ = line.product_id.categ_id
            if not line.warranty_status and categ.default_warranty_status:
                line.warranty_status = categ.default_warranty_status
            if not line.insurance_status and categ.default_insurance_status:
                line.insurance_status = categ.default_insurance_status
            if line.operation_type == "return" and not line.dest_location_id and line.equipment_id:
                line.dest_location_id = line._recorded_origin()

    @api.onchange("quantity")
    def _onchange_quantity(self):
        self.quantity_done = self.quantity

    def _qty_executed(self):
        """Executed quantity as entered: 0 means nothing received for this line."""
        return self.quantity_done

    def _needs_move(self):
        """Equipment in stock and consumables move; a non-stock equipment moves only
        when its purchase order line still has an open receipt move."""
        if self.family != "non_stock":
            return True
        return bool(self.purchase_line_id.move_ids.filtered(
            lambda m: m.state not in ("done", "cancel") and m.picking_code == "incoming"))

    def _recorded_origin(self):
        """Stock the equipment left from at its last exit; otherwise the return
        location of its off-site stock."""
        exit_line = self.search([
            ("equipment_id", "=", self.equipment_id.id),
            ("operation_id.operation_type", "=", "exit"),
            ("operation_id.state", "=", "done"),
        ], order="id desc", limit=1)
        if exit_line.origin_location_id:
            return exit_line.origin_location_id
        return self._current_location().return_location_id

    # ---------------------------------------------------------------- helpers

    def _current_location(self):
        self.ensure_one()
        equipment = self.equipment_id
        if equipment.stock_lot_id:
            quants = equipment._internal_quants()
            return quants[:1].location_id
        return equipment.current_location_id

    def _check_serial_free(self):
        if not self.lot_name or self.equipment_id:
            return
        lot = self.env["stock.lot"].sudo().search([
            ("name", "=", self.lot_name), ("product_id", "=", self.product_id.id),
            ("company_id", "in", (self.company_id.id, False)),
        ], limit=1)
        if lot and self.env["maintenance.equipment"].sudo().with_context(
                active_test=False).search_count([("stock_lot_id", "=", lot.id)]):
            raise ValidationError(_("Serial number %s already belongs to an equipment.", lot.name))

    def _check_receipt_equipment(self):
        """Only a draft equipment of the order line without serial number can be
        completed by a purchase receipt (bill posted before the receipt)."""
        equipment = self.equipment_id
        op = self.operation_id
        if op.receipt_branch != "purchase" or equipment.integration_state != "draft" \
                or equipment.stock_lot_id \
                or equipment.move_line_id.purchase_line_id != self.purchase_line_id:
            raise ValidationError(_("%s cannot be completed by this receipt.", equipment.display_name))

    def _ensure_lot(self):
        if self.lot_id:
            return
        Lot = self.env["stock.lot"]
        name = self.lot_name
        if self.lot_generate and not name:
            name = self.env["ir.sequence"].next_by_code("stock.lot.serial")
        lot = Lot.search([("name", "=", name), ("product_id", "=", self.product_id.id),
                          ("company_id", "in", (self.company_id.id, False))], limit=1)
        if not lot:
            lot = Lot.create({"name": name, "product_id": self.product_id.id,
                              "company_id": self.company_id.id})
        self.write({"lot_id": lot.id, "lot_name": name})

    def _free_draft_equipment(self):
        """Draft equipment created by a bill posted before the receipt."""
        if not self.purchase_line_id:
            return self.env["maintenance.equipment"]
        taken = self.operation_id.line_ids.equipment_id
        return self.env["maintenance.equipment"].search([
            ("move_line_id.purchase_line_id", "=", self.purchase_line_id.id),
            ("integration_state", "=", "draft"), ("stock_lot_id", "=", False),
            ("id", "not in", taken.ids),
        ], order="id", limit=1)

    def _equipment_category(self):
        categ = self.product_id.product_tmpl_id.categ_id
        category = fields.first(categ.equipment_category_ids)
        if not category:
            category = self.env["maintenance.equipment.category"].create(
                {"name": categ.name, "product_category_id": categ.id}
            )
        return category

    def _prepare_equipment(self):
        """Create or complete the equipment with its target ownership (before the
        stock move, so that the owner checks find it)."""
        op = self.operation_id
        equipment = self.equipment_id or self._free_draft_equipment()
        vals = {
            "name": self.equipment_name or (
                "%s – %s" % (self.product_id.name, self.lot_id.name) if self.lot_id
                else self.product_id.name),
            "product_id": self.product_id.id,
            "company_id": op.company_id.id,
            "owner_user_id": self.responsible_user_id.id or False,
            "warranty_status": self.warranty_status,
            "insurance_status": self.insurance_status,
            "replacement_value": self.replacement_value,
            "replacement_currency_id": self.replacement_currency_id.id or op.company_id.currency_id.id,
            "replacement_value_date": self.replacement_value_date,
            "stock_lot_id": self.lot_id.id or False,
            "current_location_id": op.location_dest_id.id if self.family == "non_stock" else False,
            "effective_date": op._today,
        }
        if op.receipt_branch == "purchase":
            vals["partner_id"] = op.partner_id.id
        if op.acquisition_nature == "current_account":
            vals.update(handover_value=self.unit_value, handover_value_date=op._today)
        if equipment:
            equipment.write(vals)
        else:
            vals["category_id"] = self._equipment_category().id
            equipment = self.env["maintenance.equipment"].create(vals)
        self.write({"equipment_id": equipment.id})
        if op.receipt_branch in THIRD_PARTY_OWNED:
            equipment._set_ownership(op.receipt_branch, op.partner_id, _("%s (receipt)", op.name))
        else:
            equipment.message_post(body=_("Received by %s.", op._get_html_link()))
        self._post_on_equipment()

    def _post_on_equipment(self):
        equipment = self.equipment_id
        if not equipment:
            return
        copies = self.env["ir.attachment"]
        for attachment in self.attachment_ids:
            copies |= attachment.copy({"res_model": "maintenance.equipment", "res_id": equipment.id})
        body = _("%(op)s – condition: %(condition)s",
                 op=self.operation_id._get_html_link(), condition=self.condition or "-")
        equipment.message_post(body=body, attachment_ids=copies.ids)

    def _find_move(self, picking):
        moves = picking.move_ids.filtered(lambda m: m.product_id == self.product_id
                                          and m.state not in ("done", "cancel"))
        if self.purchase_line_id:
            moves = moves.filtered(lambda m: m.purchase_line_id == self.purchase_line_id)
        if self.equipment_id and self.operation_type != "receipt":
            moves = moves.filtered(lambda m: m.location_id == self.origin_location_id) or moves
        if not moves:
            raise UserError(_("No move of %(product)s in %(picking)s.",
                              product=self.product_id.display_name, picking=picking.name))
        return moves[0]

    def _source_location(self, move):
        if self.operation_type == "receipt":
            return move.location_id
        return self.origin_location_id

    def _destination_location(self, move):
        if self.operation_type == "return":
            return self.dest_location_id
        return move.location_dest_id

    def _move_vals(self, source, dest):
        return {
            "name": self.product_id.display_name, "product_id": self.product_id.id,
            "product_uom_qty": 1, "product_uom": self.product_id.uom_id.id,
            "location_id": source.id, "location_dest_id": dest.id,
            "company_id": self.company_id.id,
            "restrict_partner_id": self.operation_id.partner_id.id
            if self.operation_type == "restitution" else False,
        }

    def _check_contract_start_free(self, contract_type, nature):
        """Closed intervals: a new line cannot start on the day the previous one ends."""
        op = self.operation_id
        start = op.contract_start or op._today
        previous = self.env["contract.line"].sudo().search([
            ("equipment_id", "=", self.equipment_id.id), ("equipment_nature", "=", nature),
            ("contract_id.contract_type", "=", contract_type), ("is_canceled", "=", False),
            "|", ("date_end", "=", False), ("date_end", ">=", start),
        ], limit=1)
        if previous:
            raise ValidationError(_(
                "%(equipment)s: a %(nature)s line runs until %(end)s; start the new one on "
                "%(next)s or later.", equipment=self.equipment_id.display_name, nature=nature,
                end=previous.date_end or _("no end"),
                next=previous.date_end and fields.Date.add(previous.date_end, days=1) or "-"))


class EquipmentOperationStop(models.Model):
    """Contract lines of the equipment returned or restituted, with the user's choice."""

    _name = "equipment.operation.stop"
    _description = "Contract Line to Stop"

    operation_id = fields.Many2one("equipment.operation", required=True, ondelete="cascade",
                                   index=True)
    company_id = fields.Many2one(related="operation_id.company_id", store=True, index=True)
    contract_line_id = fields.Many2one("contract.line", required=True, readonly=True,
                                       ondelete="cascade")
    equipment_id = fields.Many2one(related="contract_line_id.equipment_id")
    nature = fields.Selection(related="contract_line_id.equipment_nature")
    contract_id = fields.Many2one(related="contract_line_id.contract_id")
    mandatory = fields.Boolean(readonly=True,
                               help="Loan or rental of possession: always stopped.")
    to_stop = fields.Boolean(string="Stop", default=True)
    confirmed = fields.Boolean(help="Explicit confirmation of the choice to stop or keep "
                                    "this line.")

    def _will_stop(self):
        self.ensure_one()
        return self.mandatory or self.to_stop

    def write(self, vals):
        if {"mandatory", "contract_line_id", "operation_id"} & set(vals) and not self.env.su:
            raise AccessError(_("This field is set by the operation itself."))
        if not self.env.su and any(op.state in ("processing", "done", "cancel")
                                   for op in self.operation_id):
            raise UserError(_("An executed or cancelled operation cannot be changed."))
        res = super().write(vals)
        self.operation_id._invalidate_changed_approvals()
        return res

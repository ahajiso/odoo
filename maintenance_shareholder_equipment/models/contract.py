from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

EQUIPMENT_NATURE = [
    ("rental", "Rental"),
    ("loan", "Loan (free)"),
    ("insurance", "Insurance"),
    ("maintenance", "Maintenance"),
]


class ContractLine(models.Model):
    _inherit = "contract.line"

    equipment_id = fields.Many2one(
        "maintenance.equipment", string="Equipment", index=True, ondelete="restrict"
    )
    equipment_nature = fields.Selection(
        EQUIPMENT_NATURE,
        string="Equipment Relation",
        help="Direction comes from the contract type: rental on a supplier contract = "
        "rent paid, on a customer contract = rent received. A loan line is never "
        "invoiced.",
    )

    equipment_billing_mode = fields.Selection(
        [("recurring", "Recurring"), ("one_off", "One-off Package")],
        default="recurring", required=True,
    )
    equipment_origin_operation_id = fields.Many2one(
        "equipment.operation", string="Original Equipment Operation",
        groups="maintenance_shareholder_equipment.group_equipment_operator,maintenance_shareholder_equipment.group_equipment_approver,maintenance.group_equipment_manager",
        readonly=True, copy=False, index=True, ondelete="restrict",
    )
    equipment_billing_revision = fields.Integer(
        readonly=True, copy=False, groups="base.group_system",
    )
    equipment_rental_start = fields.Datetime(string="Planned Rental Start")
    equipment_rental_end = fields.Datetime(string="Planned Rental End")
    equipment_rental_hours = fields.Float(
        string="Planned Duration (hours)", compute="_compute_equipment_rental_hours",
    )

    @api.depends("equipment_rental_start", "equipment_rental_end")
    def _compute_equipment_rental_hours(self):
        for line in self:
            line.equipment_rental_hours = (
                (line.equipment_rental_end - line.equipment_rental_start).total_seconds() / 3600
                if line.equipment_rental_start and line.equipment_rental_end else 0
            )

    @api.constrains("equipment_billing_mode", "equipment_id", "equipment_nature",
                    "contract_id", "equipment_rental_start", "equipment_rental_end",
                    "quantity", "price_unit", "date_start", "date_end", "is_auto_renew")
    def _check_equipment_one_off(self):
        for line in self.filtered(lambda ln: ln.equipment_billing_mode == "one_off"):
            if (not line.equipment_id or line.equipment_nature != "rental"
                    or line.contract_id.contract_type != "purchase"
                    or not line.contract_id.line_recurrence or line.is_auto_renew):
                raise ValidationError(_("A one-off package needs an equipment rental line "
                                        "on a supplier contract with per-line billing."))
            if (not line.equipment_rental_start or not line.equipment_rental_end
                    or line.equipment_rental_end <= line.equipment_rental_start
                    or not line.date_end or line.quantity != 1):
                raise ValidationError(_("A one-off package needs ordered start/end times, "
                                        "an end date and quantity 1."))

    @api.depends("equipment_billing_mode")
    def _compute_recurring_next_date(self):
        res = super()._compute_recurring_next_date()
        for line in self.filtered(lambda ln: ln.equipment_billing_mode == "one_off"):
            line.recurring_next_date = False
        return res

    @api.constrains("recurring_next_date", "equipment_billing_mode")
    def _check_recurring_next_date_recurring_invoices(self):
        # OCA requires a next invoice date on unfinished recurring lines. Packages
        # intentionally have none and use the explicit draft-bill action below.
        return super(ContractLine, self.filtered(
            lambda ln: ln.equipment_billing_mode != "one_off"
        ))._check_recurring_next_date_recurring_invoices()

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and any(vals.get("equipment_origin_operation_id") for vals in vals_list):
            raise AccessError(_("This field is maintained by the billing workflow."))
        return super().create(vals_list)

    def _equipment_one_off_history(self):
        return self.env["account.move.line"].sudo().search([
            ("contract_line_id", "in", self.ids),
            ("move_id.move_type", "=", "in_invoice"),
        ]).move_id

    def unlink(self):
        if self.filtered(lambda line: line.equipment_billing_mode == "one_off")._equipment_one_off_history():
            raise UserError(_("A one-off bill keeps its contract link and history. "
                              "Cancel it and create a replacement."))
        return super().unlink()

    def write(self, vals):
        if "equipment_origin_operation_id" in vals:
            for line in self:
                if not self.env.su or line.equipment_origin_operation_id.id != vals["equipment_origin_operation_id"]:
                    raise AccessError(_("This field is maintained by the billing workflow."))
        identity = {"equipment_billing_mode", "equipment_id", "equipment_nature", "contract_id"}
        for line in self.filtered(lambda record: record.equipment_billing_mode == "one_off"):
            changed = any(key in vals and vals[key] != (
                line[key].id if self._fields[key].type == "many2one" else line[key]
            ) for key in identity)
            if changed:
                line._lock_equipment_one_off()
                if line._equipment_one_off_history():
                    raise UserError(_("A one-off bill keeps its contract link and history. "
                                      "Cancel it and create a replacement."))
        if "equipment_billing_revision" in vals and not self.env.su:
            raise AccessError(_("This field is maintained by the billing workflow."))
        protected = {"equipment_billing_mode", "equipment_rental_start", "equipment_rental_end",
                     "product_id", "equipment_id", "equipment_nature", "contract_id",
                     "price_unit", "specific_price", "quantity", "discount",
                     "uom_id", "automatic_price", "date_start", "date_end"}
        if protected.intersection(vals):
            packages = self.filtered(lambda ln: ln.equipment_billing_mode == "one_off")
            packages._lock_equipment_one_off()
            # Cancellation replaces an accounting document, not the approved
            # commitment. Historical bills keep these terms frozen as well.
            if packages._equipment_one_off_history():
                raise UserError(_("A billed one-off package commitment cannot be changed, "
                                  "even after bill cancellation."))
        return super().write(vals)

    def _lock_equipment_one_off(self):
        if not self:
            return
        self.flush_recordset()
        if self.ids:
            # Lock in a stable order, then change the technical revision through ORM.
            self.env.cr.execute("SELECT id FROM contract_line WHERE id IN %s "
                                "ORDER BY id FOR UPDATE", [tuple(sorted(self.ids))])
            self.invalidate_recordset()
            # Odoo uses REPEATABLE READ. A lock without updating this parent would
            # leave a waiting transaction's snapshot blind to the first bill. The
            # private ORM revision forces a serialization retry with a fresh snapshot.
            for line in self.sudo():
                line.write({"equipment_billing_revision": line.equipment_billing_revision + 1})

    def _equipment_one_off_bills(self):
        return self.env["account.move.line"].search([
            ("contract_line_id", "in", self.ids),
            ("move_id.move_type", "=", "in_invoice"),
            ("move_id.state", "!=", "cancel"),
            ("display_type", "=", "product"),
        ]).move_id

    def _insert_markers(self, first_date_invoiced, last_date_invoiced):
        # A package has no recurring period. The server's OCA 18.0.2.5.3
        # formats these dates unconditionally, even when there are no markers.
        # Keep the package description and let OCA prepare all accounting values.
        if self.equipment_billing_mode == "one_off":
            self.ensure_one()
            return self.name
        return super()._insert_markers(first_date_invoiced, last_date_invoiced)

    def _create_equipment_one_off_bill(self):
        self.ensure_one()
        self._lock_equipment_one_off()
        self._check_equipment_one_off()
        if (self.equipment_billing_mode != "one_off" or self.is_canceled
                or not self.active or not self.contract_id.active):
            raise UserError(_("Only an active one-off equipment rental can create this bill."))
        # Elevated read only, so hidden existing bills cannot cause a duplicate.
        existing = self.sudo()._equipment_one_off_bills()
        if existing:
            existing.with_env(self.env).check_access("read")
            if len(existing) != 1:
                raise UserError(_("Several bills already reference this one-off package."))
            self._link_one_off_bill_history(existing)
            return existing.with_env(self.env)
        if self.price_subtotal <= 0:
            raise ValidationError(_("The untaxed one-off package price must be positive."))
        contract = self.contract_id
        vals = contract._prepare_invoice(fields.Date.context_today(self))
        line_vals = self._prepare_invoice_line()
        line_vals.update(quantity=1, name=self.name)
        vals["invoice_line_ids"] = [Command.create(line_vals)]
        bill = self.env["account.move"].with_company(contract.company_id).create(vals)
        self._link_one_off_bill_history(bill)
        contract.message_post(body=_("One-off draft bill created: %s", bill._get_html_link()))
        return bill

    def _link_one_off_bill_history(self, bill):
        self.ensure_one()
        # Only the workflow can set this immutable origin. Narrow elevation links
        # the actual bill to that operation; callers gain no general write access.
        operation = self.sudo().equipment_origin_operation_id
        if operation:
            missing = bill - operation.bill_ids
            if missing:
                operation.write({"bill_ids": [Command.link(item.id) for item in missing]})

    def action_create_equipment_one_off_bill(self):
        self.ensure_one()
        # No sudo on this public entry point: normal billing and contract rights apply.
        if not self.env.su and not self.env.user.has_group("account.group_account_manager"):
            raise AccessError(_("Only accounting administrators can create a one-off supplier bill."))
        self.check_access("write")
        bill = self._create_equipment_one_off_bill()
        return {"type": "ir.actions.act_window", "res_model": "account.move",
                "res_id": bill.id, "view_mode": "form"}

    @api.constrains("equipment_id", "equipment_nature", "product_id", "contract_id")
    def _check_equipment_line(self):
        for line in self:
            if bool(line.equipment_id) != bool(line.equipment_nature):
                raise ValidationError(
                    _("Contract line %(name)s: equipment and equipment relation go "
                      "together.", name=line.display_name)
                )
            if not line.equipment_id:
                continue
            if line.equipment_nature == "insurance" and line.contract_id.contract_type != "purchase":
                raise ValidationError(_("An insurance line belongs to a supplier contract."))
            product = line.product_id
            if not product or product.type != "service" or product.maintenance_ok:
                raise ValidationError(
                    _("Contract line %(name)s: use a service product that is not an "
                      "equipment (otherwise its bills would create equipment).",
                      name=line.display_name)
                )

    @api.constrains("equipment_id", "equipment_nature", "date_start", "date_end",
                    "is_canceled", "contract_id")
    def _check_equipment_overlap(self):
        """No overlapping periods [date_start, date_end] (empty end = open-ended) per
        equipment, relation and contract type; cancelled lines are ignored."""
        for line in self.filtered(lambda ln: ln.equipment_id and not ln.is_canceled):
            others = self.search([
                ("id", "!=", line.id),
                ("equipment_id", "=", line.equipment_id.id),
                ("equipment_nature", "=", line.equipment_nature),
                ("contract_id.contract_type", "=", line.contract_id.contract_type),
                ("is_canceled", "=", False),
            ])
            for other in others:
                starts_before_other_ends = not other.date_end or line.date_start <= other.date_end
                ends_after_other_starts = not line.date_end or line.date_end >= other.date_start
                if starts_before_other_ends and ends_after_other_starts:
                    raise ValidationError(
                        _("%(equipment)s already has a %(nature)s line from %(start)s to "
                          "%(end)s (%(contract)s).",
                          equipment=line.equipment_id.display_name,
                          nature=line.equipment_nature, start=other.date_start,
                          end=other.date_end or _("no end"),
                          contract=other.contract_id.display_name)
                    )

    @api.constrains("equipment_id", "automatic_price", "contract_id")
    def _check_equipment_automatic_price(self):
        """The rent of an equipment is the stored price of its line, in a currency that
        does not depend on a price list (phase 3)."""
        for contract in self.contract_id:
            lines = contract.contract_line_ids
            if lines.filtered("equipment_id") and lines.filtered("automatic_price"):
                raise ValidationError(_(
                    "%s: a contract with an equipment line cannot have a line with an "
                    "automatic price (price list).", contract.display_name))

    def _get_contract_line_total_value(self):
        self.ensure_one()
        if self.equipment_billing_mode == "one_off":
            return self.price_subtotal
        return super()._get_contract_line_total_value()

    @api.depends("equipment_billing_mode")
    def _compute_monthly_recurring(self):
        res = super()._compute_monthly_recurring()
        for line in self.filtered(lambda ln: ln.equipment_billing_mode == "one_off"):
            line.monthly_recurring = 0
        return res

    def _can_be_invoiced(self, date_ref):
        if self.equipment_nature == "loan" or self.equipment_billing_mode == "one_off":
            return False
        return super()._can_be_invoiced(date_ref)

    def _compute_create_invoice_visibility(self):
        res = super()._compute_create_invoice_visibility()
        for line in self.filtered(lambda ln: ln.equipment_nature == "loan" or ln.equipment_billing_mode == "one_off"):
            line.create_invoice_visibility = False
        return res


class ContractContract(models.Model):
    _inherit = "contract.contract"

    # OCA's currency_id is computed and not stored: the stock monitor's SQL view reads
    # this stored copy, computed by OCA's own logic (phase 3, docs/phase3/PLAN.md §1-1).
    # The price-list path depends on the partner's property price list, which no
    # dependency can follow: a contract holding an equipment line has no automatic price
    # (ContractLine._check_equipment_automatic_price), so that path never applies.
    equipment_currency_id = fields.Many2one(
        "res.currency", string="Contract Currency (stored)",
        compute="_compute_equipment_currency_id", store=True,
    )

    def write(self, vals):
        # OCA prepares the bill from the parent (not only the rental line),
        # notably using invoice_partner_id rather than partner_id.
        protected = {"partner_id", "invoice_partner_id", "company_id",
                     "currency_id", "manual_currency_id", "journal_id", "pricelist_id",
                     "contract_type", "line_recurrence", "contract_template_id",
                     "payment_term_id", "fiscal_position_id", "generation_type",
                     "date_start", "date_end"}
        keys = protected.intersection(vals)
        if keys:
            for contract in self:
                packages = contract.sudo().with_context(active_test=False).contract_line_ids.filtered(
                    lambda line: line.equipment_billing_mode == "one_off")
                # Share the billing lock and revision: concurrent creation of
                # the first bill must not race a change of supplier/currency.
                packages._lock_equipment_one_off()
                contract.invalidate_recordset(list(keys))
                changed = False
                for key in keys:
                    current = contract[key]
                    value = vals[key]
                    if self._fields[key].type == "many2one":
                        current = current.id
                    elif self._fields[key].type == "date":
                        value = fields.Date.to_date(value) or False
                    if current != value:
                        changed = True
                        break
                if changed and packages._equipment_one_off_history():
                    raise UserError(_("A billed one-off package commitment cannot be changed, "
                                      "even after bill cancellation."))
        return super().write(vals)

    def unlink(self):
        # PostgreSQL cascades contract deletion to its lines without calling their
        # unlink hooks. Preserve cancelled bill history through this parent too.
        packages = self.with_context(active_test=False).contract_line_ids.filtered(
            lambda line: line.equipment_billing_mode == "one_off")
        if packages._equipment_one_off_history():
            raise UserError(_("A one-off bill keeps its contract link and history. "
                              "Cancel it and create a replacement."))
        return super().unlink()

    @api.constrains("line_recurrence", "contract_type")
    def _check_equipment_one_off_contract(self):
        self.contract_line_ids._check_equipment_one_off()

    @api.depends("manual_currency_id", "journal_id.currency_id", "company_id.currency_id",
                 "pricelist_id.currency_id", "contract_line_ids.automatic_price", "partner_id")
    def _compute_equipment_currency_id(self):
        for contract in self:
            contract.equipment_currency_id = (contract.manual_currency_id
                                              or contract._get_computed_currency())

    @api.depends("contract_line_ids.equipment_nature", "contract_line_ids.equipment_billing_mode")
    def _compute_recurring_next_date(self):
        """OCA takes the earliest date of all non-cancelled lines (or a computed date
        when there is none): loan lines would keep a loan-only contract selected by the
        invoicing job forever. Recompute without them."""
        res = super()._compute_recurring_next_date()
        for contract in self:
            lines = contract.contract_line_ids.filtered(
                lambda ln: not ln.is_canceled and (not ln.display_type or ln.is_recurring_note)
            )
            if not contract.contract_line_ids.filtered(
                    lambda ln: ln.equipment_nature == "loan" or ln.equipment_billing_mode == "one_off"):
                continue
            invoiceable = lines.filtered(
                lambda ln: ln.equipment_nature != "loan" and ln.equipment_billing_mode != "one_off"
                and ln.recurring_next_date
            )
            contract.recurring_next_date = (
                min(invoiceable.mapped("recurring_next_date")) if invoiceable else False
            )
        return res

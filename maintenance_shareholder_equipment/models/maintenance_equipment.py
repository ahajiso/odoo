from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

OWNERSHIP_STATUS = [
    ("owned", "Owned"),
    ("borrowed", "Borrowed"),
    ("rented", "Rented"),
    ("lent_out", "Lent Out"),
]
WARRANTY_STATUS = [
    ("under_warranty", "Under Warranty"),
    ("no_warranty", "No Warranty"),
    ("not_applicable", "Not Applicable"),
]
INSURANCE_STATUS = [
    ("insured", "Insured"),
    ("not_insured", "Not Insured"),
    ("not_applicable", "Not Applicable"),
]
# Written only by the central methods below (superuser mode), never directly.
PROTECTED_FIELDS = {"ownership_status", "owner_partner_id", "integration_state"}
# Equipment cost (phase 2f): written only by _set_cost(), never directly.
COST_FIELDS = {"cost", "cost_known", "cost_date", "cost_provisional", "cost_source",
               "cost_reference"}
COST_SOURCES = [
    ("order", "Purchase Order (estimate)"),
    ("bill", "Supplier Bill"),
    ("bill_cancelled", "Cancelled Bill"),
    ("bill_released", "Released from a Bill"),
    ("acquisition", "Acquisition without Purchase"),
    ("migration", "Migration (receipt value)"),
    ("manual", "Manual Correction"),
]
COST_MANAGER_GROUP = "account.group_account_manager"


def valid_responsible(user, company):
    """An active internal user allowed in the company (phase 2f, D6: no « not
    assigned »)."""
    user = user.sudo()
    return bool(user) and user.active and not user.share and (
        not company or company in user.company_ids)
COMPANY_OWNED = ("owned", "lent_out")
THIRD_PARTY_OWNED = ("borrowed", "rented")


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    ownership_status = fields.Selection(
        OWNERSHIP_STATUS,
        string="Ownership Status",
        required=True,
        default="owned",
        index=True,
        tracking=True,
        readonly=True,
        help="Legal relationship with the item. Changed only by business actions "
        "(receipt, handover, return) or by the ownership correction wizard.",
    )
    owner_partner_id = fields.Many2one(
        "res.partner",
        string="Legal Owner",
        required=True,
        default=lambda self: self.env.company.partner_id,
        index=True,
        tracking=True,
        readonly=True,
        help="The company for owned and lent-out items, the third party otherwise.",
    )
    integration_state = fields.Selection(
        [("draft", "To Complete"), ("done", "Integrated")],
        string="Integration",
        required=True,
        default="draft",
        index=True,
        tracking=True,
        readonly=True,
        help="To Complete: created automatically (supplier bill, import) and not yet "
        "checked. Integrated: all required information is present.",
    )
    stock_lot_id = fields.Many2one(
        "stock.lot",
        string="Serial Number (Stock)",
        index=True,
        copy=False,
        tracking=True,
        help="Serial number of the item in stock. Location and owner on stock come "
        "from it.",
    )
    asset_id = fields.Many2one(
        "account.asset",
        string="Fixed Asset",
        index=True,
        copy=False,
        tracking=True,
        help="Filled from the supplier bill line when empty; can be set by hand for a "
        "contribution without bill.",
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id", string="Company Currency"
    )
    # Float without digits, as before: Monetary or digits would change the column
    # type (double precision -> numeric), and Odoo drops every SQL view reading a
    # column whose type it converts, the stock monitor reports included.
    # Shown with its currency by the monetary widget.
    replacement_value = fields.Float(tracking=True)
    replacement_currency_id = fields.Many2one(
        "res.currency",
        string="Replacement Value Currency",
        default=lambda self: self.env.company.currency_id,
    )
    replacement_value_date = fields.Date(string="Replacement Value Date")
    warranty_status = fields.Selection(WARRANTY_STATUS, tracking=True)
    insurance_status = fields.Selection(INSURANCE_STATUS, tracking=True)
    handover_value = fields.Float(
        help="Kept for information until the accountant decides its meaning; never "
        "used in accounting.",
    )
    handover_value_date = fields.Date()
    # Equipment cost (phase 2f, docs/phase2f/PLAN.md §2). `cost` keeps the column of
    # the maintenance module (Float, company currency): the phase 3 view reads it, and
    # a type change would drop the views reading it. It is meaningful only when
    # `cost_known` is set: a Float cannot tell « unknown » from 0.
    # no tracking: _set_cost() posts one explicit message per change, with the reason
    cost = fields.Float(readonly=True,
                        help="Unit cost in company currency; see « Cost Known ».")
    cost_known = fields.Boolean(readonly=True, copy=False)
    cost_date = fields.Date(readonly=True, copy=False)
    cost_provisional = fields.Boolean(
        readonly=True, copy=False,
        help="Estimate from the purchase order, until the supplier bill is posted.")
    cost_source = fields.Selection(COST_SOURCES, readonly=True, copy=False)
    cost_reference = fields.Char(readonly=True, copy=False,
                                 help="Document the cost comes from.")
    current_location_id = fields.Many2one(
        "stock.location",
        string="Location (Non-Stock Equipment)",
        tracking=True,
        help="Only for equipment not managed in stock (vehicle, fixed installation). "
        "Must be empty when the equipment has a serial number in stock.",
    )
    # Obsolete, kept until phase 3: the stock monitor reports (bi_sql_editor views)
    # still read these columns, and removing a field drops its column with CASCADE.
    owner_type = fields.Selection(
        [("company", "Company"), ("shareholder", "Shareholder"), ("third_party", "Third Party")],
        string="Ownership Type (obsolete)",
        default="company",
    )
    acquisition_mode = fields.Selection(
        [
            ("purchase", "Purchase"),
            ("rental", "Rental"),
            ("borrowed", "Borrowed from Third Party"),
            ("loaned_out", "Loaned to Third Party"),
        ],
        string="Acquisition Mode (obsolete)",
        default="purchase",
    )

    _sql_constraints = [
        ("stock_lot_uniq", "unique(stock_lot_id)",
         "A serial number can belong to one equipment only."),
        ("asset_uniq", "unique(asset_id)",
         "A fixed asset can belong to one equipment only."),
    ]

    # ------------------------------------------------------------------ protection

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            # the cost is set by the receipt, the bill or the correction wizard
            vals_list = [{k: v for k, v in vals.items() if k not in COST_FIELDS}
                         for vals in vals_list]
        for vals in vals_list:
            # The default owner is the partner of the equipment's company, not of the
            # company the user is currently working in.
            if "owner_partner_id" not in vals and vals.get("company_id"):
                vals["owner_partner_id"] = (
                    self.env["res.company"].browse(vals["company_id"]).partner_id.id
                )
        if not self.env.su:
            for vals in vals_list:
                self._check_create_protected(vals)
        for vals in vals_list:
            self._apply_category_defaults(vals)
        return super().create(vals_list)

    def _check_create_protected(self, vals):
        company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
        if vals.get("ownership_status", "owned") != "owned" or vals.get(
            "integration_state", "draft"
        ) != "draft" or vals.get("owner_partner_id", company.partner_id.id) != company.partner_id.id:
            raise AccessError(
                _("A new equipment is created as owned by the company and to complete. "
                  "Use the receiving actions to create borrowed or rented equipment.")
            )

    def _apply_category_defaults(self, vals):
        """Warranty and insurance defaults configured on the product category, applied
        explicitly at creation (never a silent default)."""
        if not vals.get("product_id"):
            return
        categ = self.env["product.product"].browse(vals["product_id"]).categ_id
        if not vals.get("warranty_status") and categ.default_warranty_status:
            vals["warranty_status"] = categ.default_warranty_status
        if not vals.get("insurance_status") and categ.default_insurance_status:
            vals["insurance_status"] = categ.default_insurance_status

    def write(self, vals):
        if PROTECTED_FIELDS.intersection(vals) and not self.env.su:
            raise AccessError(
                _("Ownership and integration are changed only through the business "
                  "actions or the ownership correction wizard.")
            )
        if COST_FIELDS.intersection(vals) and not self.env.su:
            raise AccessError(
                _("The equipment cost is set by the receipt, the supplier bill or the cost "
                  "correction wizard (Accounting / Administrator).")
            )
        return super().write(vals)

    # --------------------------------------------------------------------- cost

    def _set_cost(self, cost, date, provisional, source, reference, reason=None):
        """Only writer of the cost fields (superuser mode). Callers: the receipt, the
        bill posting, reset and cancellation (phase 2f), the migration and the
        correction wizard (manual, Accounting / Administrator, with a reason)."""
        if source == "manual":
            if not (self.env.su or self.env.user.has_group(COST_MANAGER_GROUP)):
                raise AccessError(_("Only accounting administrators can correct an equipment "
                                    "cost."))
            if not reason:
                raise ValidationError(_("A reason is required to correct a cost."))
        elif not self.env.su:
            raise AccessError(_("The equipment cost is set by the business actions."))
        sources = dict(self._fields["cost_source"]._description_selection(self.env))
        for equipment in self:
            old = equipment.sudo()
            before = (old.cost_known, old.cost, old.cost_provisional, old.cost_source,
                      old.cost_reference)
            vals = {"cost": cost if cost is not None else 0.0, "cost_known": cost is not None,
                    "cost_date": date or False, "cost_provisional": bool(provisional),
                    "cost_source": source, "cost_reference": reference or False}
            after = (vals["cost_known"], vals["cost"], vals["cost_provisional"], source,
                     vals["cost_reference"])
            if before == after:
                continue
            equipment.sudo().write(vals)
            body = _("Cost %(cost)s %(currency)s (%(state)s), source: %(origin)s %(ref)s, "
                     "date %(date)s, by %(user)s.",
                     cost=vals["cost"] if cost is not None else _("unknown"),
                     currency=equipment.company_id.currency_id.name or "",
                     state=_("provisional") if provisional else _("final"),
                     origin=sources.get(source, source), ref=reference or "",
                     date=date or "-", user=self.env.user.name)
            if reason:
                body += " " + _("Reason: %s", reason)
            # as superuser: an accounting administrator may not write the equipment; the
            # author stays the real user
            equipment.sudo().message_post(body=body, author_id=self.env.user.partner_id.id)
        return True

    def _order_cost(self, purchase_line, date):
        """Estimate from an order line: unit price after discount, per product unit,
        in company currency at `date`."""
        self.ensure_one()
        pol = purchase_line.sudo()
        company = pol.company_id or self.company_id
        price = pol.price_unit * (1 - (pol.discount or 0.0) / 100.0)
        if pol.product_uom and pol.product_uom != pol.product_id.uom_id:
            price = pol.product_uom._compute_price(price, pol.product_id.uom_id)
        return pol.currency_id._convert(price, company.currency_id, company, date, round=False)

    def _set_cost_from_order(self, purchase_line, date, reference=None):
        for equipment in self:
            current = equipment.sudo()
            if current.cost_known and current.cost_source == "bill" and not current.cost_provisional:
                continue  # the bill (posted before the receipt) already gave the real cost
            equipment._set_cost(
                equipment._order_cost(purchase_line, date), date, True, "order",
                reference or _("%(order)s – %(product)s",
                               order=purchase_line.order_id.name,
                               product=purchase_line.product_id.display_name))

    def _receipt_order_line(self):
        """Order line and date of the purchase receipt operation of this equipment."""
        self.ensure_one()
        line = self.env["equipment.operation.line"].sudo().search([
            ("equipment_id", "=", self.id), ("purchase_line_id", "!=", False),
            ("operation_id.operation_type", "=", "receipt"), ("operation_id.state", "=", "done"),
        ], order="id desc", limit=1)
        if not line:
            return None, None
        when = line.operation_id.execution_date
        return line.purchase_line_id, (when.date() if when else line.operation_id.date)

    def _cost_after_bill_unlink(self, bill, source):
        """The bill line link is about to be removed (cancellation: `bill_cancelled`;
        quantity lowered on a draft bill: `bill_released`): back to the order estimate
        if the equipment was received on an order, otherwise the amount is kept as
        provisional with an explained source."""
        for equipment in self.sudo():
            pol, date = equipment._receipt_order_line()
            if pol:
                equipment._set_cost_from_order(pol, date)
                continue
            if not equipment.cost_known:
                continue
            reference = (_("%s (cancelled)", bill.name) if source == "bill_cancelled"
                         else _("released from %s", bill.name))
            equipment._set_cost(equipment.cost, equipment.cost_date, True, source, reference)

    # ------------------------------------------------------------- central methods

    def _set_ownership(self, status, owner, reason):
        """Only writer of ownership_status / owner_partner_id. Callers: the phase 2
        business actions (already in superuser mode after their own checks) and the
        correction wizard (ownership managers)."""
        if not self.env.su and not self.env.user.has_group(
            "maintenance_shareholder_equipment.group_equipment_ownership_manager"
        ):
            raise AccessError(_("Only equipment ownership managers can change the ownership."))
        if not reason:
            raise ValidationError(_("A reason is required to change the ownership."))
        author = self.env.user
        for equipment in self:
            old = (equipment.ownership_status, equipment.owner_partner_id.display_name)
            equipment.sudo().write({"ownership_status": status, "owner_partner_id": owner.id})
            equipment._check_stock_owner_consistency(raise_error=True)
            equipment.message_post(
                body=_("Ownership changed by %(user)s from %(old_status)s (%(old_owner)s) to "
                       "%(status)s (%(owner)s). Reason: %(reason)s",
                       user=author.name, old_status=old[0], old_owner=old[1],
                       status=status, owner=owner.display_name, reason=reason),
            )
        return True

    def action_finalize_integration(self):
        """Check that the equipment is complete, then mark it integrated."""
        if not (self.env.su or self.env.user.has_group("maintenance.group_equipment_manager")):
            raise AccessError(_("Only equipment managers can integrate an equipment."))
        for equipment in self:
            missing = equipment._integration_missing()
            if missing:
                raise ValidationError(
                    _("%(name)s cannot be integrated, missing: %(missing)s",
                      name=equipment.display_name, missing=", ".join(missing))
                )
            equipment._check_stock_owner_consistency(raise_error=True)
        self.sudo().write({"integration_state": "done"})
        for equipment in self:
            equipment.message_post(body=_("Integrated by %s.", self.env.user.name))
        return True

    def _integration_missing(self):
        self.ensure_one()
        missing = []
        if bool(self.stock_lot_id) == bool(self.current_location_id):
            missing.append(_("a serial number in stock or a location for non-stock "
                             "equipment (exactly one of them)"))
        if not self.warranty_status:
            missing.append(_("warranty status"))
        if not self.insurance_status:
            missing.append(_("insurance status"))
        if self.ownership_status in THIRD_PARTY_OWNED and not (
            self.replacement_value and self.replacement_currency_id and self.replacement_value_date
        ):
            missing.append(_("replacement value, currency and date"))
        if not valid_responsible(self.owner_user_id, self.company_id):
            missing.append(_("a responsible (active internal user of the company)"))
        return missing

    # ----------------------------------------------------------------- constraints

    @api.constrains(
        "integration_state", "stock_lot_id", "current_location_id", "warranty_status",
        "insurance_status", "ownership_status", "replacement_value",
        "replacement_currency_id", "replacement_value_date", "owner_user_id",
    )
    def _check_integrated_complete(self):
        for equipment in self.filtered(lambda e: e.integration_state == "done" and e.active):
            missing = equipment._integration_missing()
            if missing:
                raise ValidationError(
                    _("%(name)s is integrated and must keep: %(missing)s",
                      name=equipment.display_name, missing=", ".join(missing))
                )

    @api.constrains("ownership_status", "owner_partner_id", "company_id")
    def _check_owner_matches_status(self):
        for equipment in self:
            company_partner = (equipment.company_id or self.env.company).partner_id
            if equipment.ownership_status in COMPANY_OWNED and equipment.owner_partner_id != company_partner:
                raise ValidationError(
                    _("%(name)s: an owned or lent-out item belongs to the company.",
                      name=equipment.display_name)
                )
            if equipment.ownership_status in THIRD_PARTY_OWNED and equipment.owner_partner_id == company_partner:
                raise ValidationError(
                    _("%(name)s: a borrowed or rented item belongs to a third party.",
                      name=equipment.display_name)
                )

    @api.constrains("stock_lot_id", "product_id", "company_id", "current_location_id")
    def _check_lot(self):
        for equipment in self.filtered("stock_lot_id"):
            lot = equipment.stock_lot_id
            if equipment.product_id and lot.product_id != equipment.product_id:
                raise ValidationError(
                    _("%(name)s: the serial number belongs to another product.",
                      name=equipment.display_name)
                )
            if lot.company_id and equipment.company_id and lot.company_id != equipment.company_id:
                raise ValidationError(
                    _("%(name)s: the serial number belongs to another company.",
                      name=equipment.display_name)
                )
            if equipment.current_location_id:
                raise ValidationError(
                    _("%(name)s has a serial number in stock: its location comes from the "
                      "stock, the non-stock location must stay empty.",
                      name=equipment.display_name)
                )

    @api.constrains("current_location_id", "company_id")
    def _check_non_stock_location(self):
        """The location of a non-stock equipment is a stock the monitor follows: active,
        internal, same company (any place type: a vehicle lent to a third party sits in
        a lent-out stock)."""
        for equipment in self.filtered("current_location_id"):
            loc = equipment.current_location_id
            if not (loc.active and loc.usage == "internal") or (
                loc.company_id and equipment.company_id and loc.company_id != equipment.company_id
            ):
                raise ValidationError(
                    _("%(name)s: the location must be an active internal stock of the same "
                      "company.", name=equipment.display_name)
                )

    @api.constrains("asset_id", "company_id")
    def _check_asset_company(self):
        for equipment in self.filtered("asset_id"):
            if equipment.company_id and equipment.asset_id.company_id != equipment.company_id:
                raise ValidationError(
                    _("%(name)s: the fixed asset belongs to another company.",
                      name=equipment.display_name)
                )

    @api.constrains("move_line_id")
    def _check_single_bill_line(self):
        """Side 1 of the bill line link (see account.move.line): an equipment is listed
        by at most one line of a non-cancelled bill, and only by its own line."""
        Line = self.env["account.move.line"].sudo()
        for equipment in self.filtered("move_line_id"):
            other = Line.search_count([
                ("equipment_ids", "in", equipment.id),
                ("id", "!=", equipment.move_line_id.id),
                ("parent_state", "!=", "cancel"),
            ])
            if other:
                raise ValidationError(
                    _("%(name)s is already linked to another supplier bill line.",
                      name=equipment.display_name)
                )

    # ----------------------------------------------------------- stock consistency

    def _expected_stock_owner(self):
        self.ensure_one()
        return self.owner_partner_id if self.ownership_status in THIRD_PARTY_OWNED else self.env[
            "res.partner"
        ]

    def _stock_owner_mismatch(self):
        """Positive internal quants of the serial number whose owner differs from the
        ownership (empty for the company, the third party otherwise)."""
        self.ensure_one()
        if not self.stock_lot_id:
            return self.env["stock.quant"]
        quants = self.env["stock.quant"].sudo().search([
            ("lot_id", "=", self.stock_lot_id.id),
            ("quantity", ">", 0),
            ("location_id.usage", "=", "internal"),
        ])
        expected = self._expected_stock_owner()
        return quants.filtered(lambda q: q.owner_id != expected)

    def _internal_quants(self):
        """Positive quants of the serial number in internal locations."""
        self.ensure_one()
        if not self.stock_lot_id:
            return self.env["stock.quant"]
        return self.env["stock.quant"].sudo().search([
            ("lot_id", "=", self.stock_lot_id.id),
            ("quantity", ">", 0),
            ("location_id.usage", "=", "internal"),
        ])

    def _check_stock_owner_consistency(self, raise_error=False):
        self.ensure_one()
        mismatch = self._stock_owner_mismatch()
        if mismatch and raise_error:
            raise ValidationError(
                _("%(name)s: the owner on stock (%(stock_owner)s) does not match the "
                  "ownership (%(status)s).",
                  name=self.display_name,
                  stock_owner=", ".join(mismatch.owner_id.mapped("display_name")) or _("company"),
                  status=self.ownership_status)
            )
        return not mismatch

    @api.model
    def _cron_check_ownership_consistency(self):
        """Daily: one open activity per inconsistent equipment, never a duplicate;
        nothing is corrected automatically."""
        activity_type = self.env.ref(
            "maintenance_shareholder_equipment.mail_activity_ownership_check"
        )
        equipments = self.sudo().search([
            ("integration_state", "=", "done"), ("stock_lot_id", "!=", False)
        ])
        for equipment in equipments:
            if equipment._check_stock_owner_consistency():
                continue
            if equipment.activity_ids.filtered(lambda a: a.activity_type_id == activity_type):
                continue
            equipment.activity_schedule(
                activity_type_id=activity_type.id,
                user_id=(equipment.technician_user_id or self.env.ref("base.user_admin")).id,
                note=_("The owner of the serial number on stock differs from the "
                       "equipment's ownership. Check the stock or correct the ownership."),
            )

"""ROADMAP section 0 (docs/roadmap0/PLAN.md, revision 5, §2): product creation request.

A persistent document: draft → to approve → approved → done (refused, cancelled). The
approval freezes a signature of the decisive data (§2.10) and the supporting documents;
any change sends it back to approval. The execution, in one transaction, locks the
request, recomputes the accounting treatment and compares it with the signature,
checks the duplicates again, reserves the canonical keys (partial unique indexes) and
creates the product in superuser mode. It never creates a bill, an order or a move.
"""
import json

import psycopg2

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .maintenance_equipment import INSURANCE_STATUS, WARRANTY_STATUS
from .product_catalogue import FAMILIES, normalise_barcode, normalise_reference

MANAGER_GROUP = "maintenance_shareholder_equipment.group_product_catalogue_manager"
REQUESTER_GROUPS = (
    "maintenance_shareholder_equipment.group_equipment_operator",
    "purchase.group_purchase_user",
    "stock.group_stock_user",
)
STATES = [
    ("draft", "Draft"),
    ("to_approve", "To Approve"),
    ("approved", "Approved"),
    ("done", "Done"),
    ("refused", "Refused"),
    ("cancel", "Cancelled"),
]
CLOSED_STATES = ("done", "refused", "cancel")
# canonical keys reserved by the executed requests (partial unique indexes, init())
KEY_FIELDS = ("key_default_code", "key_barcode", "key_supplier")
# writes allowed on a closed request: chatter, activities, followers
CHATTER_PREFIXES = ("message_", "activity_", "website_message")


class ProductCreationRequest(models.Model):
    _name = "product.creation.request"
    _description = "Product Creation Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _check_company_auto = True
    _mail_post_access = "read"

    name = fields.Char(readonly=True, copy=False, default="/")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True)
    state = fields.Selection(STATES, default="draft", required=True, readonly=True,
                             copy=False, tracking=True, index=True)
    family = fields.Selection(FAMILIES, required=True, tracking=True)
    requester_id = fields.Many2one("res.users", string="Requester", required=True,
                                   readonly=True, default=lambda self: self.env.user,
                                   copy=False)
    responsible_id = fields.Many2one("res.users", string="Responsible", tracking=True,
                                     default=lambda self: self.env.user)
    approver_id = fields.Many2one("res.users", readonly=True, copy=False)
    approval_date = fields.Datetime(readonly=True, copy=False)
    approval_snapshot = fields.Text(readonly=True, copy=False, groups="base.group_system")
    approved_documents = fields.Text(string="Approved Document Checksums", readonly=True,
                                     copy=False, groups="base.group_system")
    approved_attachment_ids = fields.Many2many(
        "ir.attachment", "product_creation_request_approved_attachment_rel", "request_id",
        "attachment_id", string="Approved Documents", readonly=True, copy=False)
    executor_id = fields.Many2one("res.users", string="Executed by", readonly=True, copy=False)
    execution_date = fields.Datetime(readonly=True, copy=False)
    decision_note = fields.Text(string="Reason", tracking=True, copy=False,
                                help="Reason of a refusal or a cancellation.")
    product_tmpl_id = fields.Many2one("product.template", string="Product Created",
                                      readonly=True, copy=False)
    similar_confirmed = fields.Boolean(
        string="Similar Products Checked", copy=False,
        help="The approver checked the products with a similar name or supplier reference.")

    # product
    product_name = fields.Char(string="Product Name", required=True, tracking=True)
    default_code = fields.Char(string="Internal Reference", tracking=True)
    barcode = fields.Char(tracking=True)
    description = fields.Text()
    image_1920 = fields.Image(string="Photo", max_width=1920, max_height=1920)
    uom_id = fields.Many2one("uom.uom", string="Unit", required=True,
                             default=lambda self: self.env.ref("uom.product_uom_unit"))
    uom_po_id = fields.Many2one("uom.uom", string="Purchase Unit", required=True,
                                default=lambda self: self.env.ref("uom.product_uom_unit"))
    purchase_ok = fields.Boolean(string="Can be Purchased", default=True)
    sale_ok = fields.Boolean(string="Can be Sold", default=False)
    categ_id = fields.Many2one(
        "product.category", string="Product Category", required=True, tracking=True,
        domain="[('request_ready', '=', True)]")
    equipment_category_id = fields.Many2one(
        "maintenance.equipment.category", string="Equipment Category", tracking=True,
        domain="[('assignable', '=', True)]")
    tracking = fields.Selection(
        [("none", "By Quantity"), ("lot", "By Lots"), ("serial", "By Unique Serial Number")],
        string="Tracking", default="none",
        help="Durable equipment: always by serial number. Materials, consumables and goods: "
        "by quantity or by lots.")
    supplier_id = fields.Many2one("res.partner", string="Supplier", check_company=True)
    supplier_code = fields.Char(string="Supplier Reference")
    currency_id = fields.Many2one(
        "res.currency", string="Supplier Currency",
        compute="_compute_currency_id", store=True, readonly=False, precompute=True)
    supplier_price = fields.Monetary(string="Supplier Price (excl. tax)",
                                     currency_field="currency_id")
    min_qty = fields.Float(string="Minimum Quantity")
    delay = fields.Integer(string="Lead Time (days)")
    supplier_taxes_ids = fields.Many2many(
        "account.tax", "product_creation_request_supplier_tax_rel", "request_id", "tax_id",
        string="Purchase Taxes", check_company=True,
        domain="[('type_tax_use', '=', 'purchase'), ('company_id', 'parent_of', company_id)]")
    taxes_ids = fields.Many2many(
        "account.tax", "product_creation_request_sale_tax_rel", "request_id", "tax_id",
        string="Sale Taxes", check_company=True,
        domain="[('type_tax_use', '=', 'sale'), ('company_id', 'parent_of', company_id)]")
    company_currency_id = fields.Many2one(related="company_id.currency_id")
    list_price = fields.Monetary(string="Sale Price (excl. tax)",
                                 currency_field="company_currency_id")
    standard_price = fields.Monetary(string="Initial Cost (excl. tax)",
                                     currency_field="company_currency_id")
    attachment_ids = fields.Many2many(
        "ir.attachment", "product_creation_request_attachment_rel", "request_id",
        "attachment_id", string="Supporting Documents",
        help="Quotes, data sheets. Frozen at approval: an approved document cannot be "
        "removed or replaced; further documents may be added.")

    # canonical keys (stored: the duplicate search and the unique indexes use them)
    key_default_code = fields.Char(compute="_compute_keys", store=True, copy=False)
    key_barcode = fields.Char(compute="_compute_keys", store=True, copy=False)
    key_supplier = fields.Char(compute="_compute_keys", store=True, copy=False)

    # deduced and shown (§2.3)
    product_type = fields.Char(string="Product Type", compute="_compute_treatment")
    income_account_id = fields.Many2one("account.account", compute="_compute_treatment",
                                        string="Income Account")
    expense_account_id = fields.Many2one("account.account", compute="_compute_treatment",
                                         string="Expense Account")
    stock_valuation_account_id = fields.Many2one(
        "account.account", compute="_compute_treatment", string="Stock Valuation Account")
    asset_profile_id = fields.Many2one("account.asset.profile", compute="_compute_treatment",
                                       string="Asset Profile")
    cost_method = fields.Char(compute="_compute_treatment")
    valuation = fields.Char(string="Inventory Valuation", compute="_compute_treatment")
    warranty_status = fields.Selection(WARRANTY_STATUS, compute="_compute_treatment",
                                       string="Default Warranty")
    insurance_status = fields.Selection(INSURANCE_STATUS, compute="_compute_treatment",
                                        string="Default Insurance")
    treatment_text = fields.Char(string="Accounting Treatment", compute="_compute_treatment")
    duplicate_text = fields.Text(string="Possible Duplicates", compute="_compute_duplicates")

    # ------------------------------------------------------------------ database

    def init(self):
        """Partial unique indexes on the keys of the executed requests (§2.8): of two
        concurrent executions with the same key, the second fails at its write. Odoo
        has no declarative partial unique index; DDL only, no data written."""
        for key in KEY_FIELDS:
            self.env.cr.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS product_creation_request_%s_done_uniq "
                "ON product_creation_request (company_id, %s) "
                "WHERE state = 'done' AND %s IS NOT NULL AND %s <> ''" % (key, key, key, key))

    # ------------------------------------------------------------------ computes

    @api.depends("supplier_id", "company_id")
    def _compute_currency_id(self):
        for request in self:
            request.currency_id = (request.supplier_id.property_purchase_currency_id
                                   or request.company_id.currency_id)

    @api.depends("default_code", "barcode", "supplier_id", "supplier_code")
    def _compute_keys(self):
        for request in self:
            request.key_default_code = normalise_reference(request.default_code)
            request.key_barcode = normalise_barcode(request.barcode)
            code = normalise_reference(request.supplier_code)
            request.key_supplier = ("%s:%s" % (request.supplier_id.commercial_partner_id.id, code)
                                    if code and request.supplier_id else False)

    def _product_values(self):
        """Type, storage, tracking and maintenance deduced from the family (§2.2)."""
        self.ensure_one()
        family = self.family
        if family == "durable_equipment":
            return {"type": "consu", "is_storable": True, "tracking": "serial",
                    "maintenance_ok": True}
        if family in ("material", "consumable", "goods"):
            return {"type": "consu", "is_storable": True,
                    "tracking": self.tracking if self.tracking in ("none", "lot") else "none",
                    "maintenance_ok": False}
        if family == "service":
            return {"type": "service", "is_storable": False, "tracking": "none",
                    "maintenance_ok": False}
        return {"type": "consu", "is_storable": False, "tracking": "none",
                "maintenance_ok": False}

    def _treatment(self):
        """Accounting treatment of the request under the current configuration."""
        self.ensure_one()
        categ = self.categ_id.with_company(self.company_id)
        Template = self.env["product.template"]
        if not categ:
            return {}
        expense = Template._catalogue_category_account(categ, "property_account_expense_categ_id")
        income = Template._catalogue_category_account(categ, "property_account_income_categ_id")
        return {
            "income": income.id, "expense": expense.id,
            "stock_input": categ.property_stock_account_input_categ_id.id,
            "stock_output": categ.property_stock_account_output_categ_id.id,
            "stock_valuation": categ.property_stock_valuation_account_id.id,
            "profile": expense.asset_profile_id.id,
            "cost_method": categ.property_cost_method,
            "valuation": categ.property_valuation,
            "warranty": categ.default_warranty_status or False,
            "insurance": categ.default_insurance_status or False,
        }

    @api.depends("family", "categ_id", "company_id", "tracking")
    def _compute_treatment(self):
        Account = self.env["account.account"].sudo()
        for request in self:
            treatment = request._treatment() if request.family else {}
            values = request._product_values() if request.family else {}
            request.product_type = ", ".join(filter(None, [
                values.get("type") == "service" and _("service") or values.get("type") and _("goods"),
                values.get("is_storable") and _("stored"),
                values.get("tracking") == "serial" and _("serial number"),
                values.get("tracking") == "lot" and _("lots"),
                values.get("maintenance_ok") and _("maintainable"),
            ])) or False
            request.income_account_id = treatment.get("income")
            request.expense_account_id = treatment.get("expense")
            request.stock_valuation_account_id = treatment.get("stock_valuation")
            request.asset_profile_id = treatment.get("profile")
            request.cost_method = treatment.get("cost_method") or False
            request.valuation = treatment.get("valuation") or False
            request.warranty_status = treatment.get("warranty")
            request.insurance_status = treatment.get("insurance")
            text = False
            if treatment.get("profile"):
                text = _("Posting the bill creates a fixed asset (account %s).",
                         Account.browse(treatment["expense"]).code)
            elif treatment.get("expense"):
                text = _("Purchases on account %s; no fixed asset.",
                         Account.browse(treatment["expense"]).code)
            request.treatment_text = text

    @api.depends("product_name", "key_default_code", "key_barcode", "key_supplier", "company_id")
    def _compute_duplicates(self):
        for request in self:
            blocking, similar = request._find_duplicates()
            lines = [_("Blocking: %s", text) for text in blocking]
            lines += [_("Similar: %s", text) for text in similar]
            request.duplicate_text = "\n".join(lines) or False

    # ------------------------------------------------------------------ duplicates

    def _find_duplicates(self):
        """(blocking, similar): exact internal reference, barcode or supplier reference
        of a product, archived included, or of another executed request; similar names
        and supplier references to be confirmed by the approver (§2.10)."""
        self.ensure_one()
        Product = self.env["product.product"].sudo().with_context(active_test=False)
        company_domain = ["|", ("company_id", "=", False), ("company_id", "=", self.company_id.id)]
        blocking, similar = [], []
        if self.key_default_code:
            # candidates containing every word of the key (stored values may carry other
            # spaces or cases), then the exact comparison of the normalised forms
            words = [("default_code", "ilike", word) for word in self.key_default_code.split()]
            for product in Product.search(company_domain + words):
                if normalise_reference(product.default_code) == self.key_default_code:
                    blocking.append(_("internal reference of %s", product.display_name))
        if self.key_barcode:
            for product in Product.search([("barcode", "=", self.key_barcode)]):
                blocking.append(_("barcode of %s", product.display_name))
        if self.key_supplier:
            infos = self.env["product.supplierinfo"].sudo().with_context(active_test=False).search([
                ("partner_id.commercial_partner_id", "=", self.supplier_id.commercial_partner_id.id),
                ("product_code", "!=", False)])
            for info in infos:
                if normalise_reference(info.product_code) == normalise_reference(self.supplier_code):
                    blocking.append(_("supplier reference of %s", info.product_tmpl_id.display_name))
        others = self.sudo().search([("id", "!=", self.id or 0), ("state", "=", "done"),
                                     ("company_id", "=", self.company_id.id)])
        for key in KEY_FIELDS:
            if self[key] and others.filtered(lambda r, key=key: r[key] == self[key]):
                blocking.append(_("same %(key)s as request %(other)s", key=key.replace("key_", ""),
                                  other=", ".join(others.filtered(
                                      lambda r, key=key: r[key] == self[key]).mapped("name"))))
        name = " ".join((self.product_name or "").split()).lower()
        if name:
            words = [("name", "ilike", word) for word in name.split()]
            for product in Product.search(company_domain + words):
                if " ".join((product.name or "").split()).lower() == name:
                    similar.append(_("name of %s", product.display_name))
        return blocking, similar

    # ------------------------------------------------------------------ checks

    def _check_values(self):
        """Checks of the request, on the server (§2.9, §2.10)."""
        for request in self:
            company = request.company_id
            if not request._family_has_ready_category():
                problems = [_("the family « %s » waits for the accountant (C24 / C25): no "
                              "product category is ready for it yet.",
                              dict(FAMILIES)[request.family])]
            else:
                problems = request.categ_id._request_problems(
                    request.family, company, purchase_ok=request.purchase_ok,
                    sale_ok=request.sale_ok)
            if request.family == "durable_equipment":
                if not request.equipment_category_id:
                    problems.append(_("durable equipment needs its equipment category."))
            if request.equipment_category_id:
                try:
                    request.equipment_category_id._check_assignable()
                except ValidationError as error:
                    problems.append(str(error.args[0]))
            if request.uom_id.category_id != request.uom_po_id.category_id:
                problems.append(_("the unit and the purchase unit are not of the same kind."))
            for tax in request.supplier_taxes_ids:
                if tax.type_tax_use != "purchase" or not tax.active or \
                        tax.company_id not in company.parent_ids:
                    problems.append(_("%s is not an active purchase tax of the company.", tax.name))
            for tax in request.taxes_ids:
                if tax.type_tax_use != "sale" or not tax.active or \
                        tax.company_id not in company.parent_ids:
                    problems.append(_("%s is not an active sale tax of the company.", tax.name))
            if request.supplier_id and request.supplier_id.company_id \
                    and request.supplier_id.company_id != company:
                problems.append(_("the supplier belongs to another company."))
            if problems:
                raise ValidationError(_("%(request)s: %(problems)s", request=request.name,
                                        problems=" ".join(problems)))

    def _family_has_ready_category(self):
        self.ensure_one()
        ready = self.env["product.category"].sudo().search([("request_ready", "=", True)])
        return any(categ._catalogue_family() == self.family for categ in ready)

    def _signature(self):
        """Decisive data frozen by the approval (§2.10), accounting treatment included."""
        self.ensure_one()
        request = self.sudo()
        data = {
            "company": request.company_id.id, "family": request.family,
            "name": request.product_name, "default_code": request.key_default_code or "",
            "barcode": request.key_barcode or "", "categ": request.categ_id.id,
            "equipment_category": request.equipment_category_id.id,
            "values": request._product_values(), "uom": request.uom_id.id,
            "uom_po": request.uom_po_id.id, "purchase_ok": request.purchase_ok,
            "sale_ok": request.sale_ok, "supplier": request.supplier_id.id,
            "supplier_code": request.supplier_code or "", "currency": request.currency_id.id,
            "supplier_price": request.supplier_price, "min_qty": request.min_qty,
            "delay": request.delay, "supplier_taxes": sorted(request.supplier_taxes_ids.ids),
            "taxes": sorted(request.taxes_ids.ids), "list_price": request.list_price,
            "standard_price": request.standard_price, "treatment": request._treatment(),
        }
        return json.dumps(data, sort_keys=True)

    def _documents_signature(self):
        self.ensure_one()
        return json.dumps({str(att.id): att.checksum for att in self.sudo().attachment_ids},
                          sort_keys=True)

    def _signature_differences(self):
        self.ensure_one()
        try:
            before = json.loads(self.sudo().approval_snapshot or "{}")
        except ValueError:
            before = {}
        now = json.loads(self._signature())
        diffs = []
        for key in sorted(set(before) | set(now)):
            if key == "treatment":
                old, new = before.get(key) or {}, now.get(key) or {}
                diffs += ["%s: %s → %s" % (sub, old.get(sub), new.get(sub))
                          for sub in sorted(set(old) | set(new)) if old.get(sub) != new.get(sub)]
            elif before.get(key) != now.get(key):
                diffs.append("%s: %s → %s" % (key, before.get(key), now.get(key)))
        return diffs

    def _approved_documents_changed(self):
        """Approved documents missing or with another content."""
        self.ensure_one()
        try:
            approved = json.loads(self.sudo().approved_documents or "{}")
        except ValueError:
            approved = {}
        current = {str(att.id): att.checksum for att in self.sudo().attachment_ids}
        return [att_id for att_id, checksum in approved.items() if current.get(att_id) != checksum]

    # ------------------------------------------------------------------ rights

    def _is_manager(self):
        return self.env.su or self.env.user.has_group(MANAGER_GROUP)

    def _is_requester(self):
        return self.env.su or self._is_manager() or any(
            self.env.user.has_group(group) for group in REQUESTER_GROUPS)

    def _lock(self):
        """Row lock (phase 2 pattern): a concurrent approval or execution of the same
        request fails instead of running twice (read lock, no SQL write)."""
        if not self.ids:
            return
        try:
            self.env.cr.execute(
                "SELECT id FROM product_creation_request WHERE id IN %s FOR UPDATE NOWAIT",
                [tuple(self.ids)])
        except psycopg2.errors.LockNotAvailable:
            raise UserError(_("This request is being processed by someone else.")) from None
        self.invalidate_recordset()

    # ------------------------------------------------------------------ ORM

    @api.model_create_multi
    def create(self, vals_list):
        if not self._is_requester():
            raise AccessError(_("Only equipment operators, buyers, inventory users and "
                                "catalogue managers can request a product."))
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "product.creation.request") or "/"
        return super().create(vals_list)

    def write(self, vals):
        # the request's own transitions write in superuser mode; a client cannot obtain
        # it, whatever context it sends (no context key opens these checks)
        if not self.env.su:
            business = [key for key in vals if not key.startswith(CHATTER_PREFIXES)]
            for request in self:
                if request.state in CLOSED_STATES and business:
                    raise UserError(_("%s is closed: it can no longer be changed.", request.name))
            if "attachment_ids" in vals:
                for request in self.filtered(lambda r: r.state in ("approved", "done")):
                    removed = request.approved_attachment_ids - self._new_attachments(
                        request, vals["attachment_ids"])
                    if removed:
                        raise UserError(_("%s: an approved document cannot be removed.",
                                          request.name))
        result = super().write(vals)
        if not self.env.su:
            self._invalidate_changed_approvals()
        return result

    @api.model
    def _new_attachments(self, request, commands):
        """Attachments after applying the x2many commands to the request's current ones."""
        records = request.attachment_ids
        for command in commands:
            if command[0] == Command.SET:
                records = self.env["ir.attachment"].browse(command[2])
            elif command[0] in (Command.UNLINK, Command.DELETE):
                records -= self.env["ir.attachment"].browse(command[1])
            elif command[0] == Command.LINK:
                records |= self.env["ir.attachment"].browse(command[1])
            elif command[0] == Command.CLEAR:
                records = self.env["ir.attachment"]
        return records

    def _invalidate_changed_approvals(self):
        for request in self.filtered(lambda r: r.state == "approved"):
            diffs = request._signature_differences()
            if diffs:
                request._back_to_approval(_("Approval cancelled: the request changed."), diffs)

    def _back_to_approval(self, reason, details):
        self.ensure_one()
        self.sudo().write({
            "state": "to_approve", "approver_id": False, "approval_date": False,
            "approval_snapshot": False, "approved_documents": False,
            "approved_attachment_ids": [Command.clear()], "similar_confirmed": False})
        self.message_post(body="%s %s" % (reason, "; ".join(details)))
        self._notify_approvers()

    def unlink(self):
        for request in self:
            if request.state != "draft":
                raise UserError(_("%s is not a draft: cancel it instead.", request.name))
        return super().unlink()

    # ------------------------------------------------------------------ workflow

    def action_submit(self):
        self._lock()
        for request in self:
            if request.state != "draft":
                raise UserError(_("%s is not a draft.", request.name))
            if not request._is_requester():
                raise AccessError(_("Not allowed."))
            request._check_values()
            request.sudo().write(
                {"state": "to_approve"})
            request._notify_approvers()
        return True

    def action_approve(self):
        self._lock()
        for request in self:
            if not request._is_manager():
                raise AccessError(_("Only product catalogue managers can approve a request."))
            if request.state != "to_approve":
                raise UserError(_("%s is not waiting for approval.", request.name))
            if not self.env.su and request.requester_id == self.env.user:
                raise UserError(_("%s: the requester cannot approve his own request.",
                                  request.name))
            request._check_values()
            blocking, similar = request._find_duplicates()
            if blocking:
                raise UserError(_("%(request)s: duplicate: %(items)s.", request=request.name,
                                  items="; ".join(blocking)))
            if similar and not request.similar_confirmed:
                raise UserError(_(
                    "%(request)s: similar products exist (%(items)s). Check them, then tick "
                    "« Similar Products Checked ».", request=request.name,
                    items="; ".join(similar)))
            request.sudo().write({
                "state": "approved", "approver_id": self.env.user.id,
                "approval_date": fields.Datetime.now(),
                "approval_snapshot": request._signature(),
                "approved_documents": request._documents_signature(),
                "approved_attachment_ids": [Command.set(request.attachment_ids.ids)],
            })
            request.sudo().activity_unlink(["mail.mail_activity_data_todo"])
            request.message_post(body=_("Approved by %s.", self.env.user.name))
        return True

    def action_execute(self):
        """One transaction (§2.8). Returns to approval, without creating anything, when
        the treatment or the approved documents changed."""
        self._lock()
        for request in self:
            if not request._is_manager():
                raise AccessError(_("Only product catalogue managers can execute a request."))
            if request.state != "approved":
                raise UserError(_("%s is already executed or being executed, or not approved.",
                                  request.name))
            diffs = request._signature_differences()
            changed_documents = request._approved_documents_changed()
            if diffs or changed_documents:
                if changed_documents:
                    diffs.append(_("approved documents changed"))
                request._back_to_approval(
                    _("Not executed: the request or its accounting treatment changed since "
                      "the approval."), diffs)
                continue
            request._check_values()
            blocking, _similar = request._find_duplicates()
            if blocking:
                raise UserError(_("%(request)s: duplicate: %(items)s.", request=request.name,
                                  items="; ".join(blocking)))
            request._execute()
        return True

    def _execute(self):
        """Reserve the keys (unique indexes) and create the product, in the same
        transaction: any error afterwards rolls both back."""
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                self.sudo().write({
                    "state": "done", "executor_id": self.env.user.id,
                    "execution_date": fields.Datetime.now()})
                self.flush_recordset()
        except (psycopg2.errors.UniqueViolation, psycopg2.errors.LockNotAvailable):
            self.invalidate_recordset()
            raise UserError(_(
                "%s: another request with the same internal reference, barcode or supplier "
                "reference was executed at the same time. Refresh the page: the other "
                "request is then listed as a duplicate.", self.name)) from None
        template = self._create_product()
        self.sudo().write(
            {"product_tmpl_id": template.id})
        self.message_post(body=_("Product created: %s.", template.display_name))

    def _create_product(self):
        self.ensure_one()
        request = self.sudo()
        vals = dict(request._product_values(), **{
            "name": request.product_name, "default_code": request.default_code or False,
            "barcode": request.key_barcode or False, "description": request.description,
            "categ_id": request.categ_id.id, "uom_id": request.uom_id.id,
            "uom_po_id": request.uom_po_id.id, "purchase_ok": request.purchase_ok,
            "sale_ok": request.sale_ok, "list_price": request.list_price,
            "standard_price": request.standard_price, "company_id": request.company_id.id,
            "supplier_taxes_id": [Command.set(request.supplier_taxes_ids.ids)],
            "taxes_id": [Command.set(request.taxes_ids.ids)],
            "equipment_category_id": request.equipment_category_id.id,
            "image_1920": request.image_1920,
        })
        if request.supplier_id:
            vals["seller_ids"] = [Command.create({
                "partner_id": request.supplier_id.id, "product_code": request.supplier_code,
                "currency_id": request.currency_id.id, "price": request.supplier_price,
                "min_qty": request.min_qty, "delay": request.delay,
                "company_id": request.company_id.id})]
        template = self.env["product.template"].sudo().with_company(request.company_id).create(vals)
        for attachment in request.attachment_ids:
            attachment.copy({"res_model": "product.template", "res_id": template.id})
        return template

    def action_refuse(self):
        self._lock()
        for request in self:
            if not request._is_manager():
                raise AccessError(_("Only product catalogue managers can refuse a request."))
            if request.state not in ("to_approve", "approved"):
                raise UserError(_("%s cannot be refused in its current state.", request.name))
            if not request.decision_note:
                raise UserError(_("%s: give the reason of the refusal.", request.name))
            request.sudo().write({"state": "refused"})
            request.sudo().activity_unlink(["mail.mail_activity_data_todo"])
        return True

    def action_cancel(self):
        self._lock()
        for request in self:
            if request.state not in ("draft", "to_approve", "approved"):
                raise UserError(_("%s cannot be cancelled.", request.name))
            if not (request._is_manager() or request.requester_id == self.env.user):
                raise AccessError(_("Only the requester or a catalogue manager can cancel."))
            request.sudo().write({"state": "cancel"})
            request.sudo().activity_unlink(["mail.mail_activity_data_todo"])
        return True

    def action_reset_draft(self):
        self._lock()
        for request in self:
            if request.state not in ("to_approve", "approved"):
                raise UserError(_("%s cannot go back to draft.", request.name))
            if not (request._is_manager() or request.requester_id == self.env.user):
                raise AccessError(_("Not allowed."))
            request.sudo().write({
                "state": "draft", "approver_id": False, "approval_date": False,
                "approval_snapshot": False, "approved_documents": False,
                "approved_attachment_ids": [Command.clear()], "similar_confirmed": False})
        return True

    def _notify_approvers(self):
        for request in self:
            approvers = self.env.ref(MANAGER_GROUP).sudo().users.filtered(
                lambda u, r=request: r.company_id in u.company_ids and u != r.requester_id)
            for user in approvers:
                request.sudo().activity_schedule(
                    "mail.mail_activity_data_todo", user_id=user.id,
                    summary=_("Product request to approve"))

    def copy(self, default=None):
        """A refused or cancelled request is duplicated into a new draft (§2.8)."""
        default = dict(default or {}, state="draft", requester_id=self.env.user.id)
        return super().copy(default)


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def _check_approved_request_documents(self):
        requests = self.env["product.creation.request"].sudo().search([
            ("approved_attachment_ids", "in", self.ids),
            ("state", "in", ("approved", "done"))])
        if requests:
            raise UserError(_("Approved documents of %s cannot be removed or replaced.",
                              ", ".join(requests.mapped("name"))))

    def unlink(self):
        if self.ids:
            self._check_approved_request_documents()
        return super().unlink()

    def write(self, vals):
        if self.ids and {"datas", "raw", "db_datas", "store_fname", "url"} & set(vals):
            self._check_approved_request_documents()
        return super().write(vals)


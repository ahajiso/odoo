"""ROADMAP section 0 (docs/roadmap0/PLAN.md §2.4; audit of dad9933): controlled, traced
correction of a product's **default equipment category**, the only structural field
without stock or accounting effect. Category, tracking, units, storage and accounts are
changed only by the audited migration script, then by the future modification request.
The catalogue manager gives the new category and a reason; the correction checks it and
applies it in superuser mode; the before / after values stay on the correction (never
deleted with the product) and in the product's chatter."""
import psycopg2

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

MANAGER_GROUP = "maintenance_shareholder_equipment.group_product_catalogue_manager"
# set only by the correction itself (superuser mode), refused to any client
PROTECTED_FIELDS = {"name", "state", "before_values", "after_values", "user_id", "date"}


class ProductStructuralCorrection(models.Model):
    _name = "product.structural.correction"
    _description = "Product Structural Correction"
    _inherit = ["mail.thread"]
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(readonly=True, copy=False, default="/")
    product_tmpl_id = fields.Many2one("product.template", string="Product", required=True,
                                      ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="product_tmpl_id.company_id", store=True)
    state = fields.Selection([("draft", "Draft"), ("done", "Applied")], default="draft",
                             readonly=True, tracking=True, copy=False)
    reason = fields.Text(required=True, tracking=True)
    equipment_category_id = fields.Many2one(
        "maintenance.equipment.category", string="New Equipment Category", required=True,
        domain="[('assignable', '=', True)]")
    before_values = fields.Text(readonly=True, copy=False)
    after_values = fields.Text(readonly=True, copy=False)
    user_id = fields.Many2one("res.users", string="Applied by", readonly=True, copy=False)
    date = fields.Datetime(string="Applied on", readonly=True, copy=False)

    def _is_manager(self):
        return self.env.su or self.env.user.has_group(MANAGER_GROUP)

    @api.model_create_multi
    def create(self, vals_list):
        if not self._is_manager():
            raise AccessError(_("Only product catalogue managers correct a product."))
        for vals in vals_list:
            if not self.env.su and PROTECTED_FIELDS.intersection(vals):
                raise AccessError(_("This field is set by the correction itself."))
            vals["name"] = self.env["ir.sequence"].next_by_code(
                "product.structural.correction") or "/"
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            if PROTECTED_FIELDS.intersection(vals):
                raise AccessError(_("This field is set by the correction itself."))
            if any(rec.state == "done" for rec in self) and any(
                    not key.startswith("message_") for key in vals):
                raise UserError(_("An applied correction can no longer be changed."))
            if "product_tmpl_id" in vals and any(
                    rec.product_tmpl_id.id != vals["product_tmpl_id"] for rec in self):
                raise UserError(_("The product of a correction cannot be changed."))
        return super().write(vals)

    def unlink(self):
        if not self.env.su and any(rec.state == "done" for rec in self):
            raise UserError(_("An applied correction is kept as a trace."))
        return super().unlink()

    def _lock(self):
        """Row lock: a correction applied twice at the same time fails (read lock)."""
        if not self.ids:
            return
        try:
            self.env.cr.execute(
                "SELECT id FROM product_structural_correction WHERE id IN %s FOR UPDATE NOWAIT",
                [tuple(self.ids)])
        except psycopg2.errors.LockNotAvailable:
            raise UserError(_("This correction is being applied by someone else.")) from None
        self.invalidate_recordset()

    def action_apply(self):
        self._lock()
        for correction in self:
            if not correction._is_manager():
                raise AccessError(_("Only product catalogue managers correct a product."))
            if correction.state != "draft":
                raise UserError(_("%s is already applied.", correction.name))
            if not (correction.reason or "").strip():
                raise UserError(_("%s: give the reason of the correction.", correction.name))
            product = correction.product_tmpl_id
            category = correction.equipment_category_id
            # the same checks as a request, before the write in superuser mode
            category._check_assignable()
            if not product.maintenance_ok:
                raise ValidationError(_("%s is not maintainable: it has no equipment category.",
                                        product.display_name))
            before = product.equipment_category_id.display_name or "-"
            # write and every check in a savepoint: a refused correction leaves the
            # product exactly as it was
            with self.env.cr.savepoint():
                product.sudo().write({"equipment_category_id": category.id})
                product.flush_recordset()
                family = product.categ_id._catalogue_family()
                if family:
                    problems = product._family_problems(family)
                    if problems:
                        raise ValidationError(" ".join(problems))
            after = category.display_name
            correction.sudo().write({
                "state": "done", "user_id": self.env.user.id, "date": fields.Datetime.now(),
                "before_values": before, "after_values": after,
            })
            product.sudo().message_post(body=_(
                "Structural correction %(name)s by %(user)s. Reason: %(reason)s. Default "
                "equipment category: %(before)s → %(after)s",
                name=correction.name, user=self.env.user.name, reason=correction.reason,
                before=before, after=after))
        return True

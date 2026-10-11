"""ROADMAP section 0 (docs/roadmap0/PLAN.md §2.4): controlled, traced correction of the
structural fields of a product, until the modification request exists. The catalogue
manager gives the new values and a reason; the correction checks them like a request
(family rules, equipment category usable, category available) and applies them in
superuser mode; the before / after values stay on the correction and in the product's
chatter."""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .product_catalogue import STRUCTURAL_FIELDS

MANAGER_GROUP = "maintenance_shareholder_equipment.group_product_catalogue_manager"
# fields this correction may change (attribute lines stay refused, PLAN.md §2.7)
CORRECTABLE = ("categ_id", "equipment_category_id", "uom_id", "uom_po_id", "tracking",
               "is_storable", "maintenance_ok", "property_account_income_id",
               "property_account_expense_id")


class ProductStructuralCorrection(models.Model):
    _name = "product.structural.correction"
    _description = "Product Structural Correction"
    _inherit = ["mail.thread"]
    _order = "id desc"

    name = fields.Char(readonly=True, copy=False, default="/")
    product_tmpl_id = fields.Many2one("product.template", string="Product", required=True,
                                      ondelete="cascade")
    company_id = fields.Many2one(related="product_tmpl_id.company_id")
    state = fields.Selection([("draft", "Draft"), ("done", "Applied")], default="draft",
                             readonly=True, tracking=True, copy=False)
    reason = fields.Text(required=True, tracking=True)
    categ_id = fields.Many2one("product.category", string="New Product Category")
    equipment_category_id = fields.Many2one(
        "maintenance.equipment.category", string="New Equipment Category",
        domain="[('assignable', '=', True)]")
    uom_id = fields.Many2one("uom.uom", string="New Unit")
    uom_po_id = fields.Many2one("uom.uom", string="New Purchase Unit")
    tracking = fields.Selection(
        [("none", "By Quantity"), ("lot", "By Lots"), ("serial", "By Unique Serial Number")],
        string="New Tracking")
    is_storable = fields.Selection([("yes", "Stored"), ("no", "Not stored")],
                                   string="New Storage")
    maintenance_ok = fields.Selection([("yes", "Maintainable"), ("no", "Not maintainable")],
                                      string="New Maintenance")
    property_account_income_id = fields.Many2one("account.account", string="New Income Account")
    property_account_expense_id = fields.Many2one("account.account",
                                                  string="New Expense Account")
    before_values = fields.Text(readonly=True, copy=False)
    after_values = fields.Text(readonly=True, copy=False)
    user_id = fields.Many2one("res.users", string="Applied by", readonly=True, copy=False)
    date = fields.Datetime(string="Applied on", readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if not (self.env.su or self.env.user.has_group(MANAGER_GROUP)):
            raise AccessError(_("Only product catalogue managers correct a product."))
        for vals in vals_list:
            vals["name"] = self.env["ir.sequence"].next_by_code(
                "product.structural.correction") or "/"
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and any(rec.state == "done" for rec in self) and any(
                not key.startswith("message_") for key in vals):
            raise UserError(_("An applied correction can no longer be changed."))
        return super().write(vals)

    def _new_values(self):
        self.ensure_one()
        vals = {}
        for name in CORRECTABLE:
            value = self[name]
            if name in ("is_storable", "maintenance_ok"):
                if value:
                    vals[name] = value == "yes"
            elif self._fields[name].type == "many2one":
                if value:
                    vals[name] = value.id
            elif value:
                vals[name] = value
        return vals

    @staticmethod
    def _display(record, name):
        value = record[name]
        if hasattr(value, "display_name"):
            return value.display_name or "-"
        return str(value)

    def action_apply(self):
        for correction in self:
            if not (self.env.su or self.env.user.has_group(MANAGER_GROUP)):
                raise AccessError(_("Only product catalogue managers correct a product."))
            if correction.state != "draft":
                raise UserError(_("%s is already applied.", correction.name))
            if not (correction.reason or "").strip():
                raise UserError(_("%s: give the reason of the correction.", correction.name))
            vals = correction._new_values()
            if not vals:
                raise UserError(_("%s: no new value.", correction.name))
            if not set(vals) <= set(STRUCTURAL_FIELDS):
                raise UserError(_("%s: only structural fields are corrected here.",
                                  correction.name))
            product = correction.product_tmpl_id
            # the same checks as a request, before the write in superuser mode
            if correction.equipment_category_id:
                correction.equipment_category_id._check_assignable()
            if correction.categ_id and correction.categ_id._catalogue_family() and \
                    not correction.categ_id.request_ready:
                raise ValidationError(_("The category %s is not available yet.",
                                        correction.categ_id.display_name))
            before = {name: correction._display(product, name) for name in vals}
            # write and every check in a savepoint: a refused correction leaves the
            # product exactly as it was (the constraints run in the write, the family
            # rules are checked again explicitly before the savepoint is released)
            with self.env.cr.savepoint():
                product.sudo().with_company(product.company_id or self.env.company).write(vals)
                product.flush_recordset()
                family = product.categ_id._catalogue_family()
                if family:
                    problems = product._family_problems(family)
                    if problems:
                        raise ValidationError(" ".join(problems))
            after = {name: correction._display(product, name) for name in vals}
            lines = ["%s: %s → %s" % (product._fields[name].get_description(self.env)["string"],
                                      before[name], after[name]) for name in vals]
            correction.sudo().write({
                "state": "done", "user_id": self.env.user.id, "date": fields.Datetime.now(),
                "before_values": "\n".join("%s: %s" % item for item in before.items()),
                "after_values": "\n".join("%s: %s" % item for item in after.items()),
            })
            product.sudo().message_post(body=_(
                "Structural correction %(name)s by %(user)s. Reason: %(reason)s. %(changes)s",
                name=correction.name, user=self.env.user.name, reason=correction.reason,
                changes="; ".join(lines)))
        return True

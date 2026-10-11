"""ROADMAP section 0 (docs/roadmap0/PLAN.md, revision 5): governed product catalogue.

- Products are created only in superuser mode: by the execution of a product creation
  request (product_creation_request.py), by the migration script and by module
  installations. Nobody creates one directly, the catalogue manager included.
- The structural fields of a product are locked outside superuser mode until the
  modification request exists; exceptional corrections go through the « Structural
  correction » (product_structural_correction.py).
- The family of a product is not stored: it is the branch of its product category
  (roots with an external ID, data/product_category_roots.xml).
- Equipment categories are never created silently: the product carries its default
  equipment category.
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

MODULE = "maintenance_shareholder_equipment"

# family -> roots of its product categories (external IDs of this module)
FAMILY_ROOTS = {
    "durable_equipment": ("categ_root_fixed_assets", "categ_root_small_equipment"),
    "material": ("categ_root_materials",),
    "consumable": ("categ_root_consumables",),
    "goods": ("categ_root_goods",),
    "service": ("categ_root_services_purchased", "categ_root_sales"),
    "intangible": ("categ_root_intangible",),
}
FAMILIES = [
    ("durable_equipment", "Durable equipment"),
    ("material", "Construction material"),
    ("consumable", "Consumable or accessory"),
    ("goods", "Goods for resale"),
    ("service", "Service"),
    ("intangible", "Intangible asset"),
]
# fields locked outside superuser mode (PLAN.md §2.4); `standard_price` is not one of
# them: the average cost evolves with the operations
STRUCTURAL_FIELDS = (
    "categ_id", "type", "is_storable", "tracking", "maintenance_ok", "uom_id", "uom_po_id",
    "property_account_income_id", "property_account_expense_id", "equipment_category_id",
    "attribute_line_ids", "company_id",
)


def normalise_reference(value):
    """Internal and supplier references: trimmed, inner spaces collapsed, upper case."""
    return " ".join((value or "").split()).upper() or False


def normalise_barcode(value):
    """Barcode: Odoo's own uniqueness is exact; only the outer spaces are removed."""
    return (value or "").strip() or False


class ProductCategory(models.Model):
    _inherit = "product.category"

    request_ready = fields.Boolean(
        string="Available for Product Requests",
        help="Product creation requests may use this category. Set it only once the "
        "category's accounts, cost method and valuation are final (accountant).",
    )

    def _catalogue_family(self):
        """Family of the category, from the root of its branch (none outside them)."""
        self.ensure_one()
        root_ids = {int(x) for x in (self.parent_path or "").split("/") if x}
        for family, roots in FAMILY_ROOTS.items():
            for xmlid in roots:
                root = self.env.ref("%s.%s" % (MODULE, xmlid), raise_if_not_found=False)
                if root and root.id in root_ids:
                    return family
        return False

    def _is_small_equipment(self):
        self.ensure_one()
        root = self.env.ref("%s.categ_root_small_equipment" % MODULE, raise_if_not_found=False)
        return bool(root) and str(root.id) in (self.parent_path or "").split("/")

    def _request_problems(self, family, company, purchase_ok=True, sale_ok=False):
        """Why this category cannot receive a product of the family for the company
        (empty list: it can). Only final configurations are accepted (PLAN.md §2.9)."""
        self.ensure_one()
        categ = self.with_company(company)
        problems = []
        if categ._catalogue_family() != family:
            problems.append(_("the category %s is not in the branch of this family.",
                              categ.display_name))
            return problems
        if not categ.request_ready:
            problems.append(_("the category %s is not available for product requests yet.",
                              categ.display_name))
        tmpl = self.env["product.template"]
        expense = tmpl._catalogue_category_account(categ, "property_account_expense_categ_id")
        income = tmpl._catalogue_category_account(categ, "property_account_income_categ_id")
        if family == "durable_equipment":
            if categ._is_small_equipment():
                if not expense:
                    problems.append(_("no expense account on %s.", categ.display_name))
            elif not (categ.is_fixed_asset_stock and categ.property_valuation == "manual_periodic"
                      and expense.asset_profile_id):
                problems.append(_("%s is not a complete fixed-asset category (fixed-asset flag, "
                                  "manual valuation, expense account with an asset profile).",
                                  categ.display_name))
        elif family in ("material", "consumable", "goods"):
            if not (categ.property_valuation == "real_time"
                    and categ.property_stock_valuation_account_id
                    and categ.property_stock_account_input_categ_id
                    and categ.property_stock_account_output_categ_id):
                problems.append(_("%s has no automatic valuation with its stock accounts "
                                  "(accountant).", categ.display_name))
        elif family == "intangible":
            if not expense.asset_profile_id:
                problems.append(_("%s has no account with an asset profile.", categ.display_name))
        if family == "service":
            if purchase_ok and not expense:
                problems.append(_("no expense account on %s.", categ.display_name))
            if sale_ok and not income:
                problems.append(_("no income account on %s.", categ.display_name))
        return problems


class MaintenanceEquipmentCategory(models.Model):
    _inherit = "maintenance.equipment.category"

    # PLAN.md §3.4: a category still referenced is archived, never deleted
    active = fields.Boolean(default=True)
    assignable = fields.Boolean(
        string="Usable for Products",
        help="Products and requests may take this category as their default equipment "
        "category. Off for « To classify » and for the categories created automatically "
        "before the catalogue (ROADMAP section 0).",
    )

    def _check_assignable(self):
        for category in self:
            if not (category.active and category.assignable):
                raise ValidationError(_(
                    "The equipment category « %s » cannot be used for a product: archived, "
                    "transitional or created automatically.", category.display_name))


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # ROADMAP 0.1: label of maintenance_product (« Can be Maintenance »)
    maintenance_ok = fields.Boolean(string="Can be maintained")
    equipment_category_id = fields.Many2one(
        "maintenance.equipment.category", string="Default Equipment Category",
        domain="[('assignable', '=', True)]",
        help="Equipment category of the items of this product, used at their receipt and "
        "by their bill lines. Mandatory for durable equipment; no category is ever "
        "created automatically.",
    )

    @api.model
    def _catalogue_category_account(self, categ, field_name):
        """Category account as Odoo uses it (income and expense go up the hierarchy)."""
        while categ:
            if categ[field_name]:
                return categ[field_name]
            if field_name not in ("property_account_income_categ_id",
                                  "property_account_expense_categ_id"):
                break
            categ = categ.parent_id
        return self.env["account.account"]

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_(
                "Products are created through a product creation request (Inventory → "
                "Products → Product Requests), never directly."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            self._check_structural_write(vals)
        return super().write(vals)

    def _check_structural_write(self, vals):
        changed = set()
        for name in STRUCTURAL_FIELDS:
            if name not in vals or name not in self._fields:
                continue
            if name == "attribute_line_ids":
                changed.add(name)
                continue
            field = self._fields[name]
            for product in self:
                old = product[name]
                new = vals[name]
                if field.type == "many2one":
                    old = old.id
                    new = new.id if isinstance(new, models.BaseModel) else (new or False)
                if old != new:
                    changed.add(name)
        if changed:
            labels = sorted(self._fields[name].get_description(self.env)["string"]
                            for name in changed)
            raise UserError(_(
                "Structural fields of a product cannot be changed directly (%s): use a "
                "Structural Correction (with its reason) until the modification request "
                "exists.", ", ".join(labels)))

    @api.constrains("categ_id", "type", "is_storable", "tracking", "maintenance_ok",
                    "equipment_category_id")
    def _check_catalogue_family(self):
        """Family rules for the products of a family branch (PLAN.md §2.2). Products of
        the other categories (`All`, historical ones) are checked only when a
        structural field changes, which only superuser mode may do."""
        for product in self:
            family = product.categ_id._catalogue_family()
            if not family:
                continue
            problems = product._family_problems(family)
            if problems:
                raise ValidationError(_("%(product)s: %(problems)s", product=product.display_name,
                                        problems=" ".join(problems)))

    def _family_problems(self, family):
        self.ensure_one()
        problems = []
        if family == "durable_equipment":
            if not (self.type == "consu" and self.is_storable and self.tracking == "serial"
                    and self.maintenance_ok):
                problems.append(_("durable equipment is storable, tracked by serial number "
                                  "and maintainable."))
            if not self.equipment_category_id:
                problems.append(_("durable equipment needs its default equipment category."))
        elif family in ("material", "consumable", "goods"):
            if not (self.type == "consu" and self.is_storable and not self.maintenance_ok
                    and self.tracking != "serial"):
                problems.append(_("materials, consumables and goods are storable, tracked by "
                                  "quantity (lot optional) and not maintainable."))
        elif family == "service":
            if self.type != "service" or self.maintenance_ok:
                problems.append(_("a service is of type service and not maintainable."))
        elif family == "intangible":
            if self.type != "consu" or self.is_storable or self.maintenance_ok:
                problems.append(_("an intangible asset is neither stored nor maintainable."))
        if self.equipment_category_id and not (self.equipment_category_id.active
                                               and self.equipment_category_id.assignable):
            problems.append(_("its equipment category is archived, transitional or automatic."))
        return problems

    def _create_product_variant(self, combination, log_warning=False):
        """PLAN.md §2.7: a dynamic variant asked outside superuser mode is refused
        before the core creates it with its own sudo(); returning an existing variant
        is unchanged."""
        self.ensure_one()
        if (not self.env.su and self.has_dynamic_attributes()
                and not self._get_variant_for_combination(combination)):
            raise AccessError(_(
                "New variants of %s are created through a product request, never from a "
                "sale or purchase line.", self.display_name))
        return super()._create_product_variant(combination, log_warning=log_warning)


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_(
                "Products are created through a product creation request (Inventory → "
                "Products → Product Requests), never directly."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            template_vals = {k: v for k, v in vals.items() if k in STRUCTURAL_FIELDS}
            if template_vals:
                self.product_tmpl_id._check_structural_write(template_vals)
        return super().write(vals)

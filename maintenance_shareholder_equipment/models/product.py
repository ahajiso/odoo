from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .maintenance_equipment import INSURANCE_STATUS, WARRANTY_STATUS


class ProductCategory(models.Model):
    _inherit = "product.category"

    is_fixed_asset_stock = fields.Boolean(
        string="Fixed Assets Tracked in Stock",
        help="Items of this category are fixed assets: quantity and location come from "
        "stock, value from the fixed asset. Requires, for each company: manual "
        "valuation, an expense account of class 21 with an asset profile creating one "
        "asset per unit.",
    )
    default_warranty_status = fields.Selection(WARRANTY_STATUS)
    default_insurance_status = fields.Selection(INSURANCE_STATUS)

    @api.constrains("is_fixed_asset_stock", "property_valuation",
                    "property_account_expense_categ_id")
    def _check_fixed_asset_stock(self):
        # Categories are shared between companies: checked for each company the user
        # works in when saving (the selected companies), with that company's values.
        companies = self.env.companies.filtered("chart_template")
        for categ in self.filtered("is_fixed_asset_stock"):
            for company in companies:
                errors = categ.with_company(company)._fixed_asset_setup_errors()
                if errors:
                    raise ValidationError(
                        _("Category %(categ)s, company %(company)s: %(errors)s",
                          categ=categ.display_name, company=company.name,
                          errors="; ".join(errors))
                    )

    def _fixed_asset_setup_errors(self):
        """Checks for the current company (call with with_company())."""
        self.ensure_one()
        errors = []
        if self.property_valuation != "manual_periodic":
            errors.append(_("valuation must be manual"))
        account = self.property_account_expense_categ_id
        if not account or not account.code or not account.code.startswith("21"):
            errors.append(_("the expense account must be a class 21 fixed-asset account"))
        elif not account.asset_profile_id:
            errors.append(_("the expense account must carry an asset profile"))
        elif not account.asset_profile_id.asset_product_item:
            errors.append(_("the asset profile must create one asset per unit"))
        elif account.asset_profile_id.company_id != self.env.company:
            errors.append(_("the asset profile belongs to another company"))
        return errors


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.constrains("maintenance_ok", "is_storable", "tracking")
    def _check_equipment_serial(self):
        for template in self:
            if template.maintenance_ok and template.is_storable and template.tracking != "serial":
                raise ValidationError(
                    _("%(name)s is an equipment kept in stock: it must be tracked by "
                      "unique serial number.", name=template.display_name)
                )

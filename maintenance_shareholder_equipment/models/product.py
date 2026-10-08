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
        # Archived products are ignored: archiving is one of the choices offered for a
        # product that cannot be serialised (docs/phase1/setup_phase1.py).
        unserialised = self.env["product.template"].search([
            ("categ_id", "=", self.id), ("is_storable", "=", True), ("tracking", "!=", "serial"),
        ])
        if unserialised:
            errors.append(_("storable products must be tracked by serial number: %s",
                            ", ".join(unserialised.mapped("display_name"))))
        return errors

    @api.model
    def _recheck_fixed_asset_categories(self, accounts):
        """Re-run the category checks when an account or an asset profile they rely on
        changes, so that the guarantees stay true after configuration."""
        for company in self.env.companies.filtered("chart_template"):
            categs = self.with_company(company).search([
                ("is_fixed_asset_stock", "=", True),
                ("property_account_expense_categ_id", "in", accounts.ids),
            ])
            categs._check_fixed_asset_stock()


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.constrains("maintenance_ok", "is_storable", "tracking", "categ_id")
    def _check_equipment_serial(self):
        for template in self:
            if not template.is_storable or template.tracking == "serial":
                continue
            if template.maintenance_ok or template.categ_id.is_fixed_asset_stock:
                raise ValidationError(
                    _("%(name)s is an equipment or a fixed asset kept in stock: it must be "
                      "tracked by unique serial number.", name=template.display_name)
                )


class AccountAccount(models.Model):
    _inherit = "account.account"

    @api.constrains("asset_profile_id", "code")
    def _check_fixed_asset_categories(self):
        self.env["product.category"]._recheck_fixed_asset_categories(self)


class AccountAssetProfile(models.Model):
    _inherit = "account.asset.profile"

    @api.constrains("asset_product_item", "company_id", "account_asset_id")
    def _check_fixed_asset_categories(self):
        accounts = self.env["account.account"].search([("asset_profile_id", "in", self.ids)])
        self.env["product.category"]._recheck_fixed_asset_categories(accounts)

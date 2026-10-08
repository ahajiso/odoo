from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Test choices, see docs/QUESTIONS_COMPTABLE.md (C10, C8).
    equipment_rent_account_id = fields.Many2one(
        "account.account",
        string="Equipment Rental Expense Account",
        help="A supplier bill line on this account must be linked to the rental "
        "contract line of an equipment before posting.",
    )
    allow_asset_supplier_refund = fields.Boolean(
        string="Allow Supplier Refunds on Fixed-Asset Accounts",
        help="Off: a supplier refund (manual or reversal) with a line on an account "
        "carrying an asset profile is refused, because the asset module would create a "
        "negative asset and keep the original one.",
    )


    # Phase 2 (docs/phase2/PLAN.md, section 9; questions C10, C16, C17).
    equipment_loan_product_id = fields.Many2one(
        "product.product", string="Loan Product",
        help="Service product of the free loan contract lines (never invoiced).",
    )
    equipment_rent_paid_product_id = fields.Many2one(
        "product.product", string="Rent Product (Paid)",
        help="Service product of the rental lines of supplier contracts.",
    )
    equipment_rent_received_product_id = fields.Many2one(
        "product.product", string="Rent Product (Received)",
        help="Service product of the rental lines of customer contracts.",
    )
    equipment_gift_location_id = fields.Many2one(
        "stock.location", string="Source of Gifts",
        help="Inventory location whose account is credited by a gift (C17).",
    )
    equipment_current_account_location_id = fields.Many2one(
        "stock.location", string="Source of Current Account Contributions",
        help="Inventory location whose account is credited by a contribution to a "
        "shareholder current account (C17).",
    )
    equipment_regularisation_location_id = fields.Many2one(
        "stock.location", string="Source of Regularisations",
        help="Inventory location whose account is credited by a regularisation (C17).",
    )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    equipment_rent_account_id = fields.Many2one(
        related="company_id.equipment_rent_account_id", readonly=False
    )
    allow_asset_supplier_refund = fields.Boolean(
        related="company_id.allow_asset_supplier_refund", readonly=False
    )
    equipment_loan_product_id = fields.Many2one(
        related="company_id.equipment_loan_product_id", readonly=False
    )
    equipment_rent_paid_product_id = fields.Many2one(
        related="company_id.equipment_rent_paid_product_id", readonly=False
    )
    equipment_rent_received_product_id = fields.Many2one(
        related="company_id.equipment_rent_received_product_id", readonly=False
    )
    equipment_gift_location_id = fields.Many2one(
        related="company_id.equipment_gift_location_id", readonly=False
    )
    equipment_current_account_location_id = fields.Many2one(
        related="company_id.equipment_current_account_location_id", readonly=False
    )
    equipment_regularisation_location_id = fields.Many2one(
        related="company_id.equipment_regularisation_location_id", readonly=False
    )

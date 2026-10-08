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


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    equipment_rent_account_id = fields.Many2one(
        related="company_id.equipment_rent_account_id", readonly=False
    )
    allow_asset_supplier_refund = fields.Boolean(
        related="company_id.allow_asset_supplier_refund", readonly=False
    )

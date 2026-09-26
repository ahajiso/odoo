from odoo import fields, models


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    owner_type = fields.Selection(
        [
            ("company", "Company"),
            ("shareholder", "Shareholder"),
            ("third_party", "Third Party"),
        ],
        string="Ownership Type",
        default="company",
        required=True,
    )
    owner_partner_id = fields.Many2one(
        "res.partner",
        string="Owner (Third Party)",
    )
    accounting_ownership = fields.Selection(
        [
            ("company", "Company"),
            ("third_party", "Third Party"),
        ],
        string="Accounting Ownership",
        default="company",
    )
    handover_date = fields.Date(string="Handover Date")
    handover_value = fields.Float(string="Handover Value")
    replacement_value = fields.Float(string="Replacement Value")
    initial_condition = fields.Char(string="Initial Condition")
    return_obligation = fields.Boolean(string="Return Obligation")
    physical_wear_active = fields.Boolean(
        string="Physical Wear Tracking Active", default=True
    )
    accounting_depreciation_active = fields.Boolean(
        string="Accounting Depreciation Active", default=False
    )
    ownership_state = fields.Selection(
        [
            ("in_company_use", "In Company Use"),
            ("in_warehouse", "In Warehouse"),
            ("assigned_employee", "Assigned to Employee"),
            ("assigned_project", "Assigned to Project"),
            ("under_maintenance", "Under Maintenance"),
            ("damaged", "Damaged"),
            ("lost", "Lost"),
            ("stolen", "Stolen"),
            ("returned_to_owner", "Returned to Owner"),
            ("replaced_for_owner", "Replaced for Owner"),
            ("compensation_payable", "Compensation Payable"),
            ("compensation_paid", "Compensation Paid"),
            ("closed", "Closed"),
        ],
        string="Ownership Status",
        default="in_company_use",
    )

    # --- Physical location (independent of ownership/accounting) ---
    current_location_id = fields.Many2one(
        "stock.location",
        string="Current Location",
        tracking=True,
        help="Where the equipment physically is right now (warehouse, job site...). "
        "Independent of who owns it or its accounting value.",
    )

    # --- Fleet management: how the equipment entered the fleet ---
    acquisition_mode = fields.Selection(
        [
            ("purchase", "Purchase"),
            ("rental", "Rental"),
            ("borrowed", "Borrowed from Third Party"),
            ("loaned_out", "Loaned to Third Party"),
        ],
        string="Acquisition Mode",
        default="purchase",
        required=True,
    )
    rental_counterparty_id = fields.Many2one(
        "res.partner",
        string="Rental / Loan Counterparty",
        help="The rental company, the lender, or the borrower, depending on Acquisition Mode.",
    )
    rental_end_date = fields.Date(
        string="Rental / Loan End Date",
        help="Expected return date for a rented, borrowed, or loaned-out item.",
    )

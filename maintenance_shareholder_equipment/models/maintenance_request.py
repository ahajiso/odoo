from odoo import fields, models


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    repair_cost = fields.Float(string="Repair Cost")
    repairer = fields.Char(string="Repairer")
    repair_invoice_ref = fields.Char(string="Repair Invoice Reference")

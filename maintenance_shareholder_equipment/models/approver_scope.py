"""Read scope of the « Equipment Operations Approver » (phase 2f, decision D8).

An approver who has no other right on these models reads only the documents an
equipment operation refers to. The global rules of security.xml call
`res.users._equipment_approver_domain()`: an always-true domain for every other user,
so that the rights given by other groups (purchase, inventory, accounting, operator)
are never narrowed.
"""
from odoo import fields, models
from odoo.osv import expression

APPROVER_XMLID = "maintenance_shareholder_equipment.group_equipment_approver"

# model -> domain of the documents referenced by equipment operations
APPROVER_SCOPE = {
    "purchase.order": ["|", ("equipment_operation_ids", "!=", False),
                       ("equipment_operation_created_ids", "!=", False)],
    "purchase.order.line": ["|", "|", ("equipment_operation_line_ids", "!=", False),
                            ("order_id.equipment_operation_ids", "!=", False),
                            ("order_id.equipment_operation_created_ids", "!=", False)],
    "stock.picking": [("equipment_operation_id", "!=", False)],
    "stock.move": [("equipment_operation_id", "!=", False)],
    "stock.lot": ["|", ("equipment_operation_line_ids", "!=", False),
                  ("equipment_ids", "!=", False)],
    "contract.contract": ["|", ("equipment_operation_ids", "!=", False),
                          ("equipment_operation_created_ids", "!=", False)],
    "contract.line": ["|", "|", ("contract_id.equipment_operation_ids", "!=", False),
                      ("contract_id.equipment_operation_created_ids", "!=", False),
                      ("equipment_operation_stop_ids", "!=", False)],
    "account.move": [("equipment_operation_ids", "!=", False)],
    # lines of the documents above: their forms load them
    "account.move.line": [("move_id.equipment_operation_ids", "!=", False)],
    "stock.move.line": ["|", ("move_id.equipment_operation_id", "!=", False),
                        ("picking_id.equipment_operation_id", "!=", False)],
    # the contract form loads its modification history (OCA contract)
    "contract.modification": ["|", ("contract_id.equipment_operation_ids", "!=", False),
                              ("contract_id.equipment_operation_created_ids", "!=", False)],
    # the bill form loads the name of its journal: only the journals of those bills
    "account.journal": [("equipment_move_ids.equipment_operation_ids", "!=", False)],
}


# Standard rights given to every internal user that do not count as a real right on
# the model: stock gives `base.group_user` read, write, create and delete on every move
# line (stock/security/ir.model.access.csv, access_stock_move_line_all). An approver
# without Inventory rights must not keep them (audit of 888d229).
IGNORED_STANDARD_ACCESS = {
    "stock.move.line": "base.group_user",
}


class ResUsers(models.Model):
    _inherit = "res.users"

    def _equipment_approver_domain(self, model_name, mode="read"):
        """Domain of the global rules on `model_name` for the current user.

        `mode` "read": the approver alone reads the documents of the operations.
        `mode` "write" (write, create, unlink rules): the approver alone writes
        nothing; only used where a standard right gives every internal user write
        access (IGNORED_STANDARD_ACCESS)."""
        user = self.env.user.sudo()
        approver = self.env.ref(APPROVER_XMLID, raise_if_not_found=False)
        if not approver or approver not in user.groups_id:
            return expression.TRUE_DOMAIN
        # any other right on the model (a group other than the approver's, or a right
        # given to everyone) keeps its full scope
        groups = user.groups_id - approver
        ignored = IGNORED_STANDARD_ACCESS.get(model_name)
        if ignored:
            groups -= self.env.ref(ignored)
        perm = "perm_read" if mode == "read" else "perm_write"
        other = self.env["ir.model.access"].sudo().search_count([
            ("model_id.model", "=", model_name), (perm, "=", True),
            ("active", "=", True),
            "|", ("group_id", "=", False), ("group_id", "in", groups.ids),
        ])
        if other:
            return expression.TRUE_DOMAIN
        return APPROVER_SCOPE[model_name] if mode == "read" else expression.FALSE_DOMAIN


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    equipment_operation_ids = fields.One2many("equipment.operation", "purchase_id")
    equipment_operation_created_ids = fields.One2many("equipment.operation",
                                                      "purchase_created_id")


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    equipment_operation_line_ids = fields.One2many("equipment.operation.line",
                                                   "purchase_line_id")


class StockLot(models.Model):
    _inherit = "stock.lot"

    equipment_operation_line_ids = fields.One2many("equipment.operation.line", "lot_id")
    equipment_ids = fields.One2many("maintenance.equipment", "stock_lot_id")


class ContractContract(models.Model):
    _inherit = "contract.contract"

    equipment_operation_ids = fields.One2many("equipment.operation", "contract_id")
    # same relation table as equipment.operation.contract_ids (contracts it created)
    equipment_operation_created_ids = fields.Many2many(
        "equipment.operation", "contract_contract_equipment_operation_rel",
        "contract_contract_id", "equipment_operation_id")


class ContractLine(models.Model):
    _inherit = "contract.line"

    equipment_operation_stop_ids = fields.One2many("equipment.operation.stop",
                                                   "contract_line_id")


class AccountMove(models.Model):
    _inherit = "account.move"

    # same relation table as equipment.operation.bill_ids
    equipment_operation_ids = fields.Many2many(
        "equipment.operation", "account_move_equipment_operation_rel",
        "account_move_id", "equipment_operation_id")


class AccountJournal(models.Model):
    _inherit = "account.journal"

    # reverse of account.move.journal_id, for the approver's read rule only (D8)
    equipment_move_ids = fields.One2many("account.move", "journal_id", string="Journal Entries")

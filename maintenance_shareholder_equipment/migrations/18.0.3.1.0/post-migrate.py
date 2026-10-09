"""Phase 2f: cost of the equipment that existed before the cost fields.

- a posted supplier bill line: the bill's real cost;
- otherwise a purchase receipt operation: the estimate of its order line
  (provisional);
- otherwise an acquisition operation: its unit value;
- otherwise the cost stays unknown (listed by docs/phase2f/setup_phase2f.py).
Everything goes through maintenance.equipment._set_cost(), traced in the chatter.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Equipment = env["maintenance.equipment"].with_context(active_test=False)
    counts = {"bill": 0, "order": 0, "acquisition": 0, "unknown": 0}
    for equipment in Equipment.search([("cost_known", "=", False)]):
        line = equipment.move_line_id
        if line and line.move_id.state == "posted" and line.move_id.move_type == "in_invoice":
            line.move_id._fill_equipment_costs()
            counts["bill"] += 1
            continue
        pol, date = equipment._receipt_order_line()
        if pol:
            equipment._set_cost_from_order(pol, date)
            counts["order"] += 1
            continue
        acq = env["equipment.operation.line"].search([
            ("equipment_id", "=", equipment.id), ("unit_value", ">", 0),
            ("operation_id.receipt_branch", "=", "acquisition"),
            ("operation_id.state", "=", "done"),
        ], limit=1)
        if acq:
            op = acq.operation_id
            date = op.execution_date.date() if op.execution_date else op.date
            equipment._set_cost(acq.unit_value, date, False, "acquisition", op.name)
            counts["acquisition"] += 1
            continue
        counts["unknown"] += 1
    _logger.info("Phase 2f equipment costs: %s", counts)

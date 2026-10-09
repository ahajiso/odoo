from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

EQUIPMENT_NATURE = [
    ("rental", "Rental"),
    ("loan", "Loan (free)"),
    ("insurance", "Insurance"),
    ("maintenance", "Maintenance"),
]


class ContractLine(models.Model):
    _inherit = "contract.line"

    equipment_id = fields.Many2one(
        "maintenance.equipment", string="Equipment", index=True, ondelete="restrict"
    )
    equipment_nature = fields.Selection(
        EQUIPMENT_NATURE,
        string="Equipment Relation",
        help="Direction comes from the contract type: rental on a supplier contract = "
        "rent paid, on a customer contract = rent received. A loan line is never "
        "invoiced.",
    )

    @api.constrains("equipment_id", "equipment_nature", "product_id", "contract_id")
    def _check_equipment_line(self):
        for line in self:
            if bool(line.equipment_id) != bool(line.equipment_nature):
                raise ValidationError(
                    _("Contract line %(name)s: equipment and equipment relation go "
                      "together.", name=line.display_name)
                )
            if not line.equipment_id:
                continue
            if line.equipment_nature == "insurance" and line.contract_id.contract_type != "purchase":
                raise ValidationError(_("An insurance line belongs to a supplier contract."))
            product = line.product_id
            if not product or product.type != "service" or product.maintenance_ok:
                raise ValidationError(
                    _("Contract line %(name)s: use a service product that is not an "
                      "equipment (otherwise its bills would create equipment).",
                      name=line.display_name)
                )

    @api.constrains("equipment_id", "equipment_nature", "date_start", "date_end",
                    "is_canceled", "contract_id")
    def _check_equipment_overlap(self):
        """No overlapping periods [date_start, date_end] (empty end = open-ended) per
        equipment, relation and contract type; cancelled lines are ignored."""
        for line in self.filtered(lambda ln: ln.equipment_id and not ln.is_canceled):
            others = self.search([
                ("id", "!=", line.id),
                ("equipment_id", "=", line.equipment_id.id),
                ("equipment_nature", "=", line.equipment_nature),
                ("contract_id.contract_type", "=", line.contract_id.contract_type),
                ("is_canceled", "=", False),
            ])
            for other in others:
                starts_before_other_ends = not other.date_end or line.date_start <= other.date_end
                ends_after_other_starts = not line.date_end or line.date_end >= other.date_start
                if starts_before_other_ends and ends_after_other_starts:
                    raise ValidationError(
                        _("%(equipment)s already has a %(nature)s line from %(start)s to "
                          "%(end)s (%(contract)s).",
                          equipment=line.equipment_id.display_name,
                          nature=line.equipment_nature, start=other.date_start,
                          end=other.date_end or _("no end"),
                          contract=other.contract_id.display_name)
                    )

    @api.constrains("equipment_id", "automatic_price", "contract_id")
    def _check_equipment_automatic_price(self):
        """The rent of an equipment is the stored price of its line, in a currency that
        does not depend on a price list (phase 3)."""
        for contract in self.contract_id:
            lines = contract.contract_line_ids
            if lines.filtered("equipment_id") and lines.filtered("automatic_price"):
                raise ValidationError(_(
                    "%s: a contract with an equipment line cannot have a line with an "
                    "automatic price (price list).", contract.display_name))

    def _can_be_invoiced(self, date_ref):
        if self.equipment_nature == "loan":
            return False
        return super()._can_be_invoiced(date_ref)

    def _compute_create_invoice_visibility(self):
        res = super()._compute_create_invoice_visibility()
        for line in self.filtered(lambda ln: ln.equipment_nature == "loan"):
            line.create_invoice_visibility = False
        return res


class ContractContract(models.Model):
    _inherit = "contract.contract"

    # OCA's currency_id is computed and not stored: the stock monitor's SQL view reads
    # this stored copy, computed by OCA's own logic (phase 3, docs/phase3/PLAN.md §1-1).
    # The price-list path depends on the partner's property price list, which no
    # dependency can follow: a contract holding an equipment line has no automatic price
    # (ContractLine._check_equipment_automatic_price), so that path never applies.
    equipment_currency_id = fields.Many2one(
        "res.currency", string="Contract Currency (stored)",
        compute="_compute_equipment_currency_id", store=True,
    )

    @api.depends("manual_currency_id", "journal_id.currency_id", "company_id.currency_id",
                 "pricelist_id.currency_id", "contract_line_ids.automatic_price", "partner_id")
    def _compute_equipment_currency_id(self):
        for contract in self:
            contract.equipment_currency_id = (contract.manual_currency_id
                                              or contract._get_computed_currency())

    @api.depends("contract_line_ids.equipment_nature")
    def _compute_recurring_next_date(self):
        """OCA takes the earliest date of all non-cancelled lines (or a computed date
        when there is none): loan lines would keep a loan-only contract selected by the
        invoicing job forever. Recompute without them."""
        res = super()._compute_recurring_next_date()
        for contract in self:
            lines = contract.contract_line_ids.filtered(
                lambda ln: not ln.is_canceled and (not ln.display_type or ln.is_recurring_note)
            )
            if not lines.filtered(lambda ln: ln.equipment_nature == "loan"):
                continue
            invoiceable = lines.filtered(
                lambda ln: ln.equipment_nature != "loan" and ln.recurring_next_date
            )
            contract.recurring_next_date = (
                min(invoiceable.mapped("recurring_next_date")) if invoiceable else False
            )
        return res

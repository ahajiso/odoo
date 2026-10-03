from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression

from .ownership import OWNERSHIP_SELECTION

OWNERSHIP_CODES = [code for code, _label in OWNERSHIP_SELECTION]


class StockQuant(models.Model):
    _inherit = "stock.quant"

    # Not stored: derived from the standard owner_id, the stock's place type
    # and the consumable rental terms, so the quant grouping key is untouched.
    ownership = fields.Selection(
        OWNERSHIP_SELECTION,
        compute="_compute_ownership",
        search="_search_ownership",
    )

    def _company_partner_ids(self):
        return self.env["res.company"].sudo().search([]).partner_id.ids

    def _rented_pairs(self):
        rentals = self.env["lartdubati.stock.rental"].sudo().search([])
        return {(r.owner_id.id, r.product_id.id) for r in rentals}

    @api.depends("owner_id", "product_id", "location_id.place_type")
    def _compute_ownership(self):
        company_partner_ids = set(self._company_partner_ids())
        rented_pairs = self._rented_pairs()
        for quant in self:
            if quant.location_id.place_type == "lent_out":
                quant.ownership = "lent_out"
            elif not quant.owner_id or quant.owner_id.id in company_partner_ids:
                quant.ownership = "owned"
            elif (quant.owner_id.id, quant.product_id.id) in rented_pairs:
                quant.ownership = "rented"
            else:
                quant.ownership = "borrowed"

    def _ownership_domain(self, code):
        company_partner_ids = self._company_partner_ids()
        not_lent_out = [("location_id.place_type", "!=", "lent_out")]
        third_party = [
            ("owner_id", "!=", False),
            ("owner_id", "not in", company_partner_ids),
        ]
        rented = expression.OR(
            [
                [("owner_id", "=", owner_id), ("product_id", "=", product_id)]
                for owner_id, product_id in self._rented_pairs()
            ]
        ) or expression.FALSE_DOMAIN
        if code == "lent_out":
            return [("location_id.place_type", "=", "lent_out")]
        if code == "owned":
            return expression.AND(
                [
                    not_lent_out,
                    ["|", ("owner_id", "=", False), ("owner_id", "in", company_partner_ids)],
                ]
            )
        if code == "rented":
            return expression.AND([not_lent_out, third_party, rented])
        return expression.AND(
            [not_lent_out, third_party, ["!"] + expression.normalize_domain(rented)]
        )

    def _search_ownership(self, operator, value):
        if operator in ("=", "!="):
            value = [value]
        elif operator not in ("in", "not in"):
            raise UserError(_("Unsupported search on ownership: %s", operator))
        codes = set(value)
        if operator in ("!=", "not in"):
            codes = set(OWNERSHIP_CODES) - codes
        domains = [self._ownership_domain(code) for code in OWNERSHIP_CODES if code in codes]
        return expression.OR(domains) if domains else expression.FALSE_DOMAIN

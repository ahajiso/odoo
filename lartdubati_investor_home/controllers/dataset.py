"""P4-2e: an investor account calls only the models and methods of INVESTOR_METHODS
through /web/dataset/call_kw, call_button and resequence, checked before the standard
controller (docs/phase4/PLAN.md §2)."""
from odoo import http
from odoo.http import request

from odoo.addons.web.controllers.dataset import DataSet

from ..models.investor_security import check_investor_call


class InvestorDataSet(DataSet):

    @http.route()
    def call_kw(self, model, method, args, kwargs, path=None):
        check_investor_call(request.env, model, method)
        return super().call_kw(model, method, args, kwargs, path=path)

    @http.route()
    def call_button(self, model, method, args, kwargs, path=None):
        check_investor_call(request.env, model, method)
        return super().call_button(model, method, args, kwargs, path=path)

    @http.route()
    def resequence(self, model, ids, field="sequence", offset=0, context=None):
        check_investor_call(request.env, model, "resequence")  # never listed
        return super().resequence(model, ids, field=field, offset=offset, context=context)

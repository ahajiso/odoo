"""P4-2e: the export routes take a model name: an investor account may only use those of
INVESTOR_METHODS (in practice the stock monitor), checked before the standard
controllers. The records themselves stay governed by the default deny and the rules."""
import json

from odoo import http
from odoo.http import request

from odoo.addons.web.controllers.export import CSVExport, ExcelExport, Export

from ..models.investor_security import check_investor_call


class InvestorExport(Export):

    @http.route()
    def get_fields(self, model, domain, prefix="", parent_name="", import_compat=True,
                   parent_field_type=None, parent_field=None, exclude=None):
        check_investor_call(request.env, model, "fields_get")
        return super().get_fields(model, domain, prefix=prefix, parent_name=parent_name,
                                  import_compat=import_compat,
                                  parent_field_type=parent_field_type,
                                  parent_field=parent_field, exclude=exclude)

    @http.route()
    def namelist(self, model, export_id):
        check_investor_call(request.env, model, "export_data")
        return super().namelist(model, export_id)


def _check_export(data):
    check_investor_call(request.env, json.loads(data).get("model"), "export_data")


class InvestorCSVExport(CSVExport):

    @http.route()
    def web_export_csv(self, data):
        _check_export(data)
        return super().web_export_csv(data)


class InvestorExcelExport(ExcelExport):

    @http.route()
    def web_export_xlsx(self, data):
        _check_export(data)
        return super().web_export_xlsx(data)

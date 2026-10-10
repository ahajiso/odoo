"""P4-2e: the external API (/xmlrpc, /xmlrpc/2, /jsonrpc, service « object ») calls any
public method of any model; investor accounts have no use for it and are refused before
the call. The refusal is the same « Access Denied » as wrong credentials."""
import xmlrpc.client

from odoo import SUPERUSER_ID, api
from odoo.exceptions import AccessDenied
from odoo.http import request, route
from odoo.modules.registry import Registry

from odoo.addons.base.controllers.rpc import RPC

from ..models.investor_security import INVESTOR_GROUP


def _refuse_investor(params):
    """params of the « object » service: (db, uid, password, model, method, ...)."""
    try:
        db, uid = params[0], int(params[1])
    except (IndexError, TypeError, ValueError):
        return
    with Registry(db).cursor() as cr:
        user = api.Environment(cr, SUPERUSER_ID, {})["res.users"].browse(uid).exists()
        if user and user._has_group(INVESTOR_GROUP):
            raise AccessDenied()


class InvestorRPC(RPC):

    def _xmlrpc(self, service):
        if service == "object":
            params, _method = xmlrpc.client.loads(request.httprequest.get_data(),
                                                  use_datetime=True)
            _refuse_investor(params)
        return super()._xmlrpc(service)

    @route()
    def jsonrpc(self, service, method, args):
        if service == "object":
            _refuse_investor(args)
        return super().jsonrpc(service, method, args)

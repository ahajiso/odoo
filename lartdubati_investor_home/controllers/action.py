"""P4-2d: an investor account loads only the actions of INVESTOR_ACTIONS.

`/web/action/load` reads the action in sudo and checks no group; `load_breadcrumbs` (and
so the `/odoo/action-…` URLs) goes through `load`. The action is resolved as the
standard does (id, external ID, path) and refused before the standard controller runs.
"""
from odoo import http
from odoo.http import request

from odoo.addons.web.controllers.action import Action, MissingActionError

from ..models.investor_security import INVESTOR_ACTIONS, is_investor


class InvestorAction(Action):

    @http.route()
    def load(self, action_id, context=None):
        if is_investor(request.env) and not self._investor_may_load(action_id):
            raise MissingActionError(request.env._("The action “%s” does not exist.",
                                                   action_id))
        return super().load(action_id, context=context)

    @staticmethod
    def _investor_may_load(action_id):
        env = request.env
        allowed = set()
        for xmlid in INVESTOR_ACTIONS:
            action = env.ref(xmlid, raise_if_not_found=False)
            if action:
                allowed.add(action.id)
        try:
            return int(action_id) in allowed
        except (TypeError, ValueError):
            pass
        if not isinstance(action_id, str):
            return False
        if "." in action_id:
            action = env.ref(action_id, raise_if_not_found=False)
            return bool(action) and action._name.startswith("ir.actions.") \
                and action.id in allowed
        action = env["ir.actions.actions"].sudo().search([("path", "=", action_id)], limit=1)
        return bool(action) and action.id in allowed

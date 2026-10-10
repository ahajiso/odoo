"""Audit of 3326829: /mail/data for investor accounts. The route is needed by every page
(mail client init), but its `failures` option searches in sudo the failed notifications
of the messages the user wrote, checks only that each document still exists, and returns
the message body, the document and the recipients. An investor account may be the
author of messages on documents it can no longer read (rights removed). For investor
accounts only the options of INVESTOR_MAIL_DATA_OPTIONS are kept; the others, `failures`
included and any option a later Odoo version adds, are dropped (not refused: the web
client sends several options in one request)."""
import logging

from odoo import http
from odoo.http import request

from odoo.addons.mail.controllers.webclient import WebclientController

from ..models.investor_security import INVESTOR_MAIL_DATA_OPTIONS, is_investor

_logger = logging.getLogger(__name__)


class InvestorWebclientController(WebclientController):

    @http.route()
    def mail_data(self, **kwargs):
        if is_investor(request.env):
            dropped = set(kwargs) - INVESTOR_MAIL_DATA_OPTIONS
            if dropped:
                _logger.debug("Investor /mail/data options dropped: %s, uid %s",
                             sorted(dropped), request.env.uid)
            kwargs = {key: value for key, value in kwargs.items()
                      if key in INVESTOR_MAIL_DATA_OPTIONS}
        return super().mail_data(**kwargs)

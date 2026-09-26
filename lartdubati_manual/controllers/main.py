from . import main
import os
import re

from odoo import http
from odoo.http import request

MANUAL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "manual")
SAFE = re.compile(r"^[a-z0-9-]{1,40}$")

class LartdubatiManual(http.Controller):
    """Pages HTML statiques générées depuis le manuel Claude Docs.

    Les fichiers sont lus à chaque requête : republier le contenu
    (publier_manuel.sh) ne nécessite ni mise à jour du module ni redémarrage.
    """

    def _languages(self):
        if not os.path.isdir(MANUAL_DIR):
            return []
        return sorted(d for d in os.listdir(MANUAL_DIR) if SAFE.match(d) and os.path.isdir(os.path.join(MANUAL_DIR, d)))

    @http.route(["/manuel", "/manuel/<string:lang>"], type="http", auth="user", sitemap=False)
    def manual_root(self, lang=None, **kw):
        langs = self._languages()
        if lang not in langs:
            user_lang = (request.env.user.lang or "fr_FR").split("_")[0]
            lang = user_lang if user_lang in langs else ("fr" if "fr" in langs else (langs[0] if langs else "fr"))
        return request.redirect(f"/manuel/{lang}/index")

    @http.route("/manuel/<string:lang>/<string:page>", type="http", auth="user", sitemap=False)
    def manual_page(self, lang, page, **kw):
        if not (SAFE.match(lang) and SAFE.match(page)):
            raise request.not_found()
        path = os.path.join(MANUAL_DIR, lang, page + ".html")
        if not os.path.isfile(path):
            raise request.not_found()
        with open(path, "rb") as f:
            body = f.read()
        return request.make_response(body, headers=[
            ("Content-Type", "text/html; charset=utf-8"),
            ("Cache-Control", "no-cache"),
            ("X-Robots-Tag", "noindex"),
        ])

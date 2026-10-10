"""Phase 3, step 8: the dashboard in a real browser (docs/phase3/PLAN.md §4.5, §7)."""
from odoo.tests import HttpCase, tagged


def _hoot_error_checker(message):
    return "[HOOT]" not in message


@tagged("post_install", "-at_install")
class TestStockMonitorUnit(HttpCase):
    """Hoot tests of the client action (static/tests/*.test.js): the RPCs of the first
    display, the fields from fields_get only, keyboard and focus, RPC error."""

    def test_dashboard_unit(self):
        # a user made by the test: the admin password is unknown on a real database
        self.env["res.users"].create({
            "name": "Hoot runner", "login": "hoot_runner", "password": "hoot_runner",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])]})
        self.browser_js(
            "/web/tests?headless&loglevel=2&preset=desktop&timeout=15000"
            "&filter=stock_monitor_dashboard",
            "", "", login="hoot_runner", timeout=900,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=_hoot_error_checker,
        )


from odoo.addons.lartdubati_investor_home.tests.test_stock_monitor import (  # noqa: E402
    MonitorAccessCommon,
)


@tagged("post_install", "-at_install")
class TestStockMonitorTours(MonitorAccessCommon, HttpCase):
    """The dashboard and the analysis views on real data, for an investor without
    Inventory rights and for an accountant."""

    def test_dashboard_tours(self):
        self._receive(self._order(self.drill, 1), ["TOUR-MON"])
        for user, tour in ((self.investor, "stock_monitor_investor_tour"),
                           (self.accountant, "stock_monitor_accountant_tour")):
            with self.subTest(user=user.login):
                user.password = user.login  # start_tour logs in with login = password
                self.start_tour("/odoo/action-lartdubati_investor_home.action_stock_monitor",
                                tour, login=user.login)

    def test_investor_home_tour(self):
        """Phase 4: the investor opens the home page (home action), the dashboard from
        Financial, a « coming soon » notification; nothing refused on the way."""
        self.investor.password = self.investor.login
        self.start_tour("/odoo", "investor_home_tour", login=self.investor.login)

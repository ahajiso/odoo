"""Phase 3, P13 / C5: the dashboard on 10,000 monitor rows (docs/phase3/PLAN.md §4.3).

Not in the default run: `--test-tags /lartdubati_investor_home:TestStockMonitorPerf` or
`--test-tags monitor_perf`. The rows are generated in bulk (SQL inserts of test data
only); half of the stocks report in USD, so that every amount goes through the rate
lookups. The times are logged: server (get_dashboard_data + the list page) and browser
(from the action to the cards and the list rendered).
"""
import logging
import time

from odoo import Command
from odoo.tests import HttpCase, tagged

from odoo.addons.lartdubati_investor_home.tests.test_stock_monitor import MonitorAccessCommon

_logger = logging.getLogger(__name__)

ROWS = 10_000
EQUIPMENT = 1_000  # non-stock equipment rows, the rest consumable quants
LOCATIONS = 40


@tagged("-standard", "monitor_perf", "post_install", "-at_install")
class TestStockMonitorPerf(MonitorAccessCommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.env["res.currency.rate"].create({
            "currency_id": cls.usd.id, "name": "2020-01-01", "rate": 1.1,
            "company_id": cls.company.id})
        currency = cls.company.currency_id
        Location = env["stock.location"]
        stocks = Location.create([{
            "name": f"Perf stock {i}", "usage": "internal",
            "location_id": cls.warehouse.view_location_id.id, "is_monitor_stock": True,
            "monitor_currency_id": (cls.usd if i % 2 else currency).id,
            "address_id": cls.address.id,
        } for i in range(LOCATIONS)])
        shelves = Location.create([{"name": "Shelf", "usage": "internal", "location_id": s.id}
                                   for s in stocks])
        products = env["product.product"].create([{
            "name": f"Perf product {i}", "type": "consu", "is_storable": True,
            "standard_price": 3.0 + i, "categ_id": cls.categ_tools.id,
        } for i in range((ROWS - EQUIPMENT) // LOCATIONS)])
        env.flush_all()
        cr = env.cr
        cr.execute("""
            INSERT INTO stock_quant (product_id, location_id, company_id, quantity,
                                     reserved_quantity, in_date, create_date, write_date)
            SELECT p, l, %s, 5, 0, now(), now(), now()
              FROM unnest(%s::int[]) p CROSS JOIN unnest(%s::int[]) l
        """, [cls.company.id, products.ids, shelves.ids])
        cr.execute("""
            INSERT INTO maintenance_equipment (name, active, integration_state,
                ownership_status, owner_partner_id, company_id, current_location_id,
                owner_user_id, cost, cost_known, cost_date, effective_date, create_date,
                write_date)
            SELECT jsonb_build_object('en_US', 'Perf equipment ' || g), TRUE, 'done',
                   'owned', %s, %s, (%s::int[])[1 + g %% %s], %s, 100 + g, TRUE,
                   current_date - g, current_date, now(), now()
              FROM generate_series(1, %s) g
        """, [cls.company.partner_id.id, cls.company.id, shelves.ids, len(shelves),
              cls.user_responsible.id, EQUIPMENT])
        cls.profile.write({"country_ids": [Command.set(cls.france.ids)]})
        # statistics of the bulk-inserted tables, as autovacuum keeps them on a server
        env.flush_all()
        cr.execute("ANALYZE stock_quant, maintenance_equipment, stock_location, "
                   "product_product, product_template")

    def test_dashboard_on_10000_rows(self):
        Monitor = self.Monitor.with_user(self.accountant)
        self.env.flush_all()
        self.assertGreaterEqual(Monitor.search_count([("company_id", "=", self.company.id)]),
                                ROWS)
        for user in (self.accountant, self.investor):
            Monitor = self.Monitor.with_user(user)
            Monitor.get_dashboard_data({})  # warm the caches
            start = time.perf_counter()
            data = Monitor.get_dashboard_data({})
            Monitor.web_search_read(data["domain"], {"inventory_value": {}}, limit=25,
                                    order="stock_name, family, product_name, id",
                                    count_limit=1)
            elapsed = time.perf_counter() - start
            _logger.info("monitor_perf %s: server time %.2f s for %s rows", user.login,
                         elapsed, data["count"])
            self.assertLess(elapsed, 2.0, "P13: under 2 s on the server")
        self.accountant.password = self.accountant.login
        start = time.perf_counter()
        self.start_tour("/odoo/action-lartdubati_investor_home.action_stock_monitor",
                        "stock_monitor_perf_tour", login=self.accountant.login)
        _logger.info("monitor_perf browser: login, load and render %.2f s",
                     time.perf_counter() - start)

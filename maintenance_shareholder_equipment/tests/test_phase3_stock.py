"""Phase 3, step 4: monitor stocks, contract currency and their migration
(docs/phase3/PLAN.md §1-1, §3.2, §6.2)."""
import importlib.util
import os

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.modules.module import get_module_path
from odoo.tests import tagged

from .common import EquipmentCommon


@tagged("post_install", "-at_install")
class TestMonitorStock(EquipmentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.france = cls.env.ref("base.fr")
        cls.address = cls.env["res.partner"].create(
            {"name": "Entrepôt (test)", "city": "Bougival", "country_id": cls.france.id})

    def _location(self, **vals):
        return self.env["stock.location"].create(dict({
            "name": "Monitor stock (test)", "usage": "internal",
            "location_id": self.warehouse.view_location_id.id,
            "is_monitor_stock": True, "monitor_currency_id": self.company.currency_id.id,
            "address_id": self.address.id}, **vals))

    def test_monitor_stock_needs_address_city_country_currency(self):
        self.assertTrue(self._location().is_monitor_stock)
        no_city = self.address.copy({"city": False})
        no_country = self.address.copy({"country_id": False})
        cases = [
            ({"address_id": False}, "address with a city and a country"),
            ({"address_id": no_city.id}, "address with a city and a country"),
            ({"address_id": no_country.id}, "address with a city and a country"),
            ({"monitor_currency_id": False}, "needs a currency"),
            ({"usage": "view"}, "only an internal location"),
        ]
        for vals, message in cases:
            with self.subTest(vals=vals), self.assertRaisesRegex(ValidationError, message):
                self._location(**vals)

    def test_flag_set_later_is_checked(self):
        location = self.env["stock.location"].create({
            "name": "Plain", "usage": "internal",
            "location_id": self.warehouse.view_location_id.id})
        with self.assertRaisesRegex(ValidationError, "needs a currency"):
            location.is_monitor_stock = True
        location.write({"is_monitor_stock": True,
                        "monitor_currency_id": self.company.currency_id.id,
                        "address_id": self.address.id})
        with self.assertRaisesRegex(ValidationError, "city and a country"):
            location.address_id = False

    def test_lent_out_must_be_monitor_stock(self):
        with self.assertRaisesRegex(ValidationError, "must be a monitor stock"):
            self.env["stock.location"].create(self._lent_out_vals(
                name="Unflagged", is_monitor_stock=False))
        lent = self.env["stock.location"].create(self._lent_out_vals(name="Flagged"))
        with self.assertRaisesRegex(ValidationError, "must be a monitor stock"):
            lent.is_monitor_stock = False
        lent.active = False  # archived: not checked
        lent.is_monitor_stock = False

    def test_migration_flags_candidates_in_company_currency(self):
        lent = self.env["stock.location"].create(self._lent_out_vals(name="Lent (mig)"))
        # as before the update: neither flag nor currency (written without constraints)
        self.env.cr.execute(
            "UPDATE stock_location SET is_monitor_stock = NULL, monitor_currency_id = NULL "
            "WHERE id IN %s", [(self.stock.id, lent.id)])
        (self.stock | lent).invalidate_recordset()
        # every candidate of the database gets an address, as the precheck requires
        others = self.env["stock.warehouse"].search([]).lot_stock_id.filtered(
            lambda loc: not loc.is_monitor_stock)
        others.address_id = self.address
        self._migrate()
        for location in (self.stock, lent):
            with self.subTest(location=location.complete_name):
                self.assertTrue(location.is_monitor_stock)
                self.assertEqual(location.monitor_currency_id, self.company.currency_id)

    def test_migration_stops_on_a_candidate_without_address(self):
        self.env.cr.execute(
            "UPDATE stock_location SET is_monitor_stock = NULL, monitor_currency_id = NULL, "
            "address_id = NULL WHERE id = %s", [self.stock.id])
        self.stock.invalidate_recordset()
        with self.assertRaisesRegex(ValidationError, "city and a country"):
            self._migrate()

    def _migrate(self):
        path = os.path.join(get_module_path("maintenance_shareholder_equipment"),
                            "migrations", "18.0.4.0.0", "post-migrate.py")
        spec = importlib.util.spec_from_file_location("phase3_post_migrate", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, "18.0.3.1.0")


@tagged("post_install", "-at_install")
class TestContractCurrency(EquipmentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usd = cls.env.ref("base.USD")
        cls.chf = cls.env.ref("base.CHF")
        (cls.usd | cls.chf).active = True

    def _contract(self, line_vals=None, **vals):
        # one equipment per contract: rental lines of one equipment may not overlap
        equipment = self.env["maintenance.equipment"].create(
            {"name": "Rented lift (currency)", "current_location_id": self.stock.id})
        return self.env["contract.contract"].create(dict({
            "name": "Rental", "partner_id": self.lender.id, "contract_type": "purchase",
            "line_recurrence": True, "company_id": self.company.id,
            "contract_line_ids": [Command.create(dict({
                "product_id": self.rent_service.id, "name": "Rent", "quantity": 1,
                "price_unit": 300.0, "recurring_rule_type": "monthly",
                "recurring_interval": 1, "date_start": "2026-01-01",
                "recurring_next_date": "2026-01-01",
                "equipment_id": equipment.id, "equipment_nature": "rental",
            }, **(line_vals or {})))],
        }, **vals))

    def test_currency_follows_oca_logic(self):
        company = self._contract()
        self.assertEqual(company.equipment_currency_id, self.company.currency_id)
        self.assertEqual(company.equipment_currency_id, company.currency_id)
        manual = self._contract(manual_currency_id=self.usd.id, name="Manual")
        self.assertEqual(manual.equipment_currency_id, self.usd)
        journal = company.journal_id.copy({"code": "PCHF", "currency_id": self.chf.id})
        by_journal = self._contract(journal_id=journal.id, name="Journal")
        self.assertEqual(by_journal.equipment_currency_id, self.chf)
        self.assertEqual(by_journal.equipment_currency_id, by_journal.currency_id)

    def test_currency_recomputed_when_the_journal_changes(self):
        contract = self._contract()
        journal = contract.journal_id
        journal.currency_id = self.usd
        self.assertEqual(contract.equipment_currency_id, self.usd)
        contract.manual_currency_id = self.chf
        self.assertEqual(contract.equipment_currency_id, self.chf)
        contract.manual_currency_id = False
        self.assertEqual(contract.equipment_currency_id, self.usd)

    def test_automatic_price_refused_with_an_equipment_line(self):
        with self.assertRaisesRegex(ValidationError, "automatic price"):
            self._contract(line_vals={"automatic_price": True})
        contract = self._contract()
        with self.assertRaisesRegex(ValidationError, "automatic price"):
            contract.write({"contract_line_ids": [Command.create({
                "product_id": self.rent_service.id, "name": "Priced", "quantity": 1,
                "automatic_price": True, "recurring_rule_type": "monthly",
                "recurring_interval": 1, "date_start": "2026-01-01",
                "recurring_next_date": "2026-01-01"})]})
        # a contract without equipment line keeps OCA's price list behaviour
        plain = self.env["contract.contract"].create({
            "name": "Plain", "partner_id": self.lender.id, "contract_type": "purchase",
            "line_recurrence": True, "company_id": self.company.id,
            "contract_line_ids": [Command.create({
                "product_id": self.rent_service.id, "name": "Priced", "quantity": 1,
                "automatic_price": True, "recurring_rule_type": "monthly",
                "recurring_interval": 1, "date_start": "2026-01-01",
                "recurring_next_date": "2026-01-01"})]})
        self.assertTrue(plain.contract_line_ids.automatic_price)

"""Phase 3, step 5: the stock monitor view (docs/phase3/PLAN.md §3)."""
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.maintenance_shareholder_equipment.tests.test_operation import (
    TestOperationCommon,
)


class MonitorCommon(TestOperationCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.france = cls.env.ref("base.fr")
        cls.usd = cls.env.ref("base.USD")
        cls.chf = cls.env.ref("base.CHF")
        (cls.usd | cls.chf).active = True
        cls.address = cls.env["res.partner"].create(
            {"name": "Entrepôt Bougival (test)", "city": "Bougival", "country_id": cls.france.id})
        cls.stock.write({"is_monitor_stock": True, "address_id": cls.address.id,
                         "monitor_currency_id": cls.company.currency_id.id})
        cls.Monitor = cls.env["lartdubati.stock.monitor"]
        cls.today = fields.Date.today()

    def _rows(self, domain):
        self.env.flush_all()
        self.Monitor.invalidate_model()
        return self.Monitor.search(domain)

    def _equipment_row(self, equipment):
        row = self._rows([("id", "=", equipment.id * 2)])
        self.assertEqual(len(row), 1)
        return row

    def _quant_rows(self, product):
        return self._rows([("product_id", "=", product.id), ("family", "=", "consumable")])

    def _set_asset(self, asset, **values):
        """Asset figures written as the depreciation would leave them (the view only
        reads the columns)."""
        self.env.flush_all()
        sets = ", ".join(f"{key} = %s" for key in values)
        self.env.cr.execute(f"UPDATE account_asset SET {sets} WHERE id = %s",
                            [*values.values(), asset.id])

    def _serial_product(self, name, categ):
        return self._product(name, categ, storable=True)


@tagged("post_install", "-at_install")
class TestMonitorValues(MonitorCommon):
    """§3.4: the three values and the asset states."""

    def test_fixed_asset_states_and_salvage_value(self):
        po = self._order(self.drill, 1)
        equipment = self._receive(po, ["MON-A1"])
        self._bill(po)
        asset = equipment.asset_id
        self.assertTrue(asset)
        row = self._equipment_row(equipment)
        self.assertEqual((row.family, row.ownership_status), ("asset", "owned"))
        self.assertEqual(row.stock_id, self.stock)
        self.assertEqual((row.country_name, row.city), ("France", "Bougival"))
        self.assertAlmostEqual(row.inventory_value, asset.purchase_value)
        self.assertEqual(row.stock_value, 0)
        self.assertAlmostEqual(row.original_value, asset.purchase_value)
        self.assertEqual(row.asset_state, "draft")
        self.assertAlmostEqual(row.accounting_value, asset.purchase_value)
        self.assertEqual(row.accounting_provisional, 1)
        self.assertEqual(row.alert_asset_missing, 0)
        # running asset with depreciation and a salvage value: NBV = purchase − depreciated
        self._set_asset(asset, state="open", value_depreciated=20.0, salvage_value=10.0)
        row = self._equipment_row(equipment)
        self.assertAlmostEqual(row.accounting_value, asset.purchase_value - 20.0)
        self.assertAlmostEqual(row.depreciated_value, 20.0)
        self.assertEqual(row.accounting_provisional, 0)
        self._set_asset(asset, state="close")
        self.assertAlmostEqual(self._equipment_row(equipment).accounting_value,
                               asset.purchase_value - 20.0)
        self._set_asset(asset, state="removed")
        row = self._equipment_row(equipment)
        self.assertEqual(row.accounting_value, 0)
        self.assertEqual(row.alert_asset_removed, 1)

    def test_fixed_asset_category_before_its_bill(self):
        equipment = self._receive(self._order(self.drill, 1), ["MON-A2"])
        row = self._equipment_row(equipment)
        self.assertAlmostEqual(row.inventory_value, 100.0)  # order estimate (2f)
        self.assertEqual(row.inventory_provisional, 1)
        self.assertEqual((row.stock_value, row.accounting_value), (0, 0))
        self.assertEqual(row.alert_asset_missing, 1)
        self.assertEqual(row.alert_no_asset, 0)
        self.assertFalse(row.original_value)

    def test_expensed_equipment_has_no_accounting_value(self):
        saw = self._serial_product("Saw (expensed)", self.categ_tools)
        equipment = self._receive(self._order(saw, 1), ["MON-S1"])
        row = self._equipment_row(equipment)
        self.assertAlmostEqual(row.inventory_value, 100.0)
        self.assertEqual((row.stock_value, row.accounting_value), (0, 0))
        self.assertEqual(row.alert_no_asset, 1)
        self.assertEqual(row.alert_asset_missing, 0)

    def test_unknown_cost_is_null_not_zero(self):
        saw = self._serial_product("Saw (unknown cost)", self.categ_tools)
        equipment = self._receive(self._order(saw, 1), ["MON-S2"])
        equipment.sudo().write({"cost_known": False, "cost": 0.0})
        row = self._equipment_row(equipment)
        self.assertEqual(row.inventory_value_known, 0, "unknown, not 0")
        self.assertEqual(row.alert_cost_missing, 1)
        # a real zero stays 0, without alert
        equipment.sudo().write({"cost_known": True, "cost": 0.0})
        row = self._equipment_row(equipment)
        self.assertEqual(row.inventory_value, 0)
        self.assertEqual(row.inventory_value_known, 1)
        self.assertEqual(row.alert_cost_missing, 0)

    def test_borrowed_uses_replacement_value(self):
        op = self._borrow("MON-B1")
        op.with_user(self.user_both).action_execute()
        equipment = op.line_ids.equipment_id
        row = self._equipment_row(equipment)
        self.assertEqual(row.ownership_status, "borrowed")
        self.assertAlmostEqual(row.inventory_value, 900.0)
        self.assertAlmostEqual(row.replacement_value, 900.0)
        self.assertEqual((row.stock_value, row.accounting_value), (0, 0))
        self.assertEqual(row.alert_replacement_old, 0)
        equipment.sudo().replacement_value_date = self.today - timedelta(days=400)
        self.assertEqual(self._equipment_row(equipment).alert_replacement_old, 1)
        self.company.stock_monitor_replacement_max_age = 24
        self.assertEqual(self._equipment_row(equipment).alert_replacement_old, 0)
        self.env.cr.execute("UPDATE maintenance_equipment SET replacement_value = 0 "
                            "WHERE id = %s", [equipment.id])
        row = self._equipment_row(equipment)
        self.assertEqual(row.inventory_value_known, 0)
        self.assertEqual(row.alert_replacement_missing, 1)

    def test_consumable_at_average_cost_and_negative_quant(self):
        Quant = self.env["stock.quant"]
        Quant._update_available_quantity(self.screws, self.stock, 10)
        row = self._quant_rows(self.screws)
        self.assertEqual(len(row), 1)
        self.assertEqual(row.quantity, 10)
        self.assertAlmostEqual(row.inventory_value, 10 * self.screws.standard_price)
        # manual valuation: the books carry nothing
        self.assertEqual((row.stock_value, row.accounting_value), (0, 0))
        Quant._update_available_quantity(self.screws, self.stock, -15)
        row = self._quant_rows(self.screws)
        self.assertEqual(row.quantity, -5)
        self.assertAlmostEqual(row.inventory_value, -5 * self.screws.standard_price)
        self.assertEqual(row.alert_negative_quantity, 1)

    def test_draft_and_archived_equipment_absent(self):
        draft = self.env["maintenance.equipment"].create(
            {"name": "Draft (monitor)", "current_location_id": self.stock.id})
        self.assertNotEqual(draft.integration_state, "done")
        self.assertFalse(self._rows([("id", "=", draft.id * 2)]))
        equipment = self._receive(self._order(self.drill, 1), ["MON-AR"])
        self.assertTrue(self._rows([("id", "=", equipment.id * 2)]))
        equipment.sudo().active = False
        self.assertFalse(self._rows([("id", "=", equipment.id * 2)]))


@tagged("post_install", "-at_install")
class TestMonitorPlacement(MonitorCommon):
    """§3.1-3.2: grain, unique ids, stock resolution, serial positions."""

    def _internal(self, name, parent, **vals):
        return self.env["stock.location"].create(dict(
            {"name": name, "usage": "internal", "location_id": parent.id}, **vals))

    def test_nearest_stock_and_sub_location_without_address(self):
        shelf = self._internal("Shelf", self.stock)
        other_address = self.address.copy({"name": "Annexe", "city": "Rueil"})
        annex = self._internal("Annex", self.stock, is_monitor_stock=True,
                               monitor_currency_id=self.company.currency_id.id,
                               address_id=other_address.id)
        bin_ = self._internal("Bin", annex)
        Quant = self.env["stock.quant"]
        Quant._update_available_quantity(self.screws, shelf, 1)
        Quant._update_available_quantity(self.screws, bin_, 2)
        rows = {row.location_id: row for row in self._quant_rows(self.screws)}
        self.assertEqual(rows[shelf].stock_id, self.stock)
        self.assertEqual(rows[shelf].city, "Bougival")
        self.assertEqual(rows[bin_].stock_id, annex, "the nearest monitor stock wins")
        self.assertEqual(rows[bin_].city, "Rueil")

    def test_stock_outside_its_warehouse_root_and_outside_any_stock(self):
        # like Bg/Stock: a monitor stock that is not under the warehouse's view location
        root = self.env["stock.location"].create({"name": "Elsewhere", "usage": "view"})
        detached = self._internal("Detached stock", root, is_monitor_stock=True,
                                  monitor_currency_id=self.company.currency_id.id,
                                  address_id=self.address.id)
        loose = self._internal("Loose", root)
        Quant = self.env["stock.quant"]
        Quant._update_available_quantity(self.screws, detached, 1)
        Quant._update_available_quantity(self.screws, loose, 1)
        rows = {row.location_id: row for row in self._quant_rows(self.screws)}
        self.assertEqual(rows[detached].stock_id, detached)
        self.assertEqual(rows[detached].alert_outside_stock, 0)
        self.assertFalse(rows[loose].stock_id)
        self.assertEqual(rows[loose].alert_outside_stock, 1)

    def test_serial_with_two_positions_is_one_row(self):
        equipment = self._receive(self._order(self.drill, 1), ["MON-P1"])
        shelf = self._internal("Shelf 2", self.stock)
        self.env["stock.quant"]._update_available_quantity(
            self.drill, shelf, 1, lot_id=equipment.stock_lot_id)
        row = self._equipment_row(equipment)
        self.assertEqual(row.lot_quant_count, 2)
        self.assertEqual(row.alert_integrity, 1)
        self.assertEqual(row.asset_count, 1)
        self.env.cr.execute("SELECT id FROM lartdubati_stock_monitor GROUP BY id "
                            "HAVING count(*) > 1")
        self.assertFalse(self.env.cr.fetchall(), "ids are unique")

    def test_serial_without_position(self):
        equipment = self._receive(self._order(self.drill, 1), ["MON-P2"])
        self.env["stock.quant"]._update_available_quantity(
            self.drill, self.stock, -1, lot_id=equipment.stock_lot_id)
        row = self._equipment_row(equipment)
        self.assertFalse(row.location_id)
        self.assertFalse(row.stock_id)
        self.assertEqual(row.alert_no_position, 1)
        self.assertEqual(row.alert_outside_stock, 0)


@tagged("post_install", "-at_install")
class TestMonitorRent(MonitorCommon):
    """§3.6: current rent, monthly equivalent and rent paid."""

    def _rented(self, serial, **op_vals):
        op = self._borrow(serial, receipt_branch="rented", lines=[dict(
            product_id=self.drill.id, lot_name=serial, replacement_value=1500.0,
            rent_amount=80.0, replacement_value_date=self.today)], **op_vals)
        op.with_user(self.user_both).action_execute()
        return op

    def test_monthly_equivalent_per_periodicity(self):
        op = self._rented("MON-R1")
        equipment = op.line_ids.equipment_id
        line = op.contract_ids.contract_line_ids.filtered("equipment_id")
        row = self._equipment_row(equipment)
        self.assertAlmostEqual(row.rent_amount, 80.0)
        self.assertEqual(row.rent_rule_type, "monthly")
        self.assertAlmostEqual(row.rent_monthly, 80.0)
        line.write({"recurring_rule_type": "quarterly", "recurring_interval": 2})
        self.assertAlmostEqual(self._equipment_row(equipment).rent_monthly, 80.0 / 6)
        line.write({"recurring_rule_type": "yearly", "recurring_interval": 1})
        self.assertAlmostEqual(self._equipment_row(equipment).rent_monthly, 80.0 / 12)
        line.write({"recurring_rule_type": "weekly"})
        row = self._equipment_row(equipment)
        self.assertEqual(row.rent_monthly_known, 0)
        self.assertAlmostEqual(row.rent_amount, 80.0, msg="amount and period still shown")
        self.assertEqual(row.alert_rent_period_unsupported, 1)

    def test_rent_paid_posted_bills_minus_refunds(self):
        op = self._rented("MON-R2")
        equipment = op.line_ids.equipment_id
        contract = op.contract_ids
        contract.recurring_create_invoice()
        bill = contract._get_related_invoices()
        tax = self.env["account.tax"].create({
            "name": "Purchase 20 (monitor test)", "amount": 20.0,
            "type_tax_use": "purchase", "company_id": self.company.id})
        bill.invoice_line_ids.tax_ids = tax
        bill.invoice_date = self.today
        self.assertFalse(self._equipment_row(equipment).rent_paid, "draft bill ignored")
        self.assertEqual(self._equipment_row(equipment).rent_paid_source_amount, 0)
        bill.action_post()
        row = self._equipment_row(equipment)
        self.assertAlmostEqual(row.rent_paid, 80.0, msg="untaxed: the tax line is excluded")
        refund = bill._reverse_moves([{"invoice_date": self.today, "date": self.today}])
        refund.invoice_line_ids.price_unit = 30.0
        refund.action_post()
        self.assertAlmostEqual(self._equipment_row(equipment).rent_paid, 50.0)

    def test_rental_ended_alert(self):
        op = self._rented("MON-R3")
        equipment = op.line_ids.equipment_id
        line = op.contract_ids.contract_line_ids.filtered("equipment_id")
        self.assertEqual(self._equipment_row(equipment).alert_rental_ended, 0)
        self.env.cr.execute("UPDATE contract_line SET date_start = %s, date_end = %s "
                            "WHERE id = %s", [self.today - timedelta(days=60),
                                              self.today - timedelta(days=1), line.id])
        row = self._equipment_row(equipment)
        self.assertFalse(row.rent_start)
        self.assertEqual(row.alert_rental_ended, 1)


@tagged("post_install", "-at_install")
class TestMonitorConversions(MonitorCommon):
    """§3.5 and A4: the factors are those of res.currency._convert()."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Rate = cls.env["res.currency.rate"]
        Rate.search([("currency_id", "in", (cls.usd | cls.chf).ids)]).unlink()
        cls.past = cls.today - timedelta(days=200)
        Rate.create([
            # global rates and a company rate: the company row wins whatever its date
            {"currency_id": cls.usd.id, "name": cls.past, "rate": 1.10, "company_id": False},
            {"currency_id": cls.usd.id, "name": cls.today - timedelta(days=1), "rate": 1.50,
             "company_id": False},
            {"currency_id": cls.usd.id, "name": cls.today - timedelta(days=300), "rate": 1.20,
             "company_id": cls.company.id},
            {"currency_id": cls.chf.id, "name": cls.past, "rate": 0.95,
             "company_id": cls.company.id},
        ])
        cls.stock.monitor_currency_id = cls.usd

    def _convert(self, amount, source, date):
        return source._convert(amount, self.usd, self.company, date, round=False)

    def test_company_currency_to_stock_currency(self):
        self.env["stock.quant"]._update_available_quantity(self.screws, self.stock, 10)
        row = self._quant_rows(self.screws)
        eur = self.company.currency_id
        self.assertEqual(row.currency_id, self.usd)
        expected = self._convert(10 * self.screws.standard_price, eur, self.today)
        self.assertAlmostEqual(row.inventory_value, expected)
        self.assertAlmostEqual(row.inventory_value_rate, 1.20, msg="the company rate wins")
        self.assertEqual(row.inventory_value_source_currency_id, eur)
        self.assertEqual(row.inventory_value_rate_missing, 0)

    def test_foreign_to_foreign_and_later_rate_fallback(self):
        op = self._borrow("MON-C1")
        op.line_ids.write({"replacement_currency_id": self.chf.id})
        op.with_user(self.user_both).action_execute()
        equipment = op.line_ids.equipment_id
        row = self._equipment_row(equipment)
        date = equipment.replacement_value_date
        self.assertAlmostEqual(row.replacement_value, self._convert(900.0, self.chf, date))
        self.assertEqual(row.replacement_value_rate_fallback, 0)
        # dated before every CHF rate: Odoo takes the earliest later one; flagged
        old = self.past - timedelta(days=30)
        equipment.sudo().replacement_value_date = old
        row = self._equipment_row(equipment)
        self.assertAlmostEqual(row.replacement_value, self._convert(900.0, self.chf, old))
        self.assertEqual(row.replacement_value_rate_fallback, 1)
        self.assertEqual(row.replacement_value_rate_date, old)

    def test_missing_rate_gives_null_and_alert(self):
        self.env["res.currency.rate"].search([("currency_id", "=", self.chf.id)]).unlink()
        op = self._borrow("MON-C2")
        op.line_ids.write({"replacement_currency_id": self.chf.id})
        op.with_user(self.user_both).action_execute()
        row = self._equipment_row(op.line_ids.equipment_id)
        self.assertEqual(row.replacement_value_known, 0)
        self.assertEqual(row.inventory_value_known, 0)
        self.assertEqual(row.replacement_value_rate_missing, 1)
        self.assertEqual(row.alert_rate_missing, 1)
        self.assertAlmostEqual(row.replacement_value_source_amount, 900.0)

    def test_latest_mode_uses_todays_rate(self):
        op = self._borrow("MON-C3")
        op.with_user(self.user_both).action_execute()
        equipment = op.line_ids.equipment_id
        equipment.sudo().replacement_value_date = self.past
        eur = self.company.currency_id
        row = self._equipment_row(equipment)
        self.assertEqual(row.replacement_value_rate_date, self.past)
        self.company.stock_monitor_currency_mode = "latest"
        row = self._equipment_row(equipment)
        self.assertEqual(row.replacement_value_rate_date, self.today)
        self.assertAlmostEqual(row.replacement_value, self._convert(900.0, eur, self.today))


@tagged("post_install", "-at_install")
class TestMonitorLabels(MonitorCommon):
    """Point 6: translated text labels."""

    def test_product_name_translated(self):
        self.env["res.lang"]._activate_lang("fr_FR")
        self.screws.product_tmpl_id.with_context(lang="fr_FR").name = "Vis"
        self.env["stock.quant"]._update_available_quantity(self.screws, self.stock, 1)
        row = self._quant_rows(self.screws)
        self.assertEqual(row.product_name, "Screws")
        self.assertEqual(row.with_context(lang="fr_FR").product_name, "Vis")
        self.assertEqual(row.uom_name, "Units")


class MonitorAccessCommon(MonitorCommon):
    """An investor without Inventory rights, a store user and an accountant; a French
    stock with a sub-location without address and a German stock."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)

        def user(login, *groups):
            return Users.create({
                "name": login, "login": login, "company_id": cls.company.id,
                "company_ids": [Command.set(cls.company.ids)],
                "groups_id": [Command.set(
                    [cls.env.ref(g).id for g in ("base.group_user",) + groups])]})
        cls.investor = user("mon_investor", "lartdubati_investor_home.group_stock_investor")
        cls.store = user("mon_store", "stock.group_stock_user")
        cls.accountant = user("mon_accountant", "account.group_account_readonly")
        Profile = cls.env["lartdubati.stock.access"]
        cls.profile = Profile.create({"name": "Everything (test)"})
        cls.investor.stock_access_id = cls.profile
        # a German stock beside the French one
        cls.germany = cls.env.ref("base.de")
        cls.berlin = cls.env["stock.location"].create({
            "name": "Berlin", "usage": "internal",
            "location_id": cls.warehouse.view_location_id.id, "is_monitor_stock": True,
            "monitor_currency_id": cls.company.currency_id.id,
            "address_id": cls.env["res.partner"].create({
                "name": "Entrepôt Berlin (test)", "city": "Berlin",
                "country_id": cls.germany.id}).id})
        cls.shelf = cls.env["stock.location"].create(
            {"name": "Shelf (no address)", "usage": "internal", "location_id": cls.stock.id})
        Quant = cls.env["stock.quant"]
        Quant._update_available_quantity(cls.screws, cls.shelf, 4)
        Quant._update_available_quantity(cls.screws, cls.berlin, 6)

    def _visible(self, user, domain=()):
        self.env.flush_all()
        self.Monitor.invalidate_model()
        return self.Monitor.with_user(user).search(
            [("company_id", "=", self.company.id), *domain])



@tagged("post_install", "-at_install")
class TestMonitorAccess(MonitorAccessCommon):
    """§5 and points 6, 13, 1c-4: access profiles and field groups."""

    def test_profile_dimensions(self):
        op = self._borrow("MON-ACC1")
        op.with_user(self.user_both).action_execute()
        all_rows = self._visible(self.investor)
        self.assertEqual(set(all_rows.mapped("family")), {"asset", "consumable"})
        self.profile.country_ids = self.germany
        rows = self._visible(self.investor)
        self.assertEqual(set(rows.mapped("city")), {"Berlin"})
        self.profile.write({"country_ids": [Command.clear()],
                            "location_ids": [Command.set(self.stock.ids)]})
        rows = self._visible(self.investor)
        self.assertEqual(set(rows.mapped("city")), {"Bougival"},
                         "the sub-location without address follows its stock")
        self.profile.write({"location_ids": [Command.clear()], "family_ids": [Command.set(
            self.env.ref("lartdubati_investor_home.family_asset").ids)]})
        self.assertEqual(set(self._visible(self.investor).mapped("family")), {"asset"})
        self.profile.write({"family_ids": [Command.clear()], "ownership_type_ids": [
            Command.set(self.env.ref("lartdubati_investor_home.ownership_borrowed").ids)]})
        self.assertEqual(set(self._visible(self.investor).mapped("ownership_status")),
                         {"borrowed"})
        self.investor.stock_access_id = False
        self.assertFalse(self._visible(self.investor), "no profile: nothing")

    def test_investor_reads_labels_never_staff_fields(self):
        row = self._visible(self.investor, [("city", "=", "Berlin")])
        self.assertEqual(len(row), 1)
        values = row.read(["product_name", "stock_name", "country_name", "city",
                           "currency_id", "company_id", "inventory_value", "quantity"])[0]
        self.assertEqual(values["country_name"], "Germany")
        self.assertEqual(values["currency_id"][0], self.company.currency_id.id)
        fields = self.Monitor.with_user(self.investor).fields_get()
        for staff_field in ("stock_value", "accounting_value", "rent_paid", "stock_id",
                            "owner_partner_id", "alert_count", "alert_no_asset"):
            self.assertNotIn(staff_field, fields)
        self.assertIn("inventory_value", fields)
        self.assertIn("replacement_value_rate_missing", fields)
        Monitor = self.Monitor.with_user(self.investor)
        with self.assertRaises(AccessError):
            row.read(["stock_value"])
        with self.assertRaises(AccessError):
            Monitor.search([("accounting_value", ">", 0)])
        with self.assertRaises(AccessError):
            Monitor.search_count([("stock_id", "=", self.berlin.id)])
        with self.assertRaises(AccessError):
            Monitor.read_group([], ["stock_value:sum"], ["currency_id"])
        with self.assertRaises(AccessError):
            Monitor.search([], order="accounting_value desc")
        # export needs « Allow export » (base.group_allow_export), which investors do not
        # have by default; with it, a staff field still cannot be exported
        with self.assertRaises(UserError):
            row.export_data(["inventory_value"])
        self.investor.groups_id |= self.env.ref("base.group_allow_export")
        self.assertEqual(len(row.export_data(["inventory_value", "city"])["datas"]), 1)
        with self.assertRaises(AccessError):
            row.export_data(["stock_value"])

    def test_store_and_accountant_scopes(self):
        row = self._visible(self.store, [("city", "=", "Berlin")])
        self.assertEqual(row.read(["stock_value", "stock_id"])[0]["stock_id"][0],
                         self.berlin.id)
        with self.assertRaises(AccessError):
            row.read(["accounting_value"])
        with self.assertRaises(AccessError):
            self.Monitor.with_user(self.store).search([("rent_paid", ">", 0)])
        row = self._visible(self.accountant, [("city", "=", "Berlin")])
        row.read(["accounting_value", "stock_value", "rent_paid"])

    def test_nobody_writes(self):
        row = self._visible(self.store, [("city", "=", "Berlin")])
        with self.assertRaises(AccessError):
            row.write({"city": "Paris"})
        with self.assertRaises(AccessError):
            self.Monitor.with_user(self.accountant).create({"city": "Paris"})

    def test_analysis_views_for_each_profile(self):
        """The secondary interface loads for every profile; fields and filters reserved
        to staff or accountants are removed from an investor's views."""
        modes = [(False, mode) for mode in ("list", "pivot", "graph", "form", "search")]
        staff_only = ("stock_value", "accounting_value", "rent_paid", "alert_count",
                      "owner_name", "with_alerts", "outside_stock", "provisional")
        for user in (self.investor, self.store, self.accountant):
            with self.subTest(user=user.login):
                views = self.Monitor.with_user(user).get_views(modes)["views"]
                arch = "".join(view["arch"] for view in views.values())
                for name in staff_only:
                    if user == self.investor:
                        self.assertNotIn(f'"{name}"', arch)
                if user == self.accountant:
                    self.assertIn('"accounting_value"', arch)
                if user == self.store:
                    self.assertIn('"stock_value"', arch)
                    self.assertNotIn('"accounting_value"', arch)


@tagged("post_install", "-at_install")
class TestMonitorDashboardData(MonitorAccessCommon):
    """§4.3: get_dashboard_data, one call under the user's rights."""

    def _data(self, user, filters=None):
        self.env.flush_all()
        self.Monitor.invalidate_model()
        return self.Monitor.with_user(user).get_dashboard_data(filters or {})

    def test_investor_gets_no_staff_key(self):
        data = self._data(self.investor)
        self.assertFalse(data["staff"])
        self.assertEqual(set(data["totals"]), {"inventory_value", "replacement_value"})
        self.assertFalse(data["controls"])
        self.assertLessEqual(set(data["alerts"]), {"inventory_value_rate_missing",
                                                   "replacement_value_rate_missing"})
        self.assertTrue(all(card["alerts"] == 0 for card in data["stocks"]))
        store = self._data(self.store)
        self.assertTrue(store["staff"])
        self.assertIn("stock_value", store["totals"])
        self.assertNotIn("accounting_value", store["totals"])
        self.assertIn("to_complete", store["controls"])
        accountant = self._data(self.accountant)
        self.assertIn("accounting_value", accountant["totals"])
        self.assertIn("rent_paid", accountant["totals"])

    def test_filters_are_checked(self):
        Monitor = self.Monitor.with_user(self.investor)
        for filters in ({"domain": [("id", ">", 0)]}, {"countries": "France"},
                        {"stocks": [1]}, {"alert": "alert_no_asset"},
                        {"alert": "stock_value"}, ["countries"]):
            with self.subTest(filters=filters), self.assertRaises(UserError):
                Monitor.get_dashboard_data(filters)
        self.assertTrue(self.Monitor.with_user(self.store).get_dashboard_data(
            {"alert": "alert_no_asset"})["domain"])

    def test_totals_per_currency_and_selection(self):
        self.berlin.monitor_currency_id = self.usd
        self.env["res.currency.rate"].create({
            "currency_id": self.usd.id, "name": self.today - timedelta(days=1), "rate": 2.0,
            "company_id": self.company.id})
        data = self._data(self.investor)
        lines = {line["currency_id"]: line["amount"]
                 for line in data["totals"]["inventory_value"]["lines"]}
        eur = self.company.currency_id
        price = self.screws.standard_price
        self.assertAlmostEqual(lines[eur.id], 4 * price)
        self.assertAlmostEqual(lines[self.usd.id], 6 * price * 2.0, msg="never added to EUR")
        cards = {card["city"]: card for card in data["stocks"]}
        self.assertEqual(cards["Berlin"]["currency_id"], self.usd.id)
        self.assertEqual(cards["Berlin"]["name"], self.berlin.complete_name)
        self.assertEqual({choice["country"] for choice in data["choices"]},
                         {"France", "Germany"})
        berlin = self._data(self.investor, {"cities": ["Berlin"]})
        self.assertEqual(berlin["count"], 1)
        self.assertEqual([line["currency_id"] for line in
                          berlin["totals"]["inventory_value"]["lines"]], [self.usd.id])
        self.assertEqual(len(berlin["stocks"]), 1)
        self.assertEqual(len(berlin["choices"]), 2, "the selectors keep every stock")
        rows = self.Monitor.with_user(self.investor).search(berlin["domain"])
        self.assertEqual(len(rows), 1, "the returned domain gives the list page")

    def test_unconverted_amounts_stay_out_of_totals(self):
        self.env["res.currency.rate"].search([("currency_id", "=", self.chf.id)]).unlink()
        self.berlin.monitor_currency_id = self.chf
        data = self._data(self.investor)
        inventory = data["totals"]["inventory_value"]
        self.assertEqual([line["currency_id"] for line in inventory["lines"]],
                         [self.company.currency_id.id])
        self.assertEqual(inventory["missing"], [{
            "currency_id": self.company.currency_id.id,
            "amount": 6 * self.screws.standard_price}])
        self.assertEqual(data["alerts"]["inventory_value_rate_missing"], 1)

    def test_profile_restricts_every_aggregate(self):
        self.profile.country_ids = self.germany
        data = self._data(self.investor)
        self.assertEqual(data["count"], 1)
        self.assertEqual([card["city"] for card in data["stocks"]], ["Berlin"])
        self.assertEqual([choice["city"] for choice in data["choices"]], ["Berlin"])

    def test_query_count(self):
        self._data(self.accountant)  # warm the caches
        self.env.flush_all()
        self.Monitor.invalidate_model()
        with self.assertQueryCount(__system__=8):
            self.Monitor.with_user(self.accountant).get_dashboard_data({})

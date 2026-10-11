"""ROADMAP section 0 (docs/roadmap0/PLAN.md, revision 5): label, governed product
creation, structural lock, variants, creation requests, structural corrections, no
silent equipment category."""
import base64
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import EquipmentCommon

PNG = base64.b64encode(
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00"
    b"\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8"
    b"\xbd\x00\x00\x00\x00IEND\xaeB`\x82")
MODULE = "maintenance_shareholder_equipment"


@tagged("post_install", "-at_install")
class CatalogueCommon(EquipmentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Category = env["product.category"]
        cls.root_fixed = env.ref("%s.categ_root_fixed_assets" % MODULE)
        cls.root_services = env.ref("%s.categ_root_services_purchased" % MODULE)
        cls.root_materials = env.ref("%s.categ_root_materials" % MODULE)
        # categories configured and made available (D8: outside the requests)
        cls.categ_it = Category.create({
            "name": "IT (test)", "parent_id": cls.root_fixed.id,
            "property_cost_method": "average", "property_valuation": "manual_periodic",
            "property_account_expense_categ_id": cls.acc_asset.id,
            "is_fixed_asset_stock": True, "request_ready": True,
        })
        cls.categ_service = Category.create({
            "name": "Maintenance services (test)", "parent_id": cls.root_services.id,
            "property_account_expense_categ_id": cls.acc_expense.id, "request_ready": True,
        })
        cls.ecat_computers = env.ref("%s.ecat_it_computers" % MODULE)
        cls.ecat_to_classify = env.ref("%s.ecat_to_classify" % MODULE)
        Users = env["res.users"].with_context(no_reset_password=True)
        manager_group = env.ref("%s.group_product_catalogue_manager" % MODULE)

        def user(login, groups):
            return Users.create({
                "name": login, "login": login, "email": "%s@example.com" % login,
                "company_id": cls.company.id, "company_ids": [Command.set(cls.company.ids)],
                "groups_id": [Command.set([env.ref("base.group_user").id] + [g.id for g in groups])],
            })

        cls.manager = user("cat_manager", [manager_group, env.ref("stock.group_stock_user")])
        cls.manager2 = user("cat_manager2", [manager_group])
        cls.buyer = user("cat_buyer", [env.ref("purchase.group_purchase_user")])
        cls.taxes_purchase = env["account.tax"].search([
            ("type_tax_use", "=", "purchase"), ("company_id", "=", cls.company.id)], limit=1)

    def _request(self, user=None, **vals):
        values = {
            "family": "durable_equipment", "product_name": "Mac Mini (test)",
            "categ_id": self.categ_it.id, "equipment_category_id": self.ecat_computers.id,
            "company_id": self.company.id, "supplier_id": self.vendor.id,
            "supplier_code": "MM-1220", "supplier_price": 1100.0, "min_qty": 1,
            "delay": 5, "supplier_taxes_ids": [Command.set(self.taxes_purchase.ids)],
            "default_code": "MAC-001", "barcode": "4006381333931",
        }
        values.update(vals)
        return self.env["product.creation.request"].with_user(user or self.user_operator).create(values)

    def _approved(self, **vals):
        request = self._request(**vals)
        request.action_submit()
        request.with_user(self.manager).action_approve()
        self.assertEqual(request.state, "approved")
        return request


@tagged("post_install", "-at_install")
class TestCatalogueGuards(CatalogueCommon):

    def test_label_three_languages(self):
        labels = {}
        for lang in ("en_US", "fr_FR", "fa_IR"):
            self.env["res.lang"]._activate_lang(lang)
            labels[lang] = self.env["product.template"].with_context(lang=lang).fields_get(
                ["maintenance_ok"], ["string"])["maintenance_ok"]["string"]
        self.assertEqual(labels["en_US"], "Can be maintained")
        self.assertEqual(labels["fr_FR"], "Peut être maintenu")
        self.assertEqual(labels["fa_IR"], "قابل تعمیر و نگهداری است")

    def test_direct_creation_refused_to_everyone(self):
        for user in (self.manager, self.buyer, self.user_operator):
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError):
                    self.env["product.template"].with_user(user).create({"name": "Direct"})
                with self.assertRaises(AccessError):
                    self.env["product.product"].with_user(user).create({"name": "Direct"})
                with self.assertRaises(AccessError):
                    self.env["product.product"].with_user(user).name_create("Quick created")
                with self.assertRaises(AccessError):
                    self.drill.product_tmpl_id.with_user(user).copy()
        # a context key never opens it
        with self.assertRaises(AccessError):
            self.env["product.template"].with_user(self.manager).with_context(
                product_request_internal=True, skip_validation_check=True).create({"name": "X"})
        # superuser mode (migration, request execution) creates
        self.assertTrue(self.env["product.template"].sudo().create({"name": "Migration"}))

    def test_structural_fields_locked_ordinary_fields_free(self):
        tmpl = self.drill.product_tmpl_id
        tmpl.invalidate_recordset()
        for vals in ({"categ_id": self.categ_tools.id}, {"tracking": "lot"},
                     {"maintenance_ok": False}, {"uom_po_id": self.env.ref("uom.product_uom_dozen").id},
                     {"equipment_category_id": self.ecat_computers.id},
                     {"property_account_expense_id": self.acc_expense.id},
                     {"default_code": "OTHER"}, {"barcode": "123"}):
            with self.subTest(vals=vals), self.assertRaises(UserError):
                tmpl.with_user(self.manager).write(vals)
        with self.assertRaises(UserError):
            self.drill.with_user(self.manager).write({"categ_id": self.categ_tools.id})
        # same values and ordinary fields pass
        tmpl.with_user(self.manager).write({"name": "Drill renamed", "list_price": 12.0,
                                            "categ_id": tmpl.categ_id.id})
        self.drill.with_user(self.manager).write({"standard_price": 140.0})
        self.assertEqual(tmpl.name, "Drill renamed")

    def test_variants(self):
        env = self.env
        attribute = env["product.attribute"].create({
            "name": "Size (test)", "create_variant": "dynamic",
            "value_ids": [Command.create({"name": "S"}), Command.create({"name": "L"})]})
        tmpl = self.drill.product_tmpl_id
        with self.assertRaises(UserError):
            tmpl.with_user(self.manager).write({"attribute_line_ids": [Command.create({
                "attribute_id": attribute.id, "value_ids": [Command.set(attribute.value_ids.ids)]})]})
        # a template with a dynamic attribute set up in superuser mode
        dynamic = env["product.template"].create({
            "name": "Dynamic (test)", "attribute_line_ids": [Command.create({
                "attribute_id": attribute.id, "value_ids": [Command.set(attribute.value_ids.ids)]})]})
        combination = dynamic.attribute_line_ids.product_template_value_ids[:1]
        with self.assertRaises(AccessError):
            dynamic.with_user(self.buyer)._create_product_variant(combination)
        variant = dynamic._create_product_variant(combination)
        self.assertTrue(variant)
        # an existing variant is returned unchanged
        self.assertEqual(dynamic.with_user(self.buyer)._create_product_variant(combination), variant)

    def test_no_silent_equipment_category(self):
        Category = self.env["maintenance.equipment.category"]
        count = Category.search_count([])
        product = self.env["product.product"].create({
            "name": "No category", "type": "consu", "maintenance_ok": True,
            "categ_id": self.categ_tools.id, "purchase_method": "purchase",
            "supplier_taxes_id": [Command.clear()]})
        po = self._order(product, 1)
        bill = self.env["account.move"].create({
            "move_type": "in_invoice", "partner_id": self.vendor.id,
            "invoice_date": "2026-10-11",
            "invoice_line_ids": [Command.create({"product_id": product.id, "quantity": 1,
                                                 "price_unit": 10,
                                                 "purchase_line_id": po.order_line.id})]})
        with self.assertRaisesRegex(UserError, "default equipment category"):
            bill.action_post()
        self.assertEqual(Category.search_count([]), count)

    def test_equipment_category_archiving(self):
        category = self.env["maintenance.equipment.category"].create({"name": "Old (test)"})
        category.active = False
        self.assertNotIn(category, self.env["maintenance.equipment.category"].search([]))
        with self.assertRaises(ValidationError):
            category._check_assignable()
        with self.assertRaises(ValidationError):
            self.ecat_to_classify._check_assignable()


@tagged("post_install", "-at_install")
class TestCreationRequest(CatalogueCommon):

    def test_full_flow_creates_the_product(self):
        document = self.env["ir.attachment"].with_user(self.user_operator).create({
            "name": "quote.pdf", "datas": base64.b64encode(b"quote")})
        request = self._request(image_1920=PNG, attachment_ids=[Command.set(document.ids)])
        self.assertEqual(request.treatment_text, "Posting the bill creates a fixed asset "
                         "(account 215400).")
        request.action_submit()
        self.assertEqual(request.state, "to_approve")
        with self.assertRaises(AccessError):
            request.with_user(self.buyer).action_approve()
        request.with_user(self.manager).action_approve()
        request.with_user(self.manager).action_execute()
        self.assertEqual(request.state, "done")
        tmpl = request.product_tmpl_id
        self.assertTrue(tmpl.is_storable)
        self.assertEqual(tmpl.tracking, "serial")
        self.assertTrue(tmpl.maintenance_ok)
        self.assertEqual(tmpl.equipment_category_id, self.ecat_computers)
        self.assertEqual(tmpl.categ_id, self.categ_it)
        self.assertEqual(tmpl.default_code, "MAC-001")
        self.assertEqual(tmpl.seller_ids.price, 1100.0)
        self.assertEqual(tmpl.seller_ids.currency_id, self.company.currency_id)
        self.assertEqual(tmpl.supplier_taxes_id, self.taxes_purchase)
        self.assertTrue(tmpl.image_1920)
        copied = self.env["ir.attachment"].search([("res_model", "=", "product.template"),
                                                   ("res_id", "=", tmpl.id)])
        self.assertEqual(copied.mapped("name"), ["quote.pdf"])
        # a second execution changes nothing
        with self.assertRaisesRegex(UserError, "already executed"):
            request.with_user(self.manager).action_execute()

    def test_requester_cannot_approve(self):
        request = self._request(user=self.manager)
        request.with_user(self.manager).action_submit()
        with self.assertRaisesRegex(UserError, "requester"):
            request.with_user(self.manager).action_approve()
        request.with_user(self.manager2).action_approve()
        # the approver may execute (catalogue manager)
        request.with_user(self.manager2).action_execute()
        self.assertEqual(request.state, "done")

    def test_waiting_family_refused(self):
        categ = self.env["product.category"].create({
            "name": "Tiles (test)", "parent_id": self.root_materials.id})
        request = self._request(family="material", categ_id=categ.id,
                                equipment_category_id=False, default_code="TIL-1",
                                barcode=False, supplier_code="T-1")
        with self.assertRaisesRegex(ValidationError, "waits for the accountant"):
            request.action_submit()
        # a category of another branch is refused too
        request = self._request(family="service", purchase_ok=True, default_code="SV-1",
                                barcode=False, supplier_code="S-1",
                                equipment_category_id=False)
        with self.assertRaisesRegex(ValidationError, "branch"):
            request.action_submit()

    def test_service_request(self):
        request = self._approved(family="service", categ_id=self.categ_service.id,
                                 equipment_category_id=False, product_name="Repair (test)",
                                 default_code="REP-1", barcode=False, supplier_code="R-1")
        request.with_user(self.manager).action_execute()
        tmpl = request.product_tmpl_id
        self.assertEqual(tmpl.type, "service")
        self.assertFalse(tmpl.maintenance_ok)

    def test_archived_or_transitional_equipment_category_refused(self):
        for category in (self.ecat_to_classify,):
            request = self._request(equipment_category_id=category.id)
            with self.subTest(category=category.name), \
                    self.assertRaisesRegex(ValidationError, "cannot be used"):
                request.action_submit()

    def test_change_after_approval_back_to_approval(self):
        request = self._approved()
        request.with_user(self.user_operator).write({"supplier_price": 1200.0})
        self.assertEqual(request.state, "to_approve")
        self.assertFalse(request.approver_id)

    def test_treatment_recomputed_at_execution(self):
        request = self._approved()
        # the category's account changes after the approval (outside the request)
        self.categ_it.property_cost_method = "standard"
        request.with_user(self.manager).action_execute()
        self.assertEqual(request.state, "to_approve")
        self.assertFalse(request.product_tmpl_id)
        self.assertFalse(self.env["product.template"].search([("default_code", "=", "MAC-001")]))

    def test_closed_request_frozen_and_duplicated(self):
        request = self._request()
        request.action_submit()
        request.with_user(self.manager).write({"decision_note": "Not needed"})
        request.with_user(self.manager).action_refuse()
        with self.assertRaisesRegex(UserError, "closed"):
            request.with_user(self.manager).write({"product_name": "Other"})
        with self.assertRaises(AccessError):
            request.with_user(self.manager).with_context(product_request_internal=True).write(
                {"state": "draft"})
        request.message_post(body="still commented")
        copy = request.with_user(self.user_operator).copy()
        self.assertEqual(copy.state, "draft")

    def test_duplicates(self):
        existing = self.env["product.template"].create({
            "name": "Old Mac", "default_code": "mac-001 ", "active": False,
            "barcode": "4006381333931"})
        request = self._request(default_code="  Mac-001", barcode="X1")
        request.action_submit()
        with self.assertRaisesRegex(UserError, "internal reference"):
            request.with_user(self.manager).action_approve()
        # barcode: exact comparison (outer spaces only)
        request = self._request(default_code="NEW-1", barcode=" 4006381333931 ")
        request.action_submit()
        with self.assertRaisesRegex(UserError, "barcode"):
            request.with_user(self.manager).action_approve()
        existing.barcode = "abc123"
        request = self._request(default_code="NEW-2", barcode="ABC123", supplier_code="Z-9")
        request.action_submit()
        request.with_user(self.manager).action_approve()  # another barcode: case kept
        # supplier reference: per supplier
        self.env["product.supplierinfo"].create({
            "partner_id": self.vendor.id, "product_tmpl_id": existing.id,
            "product_code": "mm 1220"})
        request = self._request(default_code="NEW-3", barcode=False, supplier_code="MM 1220")
        request.action_submit()
        with self.assertRaisesRegex(UserError, "supplier reference"):
            request.with_user(self.manager).action_approve()
        request = self._request(default_code="NEW-4", barcode=False, supplier_code="MM 1220",
                                supplier_id=self.lender.id)
        request.action_submit()
        request.with_user(self.manager).action_approve()

    def test_similar_name_confirmed_by_approver(self):
        self.env["product.template"].create({"name": "Mac Mini (test)"})
        request = self._request(default_code="SIM-1", barcode=False, supplier_code="S-SIM")
        request.action_submit()
        with self.assertRaisesRegex(UserError, "Similar"):
            request.with_user(self.manager).action_approve()
        request.with_user(self.manager).write({"similar_confirmed": True})
        request.with_user(self.manager).action_approve()
        self.assertEqual(request.state, "approved")

    def test_concurrent_key_loser_stays_approved(self):
        """The unique index decides when the duplicate search cannot see the other
        execution (REPEATABLE READ): the loser gets a business message, stays approved,
        without product and without the `done` state."""
        first = self._approved(default_code="RACE-1", barcode=False, supplier_code="RC-1")
        second = self._approved(default_code=" race-1", barcode=False, supplier_code="RC-2",
                                product_name="Other name")
        first.with_user(self.manager).action_execute()
        Request = type(self.env["product.creation.request"])
        with patch.object(Request, "_find_duplicates", lambda self: ([], [])):
            with self.assertRaisesRegex(UserError, "same internal reference"):
                second.with_user(self.manager).action_execute()
        second.invalidate_recordset()
        self.assertEqual(second.state, "approved")
        self.assertFalse(second.product_tmpl_id)
        self.assertEqual(self.env["product.template"].search_count(
            [("default_code", "in", ("RACE-1", " race-1"))]), 1)

    def test_index_blocks_a_concurrent_connection(self):
        """Two real database connections (not the test's cursor): the first reserves a
        key without committing, the second cannot reserve the same key; both rolled
        back, nothing written."""
        import psycopg2

        from odoo import SUPERUSER_ID, api
        from odoo.sql_db import db_connect

        db = db_connect(self.env.cr.dbname)
        cr1, cr2 = db.cursor(), db.cursor()
        try:
            vals = {"family": "service", "product_name": "Concurrent (test)",
                    "categ_id": self.env.ref("product.product_category_all").id,
                    "company_id": self.env.ref("base.main_company").id,
                    "default_code": "CONCUR-1", "state": "done"}
            context = {"tracking_disable": True, "mail_create_nolog": True}
            first = api.Environment(cr1, SUPERUSER_ID, context)["product.creation.request"]
            first.create(dict(vals)).flush_recordset()
            cr2.execute("SET LOCAL lock_timeout = '2s'")
            second = api.Environment(cr2, SUPERUSER_ID, context)["product.creation.request"]
            blocked = False
            try:
                second.create(dict(vals, default_code=" concur-1")).flush_recordset()
            except (psycopg2.errors.LockNotAvailable, psycopg2.errors.UniqueViolation):
                blocked = True
            self.assertTrue(blocked, "the second connection reserved the same key")
        finally:
            for cr in (cr1, cr2):
                cr.rollback()
                cr.close()

    def test_error_after_reservation_rolls_back(self):
        """Reservation of the keys and creation of the product are one transaction."""
        request = self._approved(default_code="ROLL-1", barcode=False, supplier_code="RL-1")
        Request = type(self.env["product.creation.request"])

        def failing(self):
            raise UserError("creation failed")
        with patch.object(Request, "_create_product", failing):
            with self.assertRaisesRegex(UserError, "creation failed"), self.env.cr.savepoint():
                request.with_user(self.manager).action_execute()
        request.invalidate_recordset()
        self.assertEqual(request.state, "approved")
        self.assertFalse(request.product_tmpl_id)

    def test_approved_documents_frozen(self):
        approved_doc = self.env["ir.attachment"].with_user(self.user_operator).create({
            "name": "quote.pdf", "datas": base64.b64encode(b"quote")})
        request = self._approved(default_code="DOC-1", barcode=False, supplier_code="D-1",
                                 attachment_ids=[Command.set(approved_doc.ids)])
        frozen = request.sudo().approved_documents
        extra = self.env["ir.attachment"].with_user(self.user_operator).create({
            "name": "datasheet.pdf", "datas": base64.b64encode(b"sheet")})
        request.with_user(self.user_operator).write({"attachment_ids": [Command.link(extra.id)]})
        self.assertEqual(request.state, "approved")
        self.assertEqual(request.sudo().approved_documents, frozen)
        with self.assertRaisesRegex(UserError, "approved document"):
            request.with_user(self.user_operator).write(
                {"attachment_ids": [Command.unlink(approved_doc.id)]})
        with self.assertRaisesRegex(UserError, "Approved documents"):
            approved_doc.with_user(self.user_operator).unlink()
        with self.assertRaisesRegex(UserError, "Approved documents"):
            approved_doc.with_user(self.user_operator).write({"datas": base64.b64encode(b"x")})
        request.with_user(self.manager).action_execute()
        self.assertEqual(request.state, "done")

    def test_record_rules(self):
        mine = self._request(default_code="RR-1", barcode=False, supplier_code="RR-1")
        other = self._request(user=self.buyer, default_code="RR-2", barcode=False,
                              supplier_code="RR-2")
        Request = self.env["product.creation.request"]
        self.assertIn(mine, Request.with_user(self.user_operator).search([]))
        self.assertNotIn(other, Request.with_user(self.user_operator).search([]))
        self.assertIn(other, Request.with_user(self.manager).search([]))


@tagged("post_install", "-at_install")
class TestStructuralCorrection(CatalogueCommon):
    """Audit of dad9933: the correction only changes the default equipment category."""

    def _product_it(self):
        request = self._approved(default_code="SC-1", barcode=False, supplier_code="SC-1")
        request.with_user(self.manager).action_execute()
        return request.product_tmpl_id

    def _correction(self, tmpl, category, user=None):
        return self.env["product.structural.correction"].with_user(user or self.manager).create({
            "product_tmpl_id": tmpl.id, "reason": "Wrong category at creation",
            "equipment_category_id": category.id})

    def test_correction_applied_and_traced(self):
        tmpl = self._product_it()
        target = self.env.ref("%s.ecat_it_phones" % MODULE)
        correction = self._correction(tmpl, target)
        correction.with_user(self.manager).action_apply()
        self.assertEqual(tmpl.equipment_category_id, target)
        self.assertEqual(correction.state, "done")
        self.assertIn("Computers", correction.before_values)
        self.assertIn("Wrong category at creation", tmpl.message_ids[:1].body)
        with self.assertRaises(UserError):
            correction.with_user(self.manager).write({"reason": "changed"})
        with self.assertRaises(UserError):
            correction.with_user(self.manager).unlink()
        with self.assertRaises(UserError):
            correction.with_user(self.manager).action_apply()

    def test_correction_protected_fields(self):
        tmpl = self._product_it()
        target = self.env.ref("%s.ecat_it_phones" % MODULE)
        with self.assertRaises(AccessError):
            self.env["product.structural.correction"].with_user(self.manager).create({
                "product_tmpl_id": tmpl.id, "reason": "x", "equipment_category_id": target.id,
                "state": "done", "before_values": "fake"})
        correction = self._correction(tmpl, target)
        for vals in ({"state": "done"}, {"before_values": "fake"}, {"after_values": "fake"},
                     {"user_id": self.buyer.id}, {"date": "2026-01-01 00:00:00"},
                     {"name": "PSC/FAKE"}):
            with self.subTest(vals=vals), self.assertRaises(AccessError):
                correction.with_user(self.manager).write(vals)
        with self.assertRaises(UserError):
            correction.with_user(self.manager).write({"product_tmpl_id": self.drill.product_tmpl_id.id})
        # the product of a correction cannot be deleted (trace kept)
        correction.with_user(self.manager).action_apply()
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                tmpl.sudo().unlink()

    def test_correction_refuses_unusable_category_non_maintainable_non_manager(self):
        tmpl = self._product_it()
        with self.assertRaises(AccessError):
            self._correction(tmpl, self.env.ref("%s.ecat_it_phones" % MODULE), user=self.buyer)
        correction = self._correction(tmpl, self.ecat_to_classify)
        with self.assertRaises(ValidationError):
            correction.with_user(self.manager).action_apply()
        tmpl.invalidate_recordset()
        self.assertEqual(tmpl.equipment_category_id, self.ecat_computers)
        service = self.env["product.template"].create({"name": "Service (test)", "type": "service"})
        correction = self._correction(service, self.ecat_computers)
        with self.assertRaises(ValidationError):
            correction.with_user(self.manager).action_apply()

    def test_correction_of_a_product_in_stock(self):
        """Only the equipment category changes: no stock or valuation effect."""
        self._receive(self._order(self.drill, 1), ["SC-STOCK-1"])
        Layer = self.env["stock.valuation.layer"]
        layers = Layer.search_count([("product_id", "=", self.drill.id)])
        target = self.env.ref("%s.ecat_tools_cordless" % MODULE)
        self._correction(self.drill.product_tmpl_id, target).with_user(self.manager).action_apply()
        self.assertEqual(self.drill.equipment_category_id, target)
        self.assertEqual(Layer.search_count([("product_id", "=", self.drill.id)]), layers)
        self.assertNotIn("categ_id", self.env["product.structural.correction"]._fields)
        self.assertNotIn("tracking", self.env["product.structural.correction"]._fields)


@tagged("post_install", "-at_install")
class TestRequestBypasses(CatalogueCommon):
    """Audit of dad9933: direct API calls (as a client would send them)."""

    PROTECTED = {
        "state": "approved", "approval_date": "2026-01-01 00:00:00",
        "approval_snapshot": "{}", "approved_documents": "{}",
        "execution_date": "2026-01-01 00:00:00", "key_default_code": "X",
        "key_barcode": "X", "key_supplier": "X", "name": "PCR/FAKE",
    }

    def test_requester_cannot_be_usurped(self):
        with self.assertRaises(AccessError):
            self._request(user=self.manager, requester_id=self.buyer.id)
        request = self._request(user=self.manager)
        self.assertEqual(request.requester_id, self.manager)
        with self.assertRaises(AccessError):
            request.with_user(self.manager).write({"requester_id": self.buyer.id})
        request.with_user(self.manager).action_submit()
        with self.assertRaisesRegex(UserError, "requester"):
            request.with_user(self.manager).action_approve()

    def test_protected_fields_refused_to_clients(self):
        request = self._request()
        record_fields = {
            "approver_id": self.manager.id, "requester_id": self.manager.id,
            "executor_id": self.manager.id,
            "product_tmpl_id": self.drill.product_tmpl_id.id,
            "approved_attachment_ids": [Command.set([])],
        }
        for user in (self.user_operator, self.manager):
            for name, value in list(self.PROTECTED.items()) + list(record_fields.items()):
                with self.subTest(user=user.login, field=name):
                    with self.assertRaises(AccessError):
                        request.with_user(user).write({name: value})
                    with self.assertRaises(AccessError):
                        self._request(user=user, **{name: value})
        # nothing changed, the workflow still has to be followed
        self.assertEqual(request.state, "draft")
        self.assertFalse(request.approver_id)

    def test_similar_confirmed_only_by_manager_while_to_approve(self):
        request = self._request()
        with self.assertRaises(AccessError):
            request.with_user(self.user_operator).write({"similar_confirmed": True})
        with self.assertRaises(AccessError):
            request.with_user(self.manager).write({"similar_confirmed": True})  # draft
        request.action_submit()
        with self.assertRaises(AccessError):
            request.with_user(self.user_operator).write({"similar_confirmed": True})
        request.with_user(self.manager).write({"similar_confirmed": True})

    def test_keys_locked_after_creation(self):
        request = self._approved(default_code="KEY-1", barcode="KEY-BC-1", supplier_code="KS-1")
        request.with_user(self.manager).action_execute()
        tmpl = request.product_tmpl_id
        for vals in ({"default_code": "KEY-2"}, {"barcode": "KEY-BC-2"}):
            with self.subTest(vals=vals):
                with self.assertRaises(UserError):
                    tmpl.with_user(self.manager).write(vals)
                with self.assertRaises(UserError):
                    tmpl.product_variant_id.with_user(self.manager).write(vals)
        info = tmpl.seller_ids
        for vals in ({"product_code": "KS-2"}, {"partner_id": self.lender.id},
                     {"product_tmpl_id": self.drill.product_tmpl_id.id},
                     {"company_id": False}):
            with self.subTest(vals=vals), self.assertRaises(UserError):
                info.with_user(self.manager).write(vals)
        info.with_user(self.manager).write({"price": 1050.0, "min_qty": 2, "delay": 7})
        self.assertEqual(info.price, 1050.0)
        with self.assertRaises(UserError):
            info.with_user(self.manager).unlink()

    def test_foreign_attachment_refused(self):
        foreign = self.env["ir.attachment"].create({
            "name": "secret.pdf", "datas": base64.b64encode(b"secret"),
            "res_model": "res.partner", "res_id": self.vendor.id})
        with self.assertRaises(AccessError):
            self._request(attachment_ids=[Command.set(foreign.ids)])
        other_upload = self.env["ir.attachment"].with_user(self.buyer).create({
            "name": "other.pdf", "datas": base64.b64encode(b"other")})
        request = self._request()
        with self.assertRaises(AccessError):
            request.with_user(self.user_operator).write(
                {"attachment_ids": [Command.link(other_upload.id)]})
        own = self.env["ir.attachment"].with_user(self.user_operator).create({
            "name": "own.pdf", "datas": base64.b64encode(b"own")})
        request.with_user(self.user_operator).write({"attachment_ids": [Command.link(own.id)]})
        self.assertEqual((own.res_model, own.res_id), (request._name, request.id))
        self.assertEqual(foreign.res_model, "res.partner")

    def test_duplicates_per_company(self):
        other_company = self.env["res.company"].create({"name": "Other company (test)"})
        other = self.env["product.template"].create({
            "name": "Other company product", "company_id": other_company.id,
            "default_code": "MC-1", "barcode": "MC-BC-1"})
        self.env["product.supplierinfo"].create({
            "partner_id": self.vendor.id, "product_tmpl_id": other.id, "product_code": "MC-S1",
            "company_id": other_company.id})
        request = self._request(default_code="MC-1", barcode="MC-BC-1", supplier_code="MC-S1")
        request.action_submit()
        blocking, _similar = request._find_duplicates()
        self.assertFalse(blocking)
        # a shared product (no company) is a duplicate for every company
        other.company_id = False
        other.seller_ids.company_id = False
        blocking, _similar = request._find_duplicates()
        self.assertEqual(len(blocking), 3)

    def test_request_ready_reserved_to_accounting_administrators(self):
        categ = self.env["product.category"].create({
            "name": "Tiles (test)", "parent_id": self.root_materials.id})
        with self.assertRaises(AccessError):
            categ.with_user(self.manager).write({"request_ready": True})
        with self.assertRaises(AccessError):
            self.env["product.category"].with_user(self.manager).create({
                "name": "Open (test)", "request_ready": True})
        accountant = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "acc_admin", "login": "acc_admin", "company_id": self.company.id,
            "company_ids": [Command.set(self.company.ids)],
            "groups_id": [Command.set([self.env.ref("account.group_account_manager").id,
                                       self.env.ref("product.group_product_manager").id])]})
        categ.with_user(accountant).write({"request_ready": True})
        self.assertEqual(categ.request_ready_user_id, accountant)
        self.assertTrue(categ.request_ready_date)
        with self.assertRaises(AccessError):
            categ.with_user(accountant).write({"request_ready_user_id": self.manager.id})

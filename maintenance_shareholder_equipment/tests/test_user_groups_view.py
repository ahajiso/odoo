from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestUserGroupsView(TransactionCase):
    """The equipment groups are shown in the user form without developer mode, and
    the Maintenance section keeps its drop-down list (audit of the deployment of
    08/10/2026)."""

    def _visible_selection_fields(self):
        self.env["res.groups"]._update_user_groups_view()
        arch = etree.fromstring(self.env.ref("base.user_groups_view").arch)
        visible, debug_only = set(), set()
        for field in arch.iter("field"):
            name = field.get("name", "")
            in_debug = any(node.get("groups") == "base.group_no_one"
                           for node in field.iterancestors()) or \
                field.get("groups") == "base.group_no_one" or field.get("invisible") == "True"
            (debug_only if in_debug else visible).add(name)
        return visible, debug_only

    def test_groups_visible_without_developer_mode(self):
        operator = self.env.ref("maintenance_shareholder_equipment.group_equipment_operator")
        approver = self.env.ref("maintenance_shareholder_equipment.group_equipment_approver")
        manager = self.env.ref("maintenance.group_equipment_manager")
        visible, _debug = self._visible_selection_fields()
        self.assertIn("sel_groups_%s" % operator.id, visible)
        self.assertIn("sel_groups_%s" % approver.id, visible)
        self.assertNotIn("in_group_%s" % operator.id, visible)
        self.assertNotIn("in_group_%s" % approver.id, visible)
        self.assertTrue(
            any(name.startswith("sel_groups_") and str(manager.id) in name.split("_")[2:]
                for name in visible),
            "the Maintenance section is a drop-down list again",
        )

    def test_implied_groups_unchanged(self):
        operator = self.env.ref("maintenance_shareholder_equipment.group_equipment_operator")
        approver = self.env.ref("maintenance_shareholder_equipment.group_equipment_approver")
        self.assertIn(self.env.ref("stock.group_stock_user"), operator.implied_ids)
        self.assertNotIn(operator, approver.trans_implied_ids)
        self.assertNotIn(approver, operator.trans_implied_ids)

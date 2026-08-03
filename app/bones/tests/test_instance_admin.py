from django.contrib import admin
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from ..instance_admin import (
    InstanceDeletionAdmin, InstanceDeletionForm, InstanceRestorationForm,
    InstanceSearchForm,
)
from ..models import InstanceDeletion


class InstanceDeletionAdminTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.model_admin = InstanceDeletionAdmin(InstanceDeletion, admin.site)

    def test_search_requires_at_least_one_value(self):
        form = InstanceSearchForm({})
        self.assertFalse(form.is_valid())
        self.assertIn("Enter at least one search value", str(form.errors))

    def test_search_accepts_hierarchy_identifiers(self):
        form = InstanceSearchForm(
            {
                "template_name": "105",
                "transect_uid": 4478950,
                "occurrence_number": 18,
                "instance_number": 4,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_deletion_requires_reason_and_confirmation(self):
        self.assertFalse(InstanceDeletionForm({"reason": "Required reason"}).is_valid())
        self.assertFalse(InstanceDeletionForm({"confirm": True}).is_valid())
        self.assertTrue(
            InstanceDeletionForm({"reason": "Incorrect observation", "confirm": True}).is_valid()
        )

    def test_restoration_requires_reason_and_confirmation(self):
        self.assertFalse(InstanceRestorationForm({"reason": "Restore reason"}).is_valid())
        self.assertFalse(InstanceRestorationForm({"confirm": True}).is_valid())
        self.assertTrue(
            InstanceRestorationForm({"reason": "Deletion was incorrect", "confirm": True}).is_valid()
        )

    def test_reason_is_limited_to_history_field_length(self):
        form = InstanceDeletionForm({"reason": "x" * 101, "confirm": True})
        self.assertFalse(form.is_valid())

    def test_admin_routes_are_registered(self):
        self.assertEqual(
            reverse("admin:bones_instancedeletion_find"),
            "/admin/bones/instancedeletion/find/",
        )
        audit_id = "00000000-0000-0000-0000-000000000001"
        self.assertEqual(
            reverse("admin:bones_instancedeletion_restore_instance", kwargs={"audit_id": audit_id}),
            f"/admin/bones/instancedeletion/restore/{audit_id}/",
        )
        self.assertEqual(
            reverse(
                "admin:bones_instancedeletion_delete_instance",
                kwargs={"occurrence_id": 694, "instance_number": 4},
            ),
            "/admin/bones/instancedeletion/delete/694/4/",
        )

    def test_admin_search_uses_valid_text_and_related_user_lookups(self):
        self.assertIn("restored_by__username", self.model_admin.search_fields)
        self.assertNotIn("restored_by", self.model_admin.search_fields)
        self.assertNotIn("restored_at", self.model_admin.search_fields)
        request = self.factory.get("/admin/bones/instancedeletion/", {"q": "273"})
        queryset, _ = self.model_admin.get_search_results(
            request, InstanceDeletion.objects.all(), "273"
        )
        self.assertIn("273", str(queryset.query))

    def test_audit_records_are_not_editable_or_deletable(self):
        request = self.factory.get("/admin/bones/instancedeletion/")
        request.user = type(
            "User",
            (),
            {"has_perm": lambda self, permission: True},
        )()
        self.assertFalse(self.model_admin.has_add_permission(request))
        self.assertFalse(self.model_admin.has_change_permission(request))
        self.assertFalse(self.model_admin.has_delete_permission(request))
        self.assertTrue(self.model_admin.has_view_permission(request))

    def test_model_has_history_and_dedicated_permission(self):
        self.assertTrue(hasattr(InstanceDeletion, "history"))
        permissions = dict(InstanceDeletion._meta.permissions)
        self.assertIn("delete_completed_instance", permissions)
        self.assertIn("restore_completed_instance", permissions)

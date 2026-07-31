from django.contrib import admin
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from ..models import TransectDeletion
from ..transect_admin import TransectDeletionAdmin, TransectDeletionForm, TransectSearchForm


class TransectDeletionAdminTests(SimpleTestCase):
    def setUp(self):
        self.admin = TransectDeletionAdmin(TransectDeletion, admin.site)
        self.factory = RequestFactory()

    def test_search_requires_a_value(self):
        self.assertFalse(TransectSearchForm({}).is_valid())
        self.assertTrue(TransectSearchForm({"transect_uid": 4478950}).is_valid())

    def test_deletion_requires_reason_and_confirmation(self):
        self.assertFalse(TransectDeletionForm({"reason": "Duplicate"}).is_valid())
        self.assertFalse(TransectDeletionForm({"confirm": True}).is_valid())
        self.assertTrue(TransectDeletionForm({"reason": "Duplicate", "confirm": True}).is_valid())

    def test_admin_routes(self):
        self.assertEqual(reverse("admin:bones_transectdeletion_find"), "/admin/bones/transectdeletion/find/")
        self.assertEqual(reverse("admin:bones_transectdeletion_delete_transect", kwargs={"transect_uid": 42}), "/admin/bones/transectdeletion/delete/42/")

    def test_audit_is_immutable_and_has_permission(self):
        request = self.factory.get("/")
        self.assertFalse(self.admin.has_add_permission(request))
        self.assertFalse(self.admin.has_change_permission(request))
        self.assertFalse(self.admin.has_delete_permission(request))
        self.assertIn("delete_completed_transect", dict(TransectDeletion._meta.permissions))

from pathlib import Path

from django.contrib import admin
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from ..models import OccurrenceDeletion
from ..occurrence_admin import (OccurrenceDeletionAdmin,
                                OccurrenceDeletionForm,
                                OccurrenceSearchForm)


class OccurrenceDeletionAdminTests(SimpleTestCase):
    def setUp(self):
        self.admin=OccurrenceDeletionAdmin(OccurrenceDeletion,admin.site)
        self.factory=RequestFactory()

    def test_search_requires_a_value(self):
        self.assertFalse(OccurrenceSearchForm({}).is_valid())
        self.assertTrue(OccurrenceSearchForm({"occurrence_id":321}).is_valid())

    def test_deletion_requires_reason_and_confirmation(self):
        self.assertFalse(OccurrenceDeletionForm({"reason":"Duplicate"}).is_valid())
        self.assertFalse(OccurrenceDeletionForm({"confirm":True}).is_valid())
        self.assertTrue(OccurrenceDeletionForm({"reason":"Duplicate","confirm":True}).is_valid())

    def test_admin_routes(self):
        self.assertEqual(reverse("admin:bones_occurrencedeletion_find"),"/admin/bones/occurrencedeletion/find/")
        self.assertEqual(reverse("admin:bones_occurrencedeletion_delete_occurrence",kwargs={"occurrence_id":321}),"/admin/bones/occurrencedeletion/delete/321/")

    def test_audit_is_immutable_and_has_permission(self):
        request=self.factory.get("/")
        self.assertFalse(self.admin.has_add_permission(request))
        self.assertFalse(self.admin.has_change_permission(request))
        self.assertFalse(self.admin.has_delete_permission(request))
        self.assertIn("delete_completed_occurrence",dict(OccurrenceDeletion._meta.permissions))

    def test_confirmation_template_lists_dependent_data_and_images(self):
        template=(Path(__file__).resolve().parents[1]/"templates"/"admin"/"bones"/"occurrencedeletion"/"delete_occurrence.html").read_text(encoding="utf-8")
        for label in ("Occurrence notes","Workflows","Responses","Image links","Exclusive image files"):
            self.assertIn(label,template)

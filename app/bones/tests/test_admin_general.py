from types import SimpleNamespace
from django.contrib import admin
from django.test import RequestFactory, SimpleTestCase
from ..admin_general import BonesHistoryAdmin, ResponseAdmin
from ..models import CompletedOccurrence, CompletedResponse, CompletedTransect, CompletedWorkflow

class GeneralAdminTests(SimpleTestCase):
    def setUp(self):
        self.factory=RequestFactory()
        self.user=SimpleNamespace(has_perm=lambda permission: True)

    def test_main_operational_models_are_registered(self):
        for model in (CompletedTransect,CompletedOccurrence,CompletedWorkflow,CompletedResponse):
            with self.subTest(model=model.__name__): self.assertIn(model,admin.site._registry)

    def test_answers_use_audited_admin(self):
        model_admin=admin.site._registry[CompletedResponse]
        self.assertIsInstance(model_admin,ResponseAdmin)
        self.assertIsInstance(model_admin,BonesHistoryAdmin)

    def test_answer_hierarchy_is_readonly(self):
        model_admin=admin.site._registry[CompletedResponse]
        for field in ("id","occurrence","workflow","question","question_number","question_text"):
            self.assertIn(field,model_admin.readonly_fields)
        for field in ("response_code","response","skipped"):
            self.assertIn(field,model_admin.fields)

    def test_edit_reason_is_required_for_existing_answer(self):
        model_admin=admin.site._registry[CompletedResponse]
        request=self.factory.get("/admin/bones/completedresponse/1/change/"); request.user=self.user
        instance=CompletedResponse(id=1,occurrence_id=2,workflow_id="w",question_id=None,question_text="Free text",skipped=False)
        form_class=model_admin.get_form(request,instance,change=True)
        form=form_class(instance=instance)
        self.assertTrue(form.fields["edit_reason"].required)
        self.assertIn("record_version",form.fields)
        self.assertIn("answer_option",form.fields)
        self.assertIsInstance(form.fields["answer_option"].widget, __import__("django").forms.HiddenInput)

    def test_operational_admins_disable_delete_and_bulk_delete(self):
        request=self.factory.get("/admin/"); request.user=self.user
        for model in (CompletedTransect,CompletedOccurrence,CompletedWorkflow,CompletedResponse):
            model_admin=admin.site._registry[model]
            with self.subTest(model=model.__name__):
                self.assertFalse(model_admin.has_delete_permission(request))
                self.assertNotIn("delete_selected",model_admin.get_actions(request))
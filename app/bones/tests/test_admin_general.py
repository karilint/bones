from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from pathlib import Path
from django.contrib import admin
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse
from ..admin_general import (BonesHistoryAdmin, OccurrenceInfoAdmin, ResponseAdmin,
                             WorkflowAdmin, WorkflowDeletionForm)
from ..models import CompletedOccurrence, CompletedOccurrenceInfo, CompletedResponse, CompletedTransect, CompletedWorkflow

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

    def test_workflow_removal_requires_reason_and_confirmation(self):
        self.assertFalse(WorkflowDeletionForm({"reason":"Correction"}).is_valid())
        self.assertFalse(WorkflowDeletionForm({"confirm":True}).is_valid())
        self.assertTrue(WorkflowDeletionForm({"reason":"Duplicate workflow","confirm":True}).is_valid())

    def test_workflow_admin_has_dedicated_removal_route(self):
        model_admin=admin.site._registry[CompletedWorkflow]
        self.assertIsInstance(model_admin,WorkflowAdmin)
        self.assertEqual(
            reverse("admin:bones_completedworkflow_remove",args=("workflow-1",)),
            "/admin/bones/completedworkflow/workflow-1/remove/",
        )

    def test_workflow_removal_template_documents_safeguards(self):
        template=(Path(__file__).resolve().parents[1]/"templates"/"admin"/"bones"/"completedworkflow"/"remove_workflow.html").read_text(encoding="utf-8")
        self.assertIn("last workflow in the instance",template)
        self.assertIn("Responses to delete",template)
        self.assertIn("Instance images",template)

    def test_occurrence_notes_use_audited_admin(self):
        model_admin=admin.site._registry[CompletedOccurrenceInfo]
        self.assertIsInstance(model_admin,OccurrenceInfoAdmin)
        self.assertIsInstance(model_admin,BonesHistoryAdmin)
        for field in ("id","occurrence","pre_or_post","question_text","response_data_type"):
            self.assertIn(field,model_admin.readonly_fields)
        for field in ("answer_option","response_code","response","edit_reason","record_version"):
            self.assertIn(field,model_admin.fields)

    def test_occurrence_note_without_options_uses_free_text_fields(self):
        model_admin=admin.site._registry[CompletedOccurrenceInfo]
        request=self.factory.get("/admin/bones/completedoccurrenceinfo/1/change/"); request.user=self.user
        instance=CompletedOccurrenceInfo(id=1,occurrence_id=2,pre_or_post="Post",question_text="Taxon Guess?",response_data_type=None)
        form=model_admin.get_form(request,instance,change=True)(instance=instance)
        self.assertTrue(form.fields["edit_reason"].required)
        self.assertIsInstance(form.fields["answer_option"].widget,__import__("django").forms.HiddenInput)
        self.assertNotIsInstance(form.fields["response"].widget,__import__("django").forms.HiddenInput)

    @patch("bones.admin_general.DataTypeOption.objects.filter")
    def test_occurrence_note_with_options_uses_dropdown(self,filter_options):
        option=SimpleNamespace(code="lion",text="Lion")
        options=MagicMock(); options.order_by.return_value=[option]; filter_options.return_value=options
        model_admin=admin.site._registry[CompletedOccurrenceInfo]
        request=self.factory.get("/admin/bones/completedoccurrenceinfo/1/change/"); request.user=self.user
        instance=CompletedOccurrenceInfo(id=1,occurrence_id=2,pre_or_post="Post",question_text="Taxon Guess?",response_data_type="taxon-type",response_code="lion",response="Lion")
        form_class=model_admin.get_form(request,instance,change=True)
        form=form_class(data={"answer_option":"lion","edit_reason":"Corrected identification","record_version":__import__("bones.admin_general",fromlist=["signature"]).signature(instance)},instance=instance)
        self.assertIsInstance(form.fields["answer_option"].widget,__import__("django").forms.Select)
        self.assertIsInstance(form.fields["response_code"].widget,__import__("django").forms.HiddenInput)
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.cleaned_data["response_code"],"lion")
        self.assertEqual(form.cleaned_data["response"],"Lion")
        filter_options.assert_called_once_with(data_type_id="taxon-type")

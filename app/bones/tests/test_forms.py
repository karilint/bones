from django.test import SimpleTestCase
from django_select2.forms import ModelSelect2Widget

from ..forms import (
    CompletedOccurrenceForm,
    CompletedTransectForm,
    CompletedWorkflowForm,
    QuestionForm,
)


class Select2FormWidgetTests(SimpleTestCase):
    """Ensure model forms expose select2 configuration as mandated."""

    def test_completed_transect_form_uses_select2_widget(self):
        form = CompletedTransectForm()
        widget = form.fields["transect_template"].widget
        self.assertIsInstance(widget, ModelSelect2Widget)
        self.assertEqual(widget.attrs.get("style"), "width: 100%")
        self.assertIn("data-placeholder", widget.attrs)
        self.assertIn("template", widget.attrs["data-placeholder"].lower())

    def test_completed_occurrence_form_select2_configuration(self):
        form = CompletedOccurrenceForm()
        widget = form.fields["transect"].widget
        self.assertIsInstance(widget, ModelSelect2Widget)
        self.assertEqual(widget.attrs.get("style"), "width: 100%")

    def test_completed_workflow_form_has_multiple_select2_fields(self):
        form = CompletedWorkflowForm()
        occurrence_widget = form.fields["occurrence"].widget
        workflow_widget = form.fields["template_workflow"].widget
        for widget in (occurrence_widget, workflow_widget):
            self.assertIsInstance(widget, ModelSelect2Widget)
            self.assertEqual(widget.attrs.get("style"), "width: 100%")

    def test_question_form_select2_fields(self):
        form = QuestionForm()
        for field_name in ("data_type", "workflow"):
            widget = form.fields[field_name].widget
            self.assertIsInstance(widget, ModelSelect2Widget)
            self.assertEqual(widget.attrs.get("style"), "width: 100%")
            self.assertIn("data-placeholder", widget.attrs)

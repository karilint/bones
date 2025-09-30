from django.test import RequestFactory, SimpleTestCase

from ..models import DataType, Question
from ..views.detail import QuestionDetailView


class QuestionDetailViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _build_view(self):
        view = QuestionDetailView()
        request = self.factory.get("/templates/questions/q1/")
        view.setup(request, pk="q1")
        data_type = DataType(id="dt1", name="Text", is_user_data_type=False)
        question = Question(
            id="q1",
            prompt="Example prompt",
            data_type=data_type,
            data_type_name="Text",
            workflow=None,
        )
        view.object = question
        return view, question

    def test_get_form_applies_w3_css_classes(self):
        view, _ = self._build_view()
        form = view.get_form()
        prompt_classes = form.fields["prompt"].widget.attrs["class"].split()
        self.assertIn("w3-input", prompt_classes)
        self.assertIn("w3-border", prompt_classes)
        self.assertIn("w3-round", prompt_classes)
        data_type_classes = form.fields["data_type"].widget.attrs["class"].split()
        self.assertIn("w3-select", data_type_classes)

    def test_breadcrumbs_include_questions_section(self):
        view, question = self._build_view()
        breadcrumbs = view.get_breadcrumbs()
        labels = [crumb["label"] for crumb in breadcrumbs]
        self.assertIn("Questions", labels)
        self.assertIn(f"Question {question}", labels)

from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from ..models import DataLogFile, DataType, Question
from ..views.detail import (
    DataLogFileDetailView, DataLogFilePayloadView, QuestionDetailView,
)


class DataLogFileDetailViewTests(SimpleTestCase):
    def test_queryset_defers_large_payload(self):
        deferred, is_deferred = DataLogFileDetailView().get_queryset().query.deferred_loading
        self.assertTrue(is_deferred)
        self.assertIn("contents", deferred)

    def test_detail_exposes_separate_payload_download(self):
        view = DataLogFileDetailView()
        view.object = DataLogFile(id=7)
        action = view.get_extra_actions()[0]
        self.assertEqual(action["url"], reverse("bones:logs:payload", kwargs={"pk": 7}))
        self.assertEqual(action["icon"], "fa-solid fa-download")

    @patch("bones.views.detail.get_object_or_404")
    def test_payload_download_is_plain_text_attachment(self, get_object):
        get_object.return_value = SimpleNamespace(pk=7, contents="payload text")
        response = DataLogFilePayloadView().get(RequestFactory().get("/"), pk=7)
        self.assertEqual(response.content, b"payload text")
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="data-log-7.txt"')


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

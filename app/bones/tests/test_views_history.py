from types import SimpleNamespace

from django.db import DatabaseError
from django.test import RequestFactory, SimpleTestCase

from ..models import Question
from ..views.history import HistoryIndexView, HistoryTimelineView


class DummyHistoryTimelineView(HistoryTimelineView):
    model = Question
    entity_label = "Question"
    entity_plural_label = "Questions"
    list_route_name = "history:questions"
    detail_route_name = "history:question_entry"
    record_route_name = "history:question_record"
    object_detail_route_name = "templates:question_detail"

    def get_history_queryset(self):
        return [
            SimpleNamespace(
                history_id=1,
                history_object_id="q1",
                history_user=None,
                instance=SimpleNamespace(pk="q1"),
            )
        ]


class ErrorHistoryTimelineView(DummyHistoryTimelineView):
    def get_history_queryset(self):  # pragma: no cover - intentionally raises
        raise DatabaseError("Unavailable")


class HistoryViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_history_index_sections(self):
        view = HistoryIndexView()
        request = self.factory.get("/history/")
        view.setup(request)
        context = view.get_context_data()
        sections = context["history_sections"]
        self.assertEqual(len(sections), 4)
        for section in sections:
            self.assertIsNotNone(section.label)

    def test_timeline_view_builds_entry_links(self):
        view = DummyHistoryTimelineView()
        request = self.factory.get("/history/questions/")
        view.setup(request)
        context = view.get_context_data()
        entries = context["history_entries"]
        self.assertTrue(entries)
        entry = entries[0]
        self.assertIn("record_url", entry)
        self.assertIn("detail_url", entry)
        self.assertIsNone(entry["record_url"])

    def test_timeline_view_handles_database_errors(self):
        view = ErrorHistoryTimelineView()
        request = self.factory.get("/history/questions/")
        view.setup(request)
        context = view.get_context_data()
        self.assertTrue(view.history_error)
        self.assertEqual(context["history_entries"], [])

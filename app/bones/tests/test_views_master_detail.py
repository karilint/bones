from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from ..views.master_detail import (
    BonesMasterDetailView,
    CompletedOccurrenceDetailView,
    CompletedTransectDetailView,
)


class MasterDetailViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_base_breadcrumbs_include_dashboard(self):
        class DummyMasterDetail(BonesMasterDetailView):
            template_name = "bones/completed_transect_detail.html"

        view = DummyMasterDetail()
        request = self.factory.get("/dummy/1/")
        view.setup(request, pk=1)
        view.object = SimpleNamespace(pk=1)
        breadcrumbs = view.get_breadcrumbs()
        self.assertEqual(breadcrumbs[0]["label"], "Dashboard")

    def test_completed_transect_tabs_include_history(self):
        view = CompletedTransectDetailView()
        request = self.factory.get("/transects/1/")
        view.setup(request, pk=1)
        view.object = SimpleNamespace(pk=1, history=SimpleNamespace(all=lambda: []))
        tabs = list(view.get_tabs())
        tab_ids = [tab["id"] for tab in tabs]
        self.assertIn("history", tab_ids)

    def test_completed_occurrence_extra_actions_use_safe_reverse(self):
        view = CompletedOccurrenceDetailView()
        request = self.factory.get("/occurrences/1/")
        view.setup(request, pk=1)
        view.object = SimpleNamespace(pk=1, transect=None, history=SimpleNamespace(all=lambda: []))
        actions = list(view.get_extra_actions())
        self.assertTrue(actions)
        for action in actions:
            self.assertIn("label", action)
            self.assertIn("icon", action)

    def test_format_coordinates_handles_missing_values(self):
        result = CompletedTransectDetailView._format_coordinates(None, 12)
        self.assertEqual(result, "—")
        formatted = CompletedTransectDetailView._format_coordinates(1.23, 4.56)
        self.assertIn("Lat", formatted)

    def test_completed_occurrence_instance_summaries_grouped_by_instance(self):
        class DummyManager:
            def __init__(self, items):
                self._items = list(items)

            def all(self):
                return list(self._items)

        view = CompletedOccurrenceDetailView()
        request = self.factory.get("/occurrences/42/")
        view.setup(request, pk=42)

        workflows = [
            SimpleNamespace(
                pk=1,
                template_workflow=SimpleNamespace(name="Alpha"),
                instance_number=1,
                completed_by="Alice",
            ),
            SimpleNamespace(
                pk=2,
                template_workflow=SimpleNamespace(name="Beta"),
                instance_number=2,
                completed_by="Bob",
            ),
            SimpleNamespace(
                pk=3,
                template_workflow=SimpleNamespace(name="Alpha"),
                instance_number=1,
                completed_by="Cara",
            ),
        ]
        responses = [
            SimpleNamespace(
                question_number=2,
                question_text="Second question",
                response="Answer two",
                response_code="R2",
                skipped=False,
                workflow=workflows[0],
            ),
            SimpleNamespace(
                question_number=1,
                question_text="First question",
                response="Answer one",
                response_code="R1",
                skipped=False,
                workflow=workflows[2],
            ),
            SimpleNamespace(
                question_number=1,
                question_text="Beta question",
                response="Answer beta",
                response_code="R4",
                skipped=False,
                workflow=workflows[1],
            ),
            SimpleNamespace(
                question_number=2,
                question_text="Skipped question",
                response="Should hide",
                response_code="R5",
                skipped=True,
                workflow=workflows[1],
            ),
        ]

        view.object = SimpleNamespace(
            pk=42,
            responses=DummyManager(responses),
            workflows=DummyManager(workflows),
        )

        with patch("bones.views.master_detail.safe_reverse", return_value="/workflows/"):
            instance_summaries = view.get_instance_summaries()

        self.assertEqual([summary["number"] for summary in instance_summaries], [1, 2])
        self.assertNotIn("—", [summary["display_number"] for summary in instance_summaries])

        instance_one = instance_summaries[0]
        instance_two = instance_summaries[1]

        self.assertEqual(len(instance_one["response_rows"]), 2)
        self.assertEqual(len(instance_one["workflow_rows"]), 2)
        self.assertEqual(instance_one["url"], "/workflows/?occurrence=42&instance_number=1")

        self.assertEqual(len(instance_two["response_rows"]), 1)
        self.assertEqual(len(instance_two["workflow_rows"]), 1)
        self.assertEqual(instance_two["url"], "/workflows/?occurrence=42&instance_number=2")

        instance_one_question_order = [row[0]["value"] for row in instance_one["response_rows"]]
        self.assertEqual(instance_one_question_order, ["First question", "Second question"])

        instance_two_questions = [row[0]["value"] for row in instance_two["response_rows"]]
        self.assertEqual(instance_two_questions, ["Beta question"])

from types import SimpleNamespace

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

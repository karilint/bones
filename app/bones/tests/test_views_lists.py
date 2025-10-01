from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import django_filters
from django.test import RequestFactory, SimpleTestCase

from ..models import CompletedTransect, TemplateTransect
from ..views.lists import (
    BonesListView,
    CompletedTransectListView,
    TemplateTransectListView,
)


class DummyFilterSet(django_filters.FilterSet):
    class Meta:
        model = CompletedTransect
        fields = []


class DummyListView(BonesListView):
    template_name = "bones/completed_transect_list.html"
    model = CompletedTransect
    filterset_class = DummyFilterSet
    page_icon = "fa-solid fa-route"
    page_title = "Completed transects"
    intro_text = "Inspect collected transects"
    table_caption = "Transect summary"
    detail_route_name = "transects:detail"
    history_route_name = "history:transect_record"

    def get_table_headers(self):
        return [{"label": "Name"}]

    def get_table_rows(self, object_list):
        return [[{"value": getattr(obj, "name", "Unknown")}] for obj in object_list]


class BonesListViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_action_buttons_render_disabled_when_missing_url(self):
        view = DummyListView()
        button_html = view._render_action_button(None, "View", "fa-eye")
        self.assertIn("w3-disabled", button_html)
        self.assertIn("fa-eye", button_html)

    def test_action_buttons_include_links_when_url_present(self):
        view = DummyListView()
        html = view._render_action_button("/detail/", "View", "fa-eye")
        self.assertIn("href=\"/detail/\"", html)
        self.assertIn("w3-button", html)

    def test_get_context_data_includes_table_metadata(self):
        request = self.factory.get("/transects/")
        view = DummyListView()
        view.setup(request)
        view.object_list = []
        context = view.get_context_data(object_list=[])
        self.assertEqual(context["page_title"], "Completed transects")
        self.assertEqual(context["table_headers"], [{"label": "Name"}])
        self.assertFalse(context["filter_active"])
        self.assertEqual(context["filter_querystring"], "")

    def test_get_detail_and_history_urls_return_none_without_namespace(self):
        view = DummyListView()
        obj = SimpleNamespace(pk=123)
        detail_url = view.get_detail_url(obj)
        history_url = view.get_history_url(obj)
        self.assertIsNone(detail_url)
        self.assertIsNone(history_url)


class TemplateTransectListViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(
            is_authenticated=True,
            has_perms=lambda perms: True,
        )

    @patch("bones.views.lists.TemplateTransectFilterSet")
    @patch("bones.views.lists.TemplateTransect.objects")
    def test_queryset_orders_by_descending_scheduled_time(
        self, mock_manager, mock_filterset
    ):
        request = self.factory.get("/templates/transects/")
        request.user = self.user

        ordered_queryset = MagicMock(name="OrderedQuerySet")
        ordered_queryset.model = TemplateTransect
        mock_manager.order_by.return_value = ordered_queryset

        filter_instance = mock_filterset.return_value
        filter_instance.form = MagicMock()
        filter_instance.qs = ordered_queryset

        view = TemplateTransectListView()
        view.setup(request)
        view.filterset_class = mock_filterset
        queryset = view.get_queryset()

        mock_manager.order_by.assert_called_once_with("-scheduled_time")
        mock_filterset.assert_called_once_with(data={}, queryset=ordered_queryset)
        self.assertIs(queryset, ordered_queryset)


class CompletedTransectListViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(
            is_authenticated=True,
            has_perms=lambda perms: True,
        )

    @patch("bones.views.lists.CompletedTransectFilterSet")
    @patch("bones.views.lists.CompletedTransect.objects")
    def test_queryset_annotates_occurrence_counts(self, mock_manager, mock_filterset):
        request = self.factory.get("/completed-transects/")
        request.user = self.user

        select_related_qs = MagicMock(name="SelectRelatedQuerySet")
        with_counts_qs = MagicMock(name="WithOccurrenceCountsQuerySet")
        ordered_qs = MagicMock(name="OrderedQuerySet")
        ordered_qs.model = CompletedTransect

        mock_manager.select_related.return_value = select_related_qs
        select_related_qs.with_occurrence_counts.return_value = with_counts_qs
        select_related_qs.with_occurrences = MagicMock(name="with_occurrences")
        with_counts_qs.order_by.return_value = ordered_qs

        filter_instance = mock_filterset.return_value
        filter_instance.form = MagicMock()
        filter_instance.qs = ordered_qs

        view = CompletedTransectListView()
        view.setup(request)
        view.filterset_class = mock_filterset
        queryset = view.get_queryset()

        mock_manager.select_related.assert_called_once_with("transect_template")
        select_related_qs.with_occurrence_counts.assert_called_once_with()
        select_related_qs.with_occurrences.assert_not_called()
        with_counts_qs.order_by.assert_called_once_with("-start_time")
        mock_filterset.assert_called_once_with(data={}, queryset=ordered_qs)
        self.assertIs(queryset, ordered_qs)

    def test_table_rows_use_annotated_occurrence_count(self):
        class DummyTransect:
            def __init__(self):
                self.pk = 1
                self.name = "Transect"
                self.transect_template = SimpleNamespace(name="Template")
                self.start_time = None
                self.end_time = None
                self.state = "Complete"
                self.occurrence_count = 5

            @property
            def occurrences(self):  # pragma: no cover - should not be accessed
                raise AssertionError("occurrences should not be accessed")

        view = CompletedTransectListView()
        view.get_detail_url = MagicMock(return_value="detail-url")
        view.get_action_buttons = MagicMock(return_value="actions")

        rows = view.get_table_rows([DummyTransect()])

        self.assertEqual(rows[0][5]["value"], 5)
        view.get_detail_url.assert_called_once()
        view.get_action_buttons.assert_called_once()

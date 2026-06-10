from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import django_filters
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError
from django.test import RequestFactory, SimpleTestCase
from django.views.generic import ListView

from ..filters import (
    CompletedTransectFilterSet,
    FilteredListViewMixin,
    OLD_RESERVE_QUESTION_TEXT,
    TemplateTransectFilterSet,
    _info_choices,
    _state_choices,
)
from ..models import CompletedTransect, TemplateTransect


class DummyFilterSet(django_filters.FilterSet):
    class Meta:
        model = CompletedTransect
        fields = []


class DummyListView(FilteredListViewMixin, ListView):
    """Minimal list view for exercising the filter mixin."""

    model = CompletedTransect
    filterset_class = DummyFilterSet
    queryset = CompletedTransect.objects.none()
    template_name = "bones/completed_transect_list.html"

    def get_context_data(self, **kwargs):  # pragma: no cover - inherited behaviour
        return super().get_context_data(**kwargs)


class FilterErrorFilterSet(django_filters.FilterSet):
    def __init__(self, *args, **kwargs):
        raise DatabaseError("Database temporarily unavailable")

    class Meta:
        model = CompletedTransect
        fields = []


class FilterErrorListView(FilteredListViewMixin, ListView):
    model = CompletedTransect
    filterset_class = FilterErrorFilterSet
    queryset = CompletedTransect.objects.none()
    template_name = "bones/completed_transect_list.html"


class FilteredListViewMixinTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_state_choices_sorted_with_blank(self):
        choices = _state_choices(["b", "a", "", None])
        self.assertEqual(choices[0], ("", "All states"))
        self.assertEqual([label for value, label in choices[1:]], ["a", "b"])

    def test_info_choices_sorted_with_blank(self):
        choices = _info_choices(["Post", "Pre", "", None, "Post"], "All phases")
        self.assertEqual(choices[0], ("", "All phases"))
        self.assertEqual(
            [label for value, label in choices[1:]],
            ["Post", "Pre"],
        )

    def test_filtered_list_view_populates_filterset(self):
        request = self.factory.get("/transects/?state=active")
        view = DummyListView()
        view.setup(request)
        queryset = view.get_queryset()
        self.assertIsNotNone(view.filterset)
        self.assertIsNone(view.filter_error)
        self.assertEqual(queryset.model, CompletedTransect)

    def test_filtered_list_view_handles_filter_errors(self):
        request = self.factory.get("/transects/")
        view = FilterErrorListView()
        view.setup(request)
        queryset = view.get_queryset()
        self.assertIsNone(view.filterset)
        self.assertIsInstance(view.filter_error, DatabaseError)
        self.assertEqual(list(queryset), [])

    def test_merge_widget_classes_handles_iterables(self):
        view = DummyListView()
        widget = SimpleNamespace(attrs={"class": ["w3-input"]})
        view._merge_widget_classes(widget, "w3-border", "w3-input")
        self.assertEqual(widget.attrs["class"], "w3-input w3-border")

    def test_missing_filterset_class_raises(self):
        class MissingFilterView(FilteredListViewMixin, ListView):
            queryset = CompletedTransect.objects.none()
            template_name = "bones/completed_transect_list.html"

        request = self.factory.get("/transects/")
        view = MissingFilterView()
        view.setup(request)
        with self.assertRaises(ImproperlyConfigured):
            view.get_queryset()


class TemplateTransectFilterSetTests(SimpleTestCase):
    def test_scheduling_filters_target_indexed_column(self):
        queryset = TemplateTransect.objects.none()
        filterset = TemplateTransectFilterSet(data={}, queryset=queryset)

        scheduled_after = filterset.filters["scheduled_after"]
        scheduled_before = filterset.filters["scheduled_before"]

        self.assertEqual(scheduled_after.field_name, "scheduled_time")
        self.assertEqual(scheduled_before.field_name, "scheduled_time")
        self.assertEqual(scheduled_after.lookup_expr, "gte")
        self.assertEqual(scheduled_before.lookup_expr, "lte")


class CompletedTransectFilterSetTests(SimpleTestCase):
    @patch("bones.filters.CompletedTransectInfo.objects")
    @patch("bones.filters.CompletedTransect.objects")
    def test_completed_transect_filterset_adds_phase_and_old_reserve_choices(
        self, mock_transect_manager, mock_info_manager
    ):
        old_reserve_queryset = MagicMock()
        old_reserve_queryset.values_list.return_value = ["Yes", "No", "Yes"]
        mock_info_manager.filter.return_value = old_reserve_queryset
        mock_info_manager.values_list.return_value = ["Pre", "Post", "Pre"]
        mock_transect_manager.values_list.return_value = ["Complete"]

        filterset = CompletedTransectFilterSet(
            data={},
            queryset=CompletedTransect.objects.none(),
        )

        self.assertIn("phase", filterset.filters)
        self.assertIn("old_reserve_response", filterset.filters)
        self.assertEqual(
            list(filterset.filters["phase"].field.choices),
            [("", "All phases"), ("Post", "Post"), ("Pre", "Pre")],
        )
        self.assertEqual(
            list(filterset.filters["old_reserve_response"].field.choices),
            [("", "All responses"), ("No", "No"), ("Yes", "Yes")],
        )
        mock_info_manager.filter.assert_called_once_with(
            question_text__iexact=OLD_RESERVE_QUESTION_TEXT
        )

    def test_phase_filter_targets_transect_details_and_distincts(self):
        filterset = CompletedTransectFilterSet.__new__(CompletedTransectFilterSet)
        queryset = MagicMock()
        filtered = MagicMock()
        queryset.filter.return_value = filtered
        filtered.distinct.return_value = "distinct-queryset"

        result = filterset.filter_phase(queryset, "phase", "Pre")

        queryset.filter.assert_called_once_with(details__pre_or_post="Pre")
        filtered.distinct.assert_called_once_with()
        self.assertEqual(result, "distinct-queryset")

    def test_old_reserve_filter_targets_question_response_and_distincts(self):
        filterset = CompletedTransectFilterSet.__new__(CompletedTransectFilterSet)
        queryset = MagicMock()
        filtered = MagicMock()
        queryset.filter.return_value = filtered
        filtered.distinct.return_value = "distinct-queryset"

        result = filterset.filter_old_reserve_response(
            queryset,
            "old_reserve_response",
            "Yes",
        )

        queryset.filter.assert_called_once_with(
            details__question_text__iexact=OLD_RESERVE_QUESTION_TEXT,
            details__response="Yes",
        )
        filtered.distinct.assert_called_once_with()
        self.assertEqual(result, "distinct-queryset")

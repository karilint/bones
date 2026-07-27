from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import django_filters
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError
from django.http import QueryDict
from django.test import RequestFactory, SimpleTestCase
from django.views.generic import ListView

from ..filters import (
    CompletedTransectFilterSet,
    FilteredListViewMixin,
    TemplateTransectFilterSet,
    _info_choices,
    _info_multi_choices,
    _note_key,
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

    def test_info_multi_choices_sorted_without_blank(self):
        choices = _info_multi_choices(["Grassland", "", None, "Heath", "Grassland"])
        self.assertEqual(choices, (("Grassland", "Grassland"), ("Heath", "Heath")))

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
    def test_filter_order_pairs_dates_and_filters_displayed_transect(self):
        self.assertEqual(
            list(CompletedTransectFilterSet.base_filters),
            ["start_date", "end_date", "state", "phase", "transect"],
        )
        transect_filter = CompletedTransectFilterSet.base_filters["transect"]
        self.assertEqual(transect_filter.field_name, "name")
        self.assertEqual(transect_filter.label, "Transect")
        self.assertEqual(transect_filter.lookup_expr, "icontains")
        self.assertNotIn(
            "transect_template", CompletedTransectFilterSet.base_filters
        )
    @patch("bones.filters.CompletedTransectInfo.objects")
    @patch("bones.filters.CompletedTransect.objects")
    def test_completed_transect_filterset_adds_phase_and_note_choices(
        self, mock_transect_manager, mock_info_manager
    ):
        mock_info_manager.values_list.side_effect = [
            ["Pre", "Post", "Pre"],
            [
                ("Pre", "OPC Vegetation", "Grassland"),
                ("Pre", "OPC Vegetation", "Heath"),
                ("Pre", "Transect physical habitat", "grass closed"),
            ],
        ]
        mock_transect_manager.values_list.return_value = ["Complete"]

        filterset = CompletedTransectFilterSet(
            data={},
            queryset=CompletedTransect.objects.none(),
        )

        self.assertIn("phase", filterset.filters)
        self.assertNotIn("old_reserve_response", filterset.filters)
        self.assertEqual(
            list(filterset.filters["phase"].field.choices),
            [("", "All phases"), ("Post", "Post"), ("Pre", "Pre")],
        )
        self.assertEqual(
            filterset.note_filter_choices["notes"],
            (
                ("", "Any phase/question"),
                (_note_key("Pre", "OPC Vegetation"), "Pre / OPC Vegetation"),
                (
                    _note_key("Pre", "Transect physical habitat"),
                    "Pre / Transect physical habitat",
                ),
            ),
        )
        self.assertEqual(
            filterset.note_filter_choices["response_map"][
                _note_key("Pre", "OPC Vegetation")
            ],
            (("Grassland", "Grassland"), ("Heath", "Heath")),
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

    def test_note_filters_parse_indexed_rows_and_multiple_responses(self):
        data = QueryDict(mutable=True)
        data.update(
            {
                "note_0_note": _note_key("Pre", "OPC Vegetation"),
                "note_1_note": _note_key("Pre", "Transect physical habitat"),
            }
        )
        data.setlist("note_0_response", ["Grassland", "Heath"])
        data.setlist("note_1_response", ["grass closed"])

        filterset = CompletedTransectFilterSet.__new__(CompletedTransectFilterSet)
        filterset.data = data

        self.assertEqual(
            filterset._parse_note_filters(),
            [
                {
                    "index": 0,
                    "note_key": _note_key("Pre", "OPC Vegetation"),
                    "phase": "Pre",
                    "question": "OPC Vegetation",
                    "responses": ["Grassland", "Heath"],
                },
                {
                    "index": 1,
                    "note_key": _note_key("Pre", "Transect physical habitat"),
                    "phase": "Pre",
                    "question": "Transect physical habitat",
                    "responses": ["grass closed"],
                },
            ],
        )

    @patch("django_filters.FilterSet.filter_queryset")
    def test_note_filters_chain_rows_and_or_responses(self, mock_base_filter):
        filterset = CompletedTransectFilterSet.__new__(CompletedTransectFilterSet)
        filterset.note_filters = [
            {
                "index": 0,
                "phase": "Pre",
                "question": "OPC Vegetation",
                "responses": ["Grassland", "Heath"],
            },
            {
                "index": 1,
                "phase": "Pre",
                "question": "Transect physical habitat",
                "responses": ["grass closed"],
            },
        ]
        queryset = MagicMock()
        first_filtered = MagicMock()
        second_filtered = MagicMock()
        queryset.filter.return_value = first_filtered
        first_filtered.filter.return_value = second_filtered
        second_filtered.distinct.return_value = "distinct-queryset"
        mock_base_filter.return_value = queryset

        result = filterset.filter_queryset(queryset)

        queryset.filter.assert_called_once_with(
            details__pre_or_post="Pre",
            details__question_text="OPC Vegetation",
            details__response__in=["Grassland", "Heath"],
        )
        first_filtered.filter.assert_called_once_with(
            details__pre_or_post="Pre",
            details__question_text="Transect physical habitat",
            details__response__in=["grass closed"],
        )
        second_filtered.distinct.assert_called_once_with()
        self.assertEqual(result, "distinct-queryset")

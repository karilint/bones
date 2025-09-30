from types import SimpleNamespace

import django_filters
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError
from django.test import RequestFactory, SimpleTestCase
from django.views.generic import ListView

from ..filters import (
    FilteredListViewMixin,
    _state_choices,
)
from ..models import CompletedTransect


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

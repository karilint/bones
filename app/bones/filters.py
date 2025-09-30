"""Filter sets and helpers for bones list views.

The filter classes expose reusable date range controls, select2-backed
relations, and helper mixins that the upcoming list views can inherit to
wire django-filter into W3.CSS table archetypes.
"""
from __future__ import annotations

from typing import Iterable, Tuple

import django_filters
from django import forms
from django.core.exceptions import ImproperlyConfigured
from django_select2.forms import ModelSelect2Widget

from .forms import (
    CompletedOccurrenceSelect2Widget,
    CompletedTransectSelect2Widget,
    DataLogFileSelect2Widget,
    DataTypeSelect2Widget,
    TemplateTransectSelect2Widget,
    TemplateWorkflowSelect2Widget,
    select2_widget_attrs,
)
from .models import (
    CompletedOccurrence,
    CompletedTransect,
    CompletedWorkflow,
    DataLogFile,
    DataType,
    DataTypeOption,
    ProjectConfig,
    Question,
    TemplateTransect,
    TemplateWorkflow,
    TransectDataLog,
)

DATE_INPUT_ATTRS = {"type": "date"}


def _state_choices(queryset: Iterable[str]) -> Tuple[Tuple[str, str], ...]:
    """Return normalized state choices with an empty option."""

    unique_states = sorted({value for value in queryset if value})
    return (("", "All states"), *[(state, state) for state in unique_states])


class Select2FilterSetMixin:
    """Mixin that ensures select2 widgets share consistent attributes."""

    select2_fields: tuple[str, ...] = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.select2_fields:
            filter_ = self.filters.get(field_name)
            if filter_ and isinstance(filter_.field.widget, ModelSelect2Widget):
                placeholder = filter_.field.widget.attrs.get(
                    "data-placeholder", filter_.label or "Search"
                )
                filter_.field.widget.attrs = {
                    **select2_widget_attrs(placeholder),
                    **filter_.field.widget.attrs,
                }


class FilteredListViewMixin:
    """Mixin that plugs django-filter into upcoming class-based list views."""

    filterset_class = None
    filterset = None

    def get_filterset_class(self):
        if self.filterset_class is None:
            raise ImproperlyConfigured("filterset_class must be set")
        return self.filterset_class

    def get_filterset(self, queryset=None):
        filterset_class = self.get_filterset_class()
        filterset = filterset_class(
            data=self.request.GET or None,
            queryset=queryset if queryset is not None else self.get_queryset(),
        )
        self._apply_widget_styles(filterset.form)
        return filterset

    def _apply_widget_styles(self, form):
        """Ensure filter widgets align with the W3.CSS visual language."""

        for field in form.fields.values():
            widget = field.widget
            if isinstance(widget, ModelSelect2Widget):
                # Select2 manages its own styling; only ensure width is 100%.
                widget.attrs.setdefault("style", "width: 100%")
                continue

            if isinstance(
                widget,
                (
                    forms.TextInput,
                    forms.NumberInput,
                    forms.DateInput,
                    forms.DateTimeInput,
                    forms.EmailInput,
                    forms.TimeInput,
                    forms.URLInput,
                ),
            ):
                self._merge_widget_classes(widget, "w3-input", "w3-border")
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                self._merge_widget_classes(widget, "w3-select", "w3-border")
            elif isinstance(widget, forms.CheckboxInput):
                self._merge_widget_classes(widget, "w3-check")

    @staticmethod
    def _merge_widget_classes(widget, *new_classes):
        """Append CSS utility classes to a widget without duplicates."""

        existing_attr = widget.attrs.get("class", "")
        if isinstance(existing_attr, (list, tuple, set)):
            existing = [str(value) for value in existing_attr]
        else:
            existing = str(existing_attr or "").split()

        for css_class in new_classes:
            if css_class and css_class not in existing:
                existing.append(css_class)

        widget.attrs["class"] = " ".join(existing).strip()

        return None

    def get_queryset(self):  # pragma: no cover - integration point for future views
        queryset = super().get_queryset()
        self.filterset = self.get_filterset(queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):  # pragma: no cover - integration point
        kwargs.setdefault("filter", self.filterset)
        return super().get_context_data(**kwargs)


class CompletedTransectFilterSet(Select2FilterSetMixin, django_filters.FilterSet):
    """Filters for completed transects."""

    select2_fields = ("transect_template",)

    start_date = django_filters.DateFilter(
        field_name="start_time",
        lookup_expr="gte",
        label="Started after",
        widget=forms.DateInput(attrs=DATE_INPUT_ATTRS),
    )
    end_date = django_filters.DateFilter(
        field_name="end_time",
        lookup_expr="lte",
        label="Ended before",
        widget=forms.DateInput(attrs=DATE_INPUT_ATTRS),
    )
    state = django_filters.ChoiceFilter(
        field_name="state",
        label="State",
        choices=(),
    )
    transect_template = django_filters.ModelChoiceFilter(
        field_name="transect_template",
        queryset=TemplateTransect.objects.all(),
        label="Template transect",
        widget=TemplateTransectSelect2Widget(
            attrs=select2_widget_attrs("Search template transects")
        ),
    )

    class Meta:
        model = CompletedTransect
        fields = ["state", "transect_template"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        state_values = CompletedTransect.objects.values_list("state", flat=True)
        choices = _state_choices(state_values)
        self.filters["state"].extra["choices"] = choices
        self.filters["state"].field.choices = choices
        self.filters["state"].field.widget.attrs.setdefault("class", "w3-select")


class CompletedOccurrenceFilterSet(Select2FilterSetMixin, django_filters.FilterSet):
    """Filters for completed occurrences."""

    select2_fields = ("transect",)

    start_date = django_filters.DateFilter(
        field_name="recording_start_time",
        lookup_expr="gte",
        label="Started after",
        widget=forms.DateInput(attrs=DATE_INPUT_ATTRS),
    )
    end_date = django_filters.DateFilter(
        field_name="recording_end_time",
        lookup_expr="lte",
        label="Ended before",
        widget=forms.DateInput(attrs=DATE_INPUT_ATTRS),
    )
    state = django_filters.ChoiceFilter(
        field_name="state",
        label="State",
        choices=(),
    )
    transect = django_filters.ModelChoiceFilter(
        field_name="transect",
        queryset=CompletedTransect.objects.select_related("transect_template"),
        label="Transect",
        widget=CompletedTransectSelect2Widget(
            attrs=select2_widget_attrs("Search completed transects")
        ),
    )
    occurrence_number = django_filters.NumberFilter(
        field_name="occurrence_number",
        lookup_expr="exact",
        label="Occurrence number",
    )

    class Meta:
        model = CompletedOccurrence
        fields = ["state", "transect", "occurrence_number"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        state_values = CompletedOccurrence.objects.values_list("state", flat=True)
        choices = _state_choices(state_values)
        self.filters["state"].extra["choices"] = choices
        self.filters["state"].field.choices = choices
        self.filters["state"].field.widget.attrs.setdefault("class", "w3-select")


class CompletedWorkflowFilterSet(Select2FilterSetMixin, django_filters.FilterSet):
    """Filters for completed workflows."""

    select2_fields = ("occurrence", "template_workflow")

    occurrence = django_filters.ModelChoiceFilter(
        field_name="occurrence",
        queryset=CompletedOccurrence.objects.select_related("transect"),
        label="Occurrence",
        widget=CompletedOccurrenceSelect2Widget(
            attrs=select2_widget_attrs("Search occurrences")
        ),
    )
    template_workflow = django_filters.ModelChoiceFilter(
        field_name="template_workflow",
        queryset=TemplateWorkflow.objects.all(),
        label="Template workflow",
        widget=TemplateWorkflowSelect2Widget(
            attrs=select2_widget_attrs("Search template workflows")
        ),
    )
    completed_by = django_filters.CharFilter(
        field_name="completed_by",
        lookup_expr="icontains",
        label="Assigned user",
    )
    instance_number = django_filters.NumberFilter(
        field_name="instance_number",
        lookup_expr="exact",
        label="Instance number",
    )

    class Meta:
        model = CompletedWorkflow
        fields = ["occurrence", "template_workflow", "completed_by", "instance_number"]


class TemplateTransectFilterSet(django_filters.FilterSet):
    """Filters for template transects."""

    scheduled_after = django_filters.DateFilter(
        field_name="scheduled_time",
        lookup_expr="gte",
        label="Scheduled after",
        widget=forms.DateInput(attrs=DATE_INPUT_ATTRS),
    )
    scheduled_before = django_filters.DateFilter(
        field_name="scheduled_time",
        lookup_expr="lte",
        label="Scheduled before",
        widget=forms.DateInput(attrs=DATE_INPUT_ATTRS),
    )
    name = django_filters.CharFilter(
        field_name="name", lookup_expr="icontains", label="Name contains"
    )

    class Meta:
        model = TemplateTransect
        fields = ["name"]


class TemplateWorkflowFilterSet(django_filters.FilterSet):
    """Filters for template workflows."""

    name = django_filters.CharFilter(
        field_name="name", lookup_expr="icontains", label="Name contains"
    )
    added_after = django_filters.DateFilter(
        field_name="date_added",
        lookup_expr="gte",
        label="Added after",
        widget=forms.DateInput(attrs=DATE_INPUT_ATTRS),
    )
    added_before = django_filters.DateFilter(
        field_name="date_added",
        lookup_expr="lte",
        label="Added before",
        widget=forms.DateInput(attrs=DATE_INPUT_ATTRS),
    )

    class Meta:
        model = TemplateWorkflow
        fields = ["name"]


class QuestionFilterSet(Select2FilterSetMixin, django_filters.FilterSet):
    """Filters for question definitions."""

    select2_fields = ("workflow", "data_type")

    workflow = django_filters.ModelChoiceFilter(
        field_name="workflow",
        queryset=TemplateWorkflow.objects.all(),
        label="Workflow",
        widget=TemplateWorkflowSelect2Widget(
            attrs=select2_widget_attrs("Search template workflows")
        ),
    )
    data_type = django_filters.ModelChoiceFilter(
        field_name="data_type",
        queryset=DataType.objects.all(),
        label="Data type",
        widget=DataTypeSelect2Widget(
            attrs=select2_widget_attrs("Search data types")
        ),
    )
    prompt = django_filters.CharFilter(
        field_name="prompt",
        lookup_expr="icontains",
        label="Prompt contains",
    )
    data_type_name = django_filters.CharFilter(
        field_name="data_type_name",
        lookup_expr="icontains",
        label="Data type name contains",
    )

    class Meta:
        model = Question
        fields = ["workflow", "data_type", "prompt", "data_type_name"]


class DataTypeFilterSet(django_filters.FilterSet):
    """Filters for data types."""

    name = django_filters.CharFilter(
        field_name="name", lookup_expr="icontains", label="Name contains"
    )
    is_user_data_type = django_filters.BooleanFilter(
        field_name="is_user_data_type", label="User data type"
    )

    class Meta:
        model = DataType
        fields = ["name", "is_user_data_type"]


class DataTypeOptionFilterSet(Select2FilterSetMixin, django_filters.FilterSet):
    """Filters for data type options."""

    select2_fields = ("data_type",)

    data_type = django_filters.ModelChoiceFilter(
        field_name="data_type",
        queryset=DataType.objects.all(),
        label="Data type",
        widget=DataTypeSelect2Widget(
            attrs=select2_widget_attrs("Search data types")
        ),
    )
    code = django_filters.CharFilter(
        field_name="code", lookup_expr="icontains", label="Code contains"
    )
    text = django_filters.CharFilter(
        field_name="text", lookup_expr="icontains", label="Text contains"
    )

    class Meta:
        model = DataTypeOption
        fields = ["data_type", "code", "text"]


class ProjectConfigFilterSet(django_filters.FilterSet):
    """Filters for project configuration records."""

    published_after = django_filters.DateFilter(
        field_name="publish_date",
        lookup_expr="gte",
        label="Published after",
        widget=forms.DateInput(attrs=DATE_INPUT_ATTRS),
    )
    published_before = django_filters.DateFilter(
        field_name="publish_date",
        lookup_expr="lte",
        label="Published before",
        widget=forms.DateInput(attrs=DATE_INPUT_ATTRS),
    )
    project = django_filters.CharFilter(
        field_name="project", lookup_expr="icontains", label="Project contains"
    )

    class Meta:
        model = ProjectConfig
        fields = ["project"]


class DataLogFileFilterSet(django_filters.FilterSet):
    """Filters for uploaded data log files."""

    uploaded_after = django_filters.DateFilter(
        field_name="upload_date",
        lookup_expr="gte",
        label="Uploaded after",
        widget=forms.DateInput(attrs=DATE_INPUT_ATTRS),
    )
    uploaded_before = django_filters.DateFilter(
        field_name="upload_date",
        lookup_expr="lte",
        label="Uploaded before",
        widget=forms.DateInput(attrs=DATE_INPUT_ATTRS),
    )
    uploaded_by = django_filters.CharFilter(
        field_name="uploaded_by",
        lookup_expr="icontains",
        label="Uploaded by contains",
    )

    class Meta:
        model = DataLogFile
        fields = ["uploaded_by"]


class TransectDataLogFilterSet(Select2FilterSetMixin, django_filters.FilterSet):
    """Filters for transect/data log links."""

    select2_fields = ("data_log_file", "transect")

    data_log_file = django_filters.ModelChoiceFilter(
        field_name="data_log_file",
        queryset=DataLogFile.objects.all(),
        label="Data log file",
        widget=DataLogFileSelect2Widget(
            attrs=select2_widget_attrs("Search data log files")
        ),
    )
    transect = django_filters.ModelChoiceFilter(
        field_name="transect",
        queryset=CompletedTransect.objects.all(),
        label="Transect",
        widget=CompletedTransectSelect2Widget(
            attrs=select2_widget_attrs("Search completed transects")
        ),
    )
    is_primary = django_filters.BooleanFilter(
        field_name="is_primary", label="Primary file"
    )
    username = django_filters.CharFilter(
        field_name="username",
        lookup_expr="icontains",
        label="Username contains",
    )

    class Meta:
        model = TransectDataLog
        fields = ["data_log_file", "transect", "is_primary", "username"]

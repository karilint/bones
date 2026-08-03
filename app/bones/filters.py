"""Filter sets and helpers for bones list views.

The filter classes expose reusable date range controls, select2-backed
relations, and helper mixins that the upcoming list views can inherit to
wire django-filter into W3.CSS table archetypes.
"""
from __future__ import annotations

import json
from typing import Iterable, Tuple, cast

import django_filters
from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError
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
    CompletedOccurrenceInfo,
    CompletedTransect,
    CompletedTransectInfo,
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
NOTE_FILTER_PREFIX = "note_"
NOTE_FILTER_MAX_ROWS = 10


def _state_choices(queryset: Iterable[str]) -> Tuple[Tuple[str, str], ...]:
    """Return normalized state choices with an empty option."""

    unique_states = sorted({value for value in queryset if value})
    return (("", "All states"), *[(state, state) for state in unique_states])


def _info_choices(
    queryset: Iterable[str], empty_label: str
) -> Tuple[Tuple[str, str], ...]:
    """Return normalized completed-transect info choices with an empty option."""

    unique_values = sorted({value for value in queryset if value})
    return (("", empty_label), *[(value, value) for value in unique_values])


def _info_multi_choices(queryset: Iterable[str]) -> Tuple[Tuple[str, str], ...]:
    """Return normalized choices without an empty option for multi-select fields."""

    return tuple(
        (value, value) for value in sorted({value for value in queryset if value})
    )


def _note_key(phase: str, question: str) -> str:
    """Encode a phase/question pair for use as a stable GET value."""

    return json.dumps([phase, question], separators=(",", ":"))


def _parse_note_key(value: str) -> tuple[str, str]:
    """Decode a phase/question GET value into filter parts."""

    try:
        phase, question = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return "", ""
    if not isinstance(phase, str) or not isinstance(question, str):
        return "", ""
    return phase, question


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
    filter_error = None

    def get_filterset_class(self) -> type[django_filters.FilterSet]:
        if self.filterset_class is None:
            raise ImproperlyConfigured("filterset_class must be set")
        return cast(type[django_filters.FilterSet], self.filterset_class)

    def get_filterset(self, *, queryset):
        filterset_class = self.get_filterset_class()
        try:
            # pylint: disable=not-callable
            filterset = filterset_class(
                data=self.request.GET or None,
                queryset=queryset,
            )
            # pylint: enable=not-callable
        except (DatabaseError, ImproperlyConfigured) as exc:
            self.filter_error = exc
            return None

        try:
            form = filterset.form
        except (DatabaseError, ImproperlyConfigured) as exc:
            self.filter_error = exc
        else:
            self._apply_widget_styles(form)
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

    def get_queryset(self):  # pragma: no cover - integration point for future views
        try:
            queryset = super().get_queryset()
        except (DatabaseError, ImproperlyConfigured) as exc:
            self.filter_error = exc
            self.filterset = None
            return self._empty_queryset()

        filterset = self.get_filterset(queryset=queryset)
        if filterset is None:
            self.filterset = None
            return self._safe_none(queryset)

        self.filterset = filterset
        try:
            return filterset.qs
        except (DatabaseError, ImproperlyConfigured) as exc:
            self.filter_error = exc
            return self._safe_none(queryset)

    def _safe_none(self, queryset):
        if hasattr(queryset, "none"):
            return queryset.none()
        return self._empty_queryset()

    def _empty_queryset(self):
        model = getattr(self, "model", None)
        if model is not None:
            return model._default_manager.none()
        return []

    def get_context_data(self, **kwargs):  # pragma: no cover - integration point
        kwargs.setdefault("filter", self.filterset)
        kwargs.setdefault("filter_error", self.filter_error)
        return super().get_context_data(**kwargs)


class CompletedTransectFilterSet(Select2FilterSetMixin, django_filters.FilterSet):
    """Filters for completed transects."""

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
        empty_label=None,
    )
    phase = django_filters.ChoiceFilter(
        method="filter_phase",
        label="Phase",
        choices=(),
        empty_label=None,
    )
    transect = django_filters.CharFilter(
        field_name="name",
        lookup_expr="icontains",
        label="Transect",
    )

    class Meta:
        model = CompletedTransect
        fields = []
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            state_values = CompletedTransect.objects.values_list("state", flat=True)
            choices = _state_choices(state_values)
        except (DatabaseError, ImproperlyConfigured):
            choices = _state_choices(())
        self.filters["state"].extra["choices"] = choices
        self.filters["state"].field.choices = choices
        self.filters["state"].field.widget.attrs.setdefault("class", "w3-select")

        try:
            phase_values = CompletedTransectInfo.objects.values_list(
                "pre_or_post", flat=True
            )
            phase_choices = _info_choices(phase_values, "All phases")
        except (DatabaseError, ImproperlyConfigured):
            phase_choices = _info_choices((), "All phases")
        self.filters["phase"].extra["choices"] = phase_choices
        self.filters["phase"].field.choices = phase_choices
        self.filters["phase"].field.widget.attrs.setdefault("class", "w3-select")

        self.note_filter_choices = self._build_note_filter_choices()
        self.note_filters = self._parse_note_filters()

    def filter_phase(self, queryset, name, value):
        """Filter transects by pre/post phase captured in transect details."""

        if not value:
            return queryset
        return queryset.filter(details__pre_or_post=value).distinct()

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        for note_filter in self.note_filters:
            criteria = {}
            phase = note_filter["phase"]
            question = note_filter["question"]
            responses = note_filter["responses"]

            if phase:
                criteria["details__pre_or_post"] = phase
            if question:
                criteria["details__question_text"] = question
            if responses:
                criteria["details__response__in"] = responses
            if criteria:
                queryset = queryset.filter(**criteria)
        if self.note_filters:
            queryset = queryset.distinct()
        return queryset

    @property
    def note_filter_form_rows(self):
        """Return rows for rendering the repeated transect-note filter UI."""

        rows = []
        for row in self.note_filters:
            rows.append(
                {
                    **row,
                    "response_choices": self.note_filter_choices["response_map"].get(
                        row["note_key"], ()
                    ),
                }
            )
        if not rows:
            rows.append(
                {
                    "index": 0,
                    "note_key": "",
                    "phase": "",
                    "question": "",
                    "responses": [],
                    "response_choices": (),
                }
            )
        return rows

    def _build_note_filter_choices(self):
        try:
            detail_values = CompletedTransectInfo.objects.values_list(
                "pre_or_post", "question_text", "response"
            )
        except (DatabaseError, ImproperlyConfigured):
            detail_values = ()

        note_pairs = {}
        response_map = {}
        for phase, question, response in detail_values:
            if not phase or not question:
                continue
            key = _note_key(phase, question)
            note_pairs[key] = f"{phase} / {question}"
            if response:
                response_map.setdefault(key, set()).add(response)

        return {
            "notes": (
                ("", "Any phase/question"),
                *tuple(
                    (key, label)
                    for key, label in sorted(note_pairs.items(), key=lambda item: item[1])
                ),
            ),
            "response_map": {
                key: tuple((value, value) for value in sorted(values))
                for key, values in response_map.items()
            },
        }

    def _parse_note_filters(self):
        if not self.data:
            return []

        rows = []
        for index in range(NOTE_FILTER_MAX_ROWS):
            prefix = f"{NOTE_FILTER_PREFIX}{index}_"
            note_key = self.data.get(f"{prefix}note", "").strip()
            phase, question = _parse_note_key(note_key)
            responses = self._getlist(f"{prefix}response")
            responses = [value.strip() for value in responses if value.strip()]

            if phase or question or responses:
                rows.append(
                    {
                        "index": index,
                        "note_key": note_key,
                        "phase": phase,
                        "question": question,
                        "responses": responses,
                    }
                )
        return rows

    def _getlist(self, key):
        if hasattr(self.data, "getlist"):
            return self.data.getlist(key)
        value = self.data.get(key, [])
        if isinstance(value, (list, tuple)):
            return value
        if value:
            return [value]
        return []


def _related_note_choices(info_model):
    try:
        detail_values = info_model.objects.values_list(
            "pre_or_post", "question_text", "response"
        )
    except (DatabaseError, ImproperlyConfigured):
        detail_values = ()

    note_pairs = {}
    response_map = {}
    for phase, question, response in detail_values:
        if not phase or not question:
            continue
        key = _note_key(phase, question)
        note_pairs[key] = f"{phase} / {question}"
        if response:
            response_map.setdefault(key, set()).add(response)
    return {
        "notes": (
            ("", "Any phase/question"),
            *tuple(
                (key, label)
                for key, label in sorted(note_pairs.items(), key=lambda item: item[1])
            ),
        ),
        "response_map": {
            key: tuple((value, value) for value in sorted(values))
            for key, values in response_map.items()
        },
    }


def _related_note_rows(note_filters, choices):
    rows = [
        {
            **row,
            "response_choices": choices["response_map"].get(row["note_key"], ()),
        }
        for row in note_filters
    ]
    return rows or [
        {
            "index": 0,
            "note_key": "",
            "phase": "",
            "question": "",
            "responses": [],
            "response_choices": (),
        }
    ]


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
        empty_label=None,
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
        try:
            state_values = CompletedOccurrence.objects.values_list(
                "state", flat=True
            )
            choices = _state_choices(state_values)
        except (DatabaseError, ImproperlyConfigured):
            choices = _state_choices(())
        self.filters["state"].extra["choices"] = choices
        self.filters["state"].field.choices = choices
        self.filters["state"].field.widget.attrs.setdefault("class", "w3-select")
        self.transect_note_filter_choices = _related_note_choices(
            CompletedTransectInfo
        )
        self.occurrence_note_filter_choices = _related_note_choices(
            CompletedOccurrenceInfo
        )
        self.transect_note_filters = self._parse_note_filters("transect_note_")
        self.occurrence_note_filters = self._parse_note_filters("occurrence_note_")

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        queryset = self._apply_note_filters(
            queryset, self.transect_note_filters, "transect__details"
        )
        queryset = self._apply_note_filters(
            queryset, self.occurrence_note_filters, "details"
        )
        if self.transect_note_filters or self.occurrence_note_filters:
            queryset = queryset.distinct()
        return queryset

    @property
    def transect_note_filter_form_rows(self):
        return _related_note_rows(
            self.transect_note_filters, self.transect_note_filter_choices
        )

    @property
    def occurrence_note_filter_form_rows(self):
        return _related_note_rows(
            self.occurrence_note_filters, self.occurrence_note_filter_choices
        )

    @staticmethod
    def _apply_note_filters(queryset, note_filters, relation):
        for note_filter in note_filters:
            criteria = {}
            if note_filter["phase"]:
                criteria[f"{relation}__pre_or_post"] = note_filter["phase"]
            if note_filter["question"]:
                criteria[f"{relation}__question_text"] = note_filter["question"]
            if note_filter["responses"]:
                criteria[f"{relation}__response__in"] = note_filter["responses"]
            if criteria:
                queryset = queryset.filter(**criteria)
        return queryset

    def _parse_note_filters(self, prefix):
        if not self.data:
            return []
        rows = []
        for index in range(NOTE_FILTER_MAX_ROWS):
            row_prefix = f"{prefix}{index}_"
            note_key = self.data.get(f"{row_prefix}note", "").strip()
            phase, question = _parse_note_key(note_key)
            responses = [
                value.strip()
                for value in self._getlist(f"{row_prefix}response")
                if value.strip()
            ]
            if phase or question or responses:
                rows.append(
                    {
                        "index": index,
                        "note_key": note_key,
                        "phase": phase,
                        "question": question,
                        "responses": responses,
                    }
                )
        return rows

    def _getlist(self, key):
        if hasattr(self.data, "getlist"):
            return self.data.getlist(key)
        value = self.data.get(key, [])
        if isinstance(value, (list, tuple)):
            return value
        return [value] if value else []


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

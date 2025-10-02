"""List view archetypes for the Bones application."""
from __future__ import annotations

from typing import Iterable, Sequence

from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView

from ..filters import (
    CompletedOccurrenceFilterSet,
    CompletedTransectFilterSet,
    CompletedWorkflowFilterSet,
    DataLogFileFilterSet,
    DataTypeFilterSet,
    DataTypeOptionFilterSet,
    FilteredListViewMixin,
    ProjectConfigFilterSet,
    QuestionFilterSet,
    TemplateTransectFilterSet,
)
from ..models import (
    CompletedOccurrence,
    CompletedTransect,
    CompletedWorkflow,
    DataLogFile,
    DataType,
    DataTypeOption,
    ProjectConfig,
    Question,
    TemplateTransect,
)
from .mixins import BonesAuthMixin


EM_DASH = "\u2014"


def safe_reverse(name: str | None, *, kwargs: dict[str, object] | None = None) -> str | None:
    """Resolve a URL name when available, otherwise return ``None``.

    Accepts both fully-qualified ``bones:`` names and shorthand references to
    keep legacy list views working while URLs are consolidated.
    """

    if not name:
        return None

    candidate_names = [name]
    if not name.startswith("bones:"):
        candidate_names.append(f"bones:{name}")

    for candidate in candidate_names:
        try:
            if kwargs:
                return reverse(candidate, kwargs=kwargs)
            return reverse(candidate)
        except NoReverseMatch:
            continue
    return None


def format_datetime(value):
    """Return a localized datetime string or an em dash placeholder."""

    if not value:
        return EM_DASH

    if timezone.is_aware(value):
        value = timezone.localtime(value)

    return date_format(value, "DATETIME_FORMAT")


def format_boolean(value):
    """Return a translated yes/no string or an em dash."""

    if value is None:
        return EM_DASH
    return _("Yes") if value else _("No")


def format_value(value):
    """Coerce falsey values into an em dash placeholder."""

    if value in (None, ""):
        return EM_DASH
    return value


class BonesListView(BonesAuthMixin, FilteredListViewMixin, ListView):
    """Base class for list archetypes with filter + table support."""

    paginate_by = 25
    page_icon: str = ""
    page_title: str = ""
    intro_text: str = ""
    table_caption: str = ""
    detail_route_name: str | None = None
    history_route_name: str | None = None

    def get_table_headers(self) -> Sequence[dict[str, str]]:  # pragma: no cover - implemented by subclasses
        raise NotImplementedError

    def get_table_rows(self, object_list: Iterable[object]):  # pragma: no cover - implemented by subclasses
        raise NotImplementedError

    def get_table_caption(self) -> str:
        return self.table_caption or self.page_title

    def get_detail_url_kwargs(self, obj) -> dict[str, object] | None:
        return {"pk": getattr(obj, "pk", None)}

    def get_history_url_kwargs(self, obj) -> dict[str, object] | None:
        return self.get_detail_url_kwargs(obj)

    def get_detail_url(self, obj) -> str | None:
        if not self.detail_route_name:
            return None
        kwargs = self.get_detail_url_kwargs(obj)
        if not kwargs or any(value is None for value in kwargs.values()):
            return safe_reverse(self.detail_route_name)
        return safe_reverse(self.detail_route_name, kwargs=kwargs)

    def get_history_url(self, obj) -> str | None:
        if not self.history_route_name:
            return None
        kwargs = self.get_history_url_kwargs(obj)
        if not kwargs:
            return safe_reverse(self.history_route_name)
        if any(value is None for value in kwargs.values()):
            return safe_reverse(self.history_route_name)
        return safe_reverse(self.history_route_name, kwargs=kwargs)

    def get_action_buttons(self, obj) -> str:
        detail_url = self.get_detail_url(obj)
        history_url = self.get_history_url(obj)
        buttons = [
            self._render_action_button(detail_url, _("View"), "fa-regular fa-eye"),
            self._render_action_button(history_url, _("History"), "fa-solid fa-clock-rotate-left"),
        ]
        return format_html(
            '<div class="w3-bar w3-small w3-nowrap">{}</div>',
            format_html_join("", "{}", ((button,) for button in buttons)),
        )

    def get_permission_required(self):  # type: ignore[override]
        perms = super().get_permission_required()
        if perms:
            return perms
        if getattr(self, "model", None):
            meta = self.model._meta  # type: ignore[attr-defined]
            return (f"{meta.app_label}.view_{meta.model_name}",)
        return ()

    @staticmethod
    def _render_action_button(url: str | None, label: str, icon: str) -> str:
        if url:
            return format_html(
                '<a href="{0}" class="w3-button w3-round w3-border w3-white w3-margin-right">'
                '<span class="fa-fw {1}" aria-hidden="true"></span>'
                '<span class="w3-margin-left">{2}</span>'
                '</a>',
                url,
                icon,
                label,
            )
        return format_html(
            '<span class="w3-button w3-round w3-border w3-light-grey w3-margin-right w3-disabled"'
            ' aria-disabled="true">'
            '<span class="fa-fw {0}" aria-hidden="true"></span>'
            '<span class="w3-margin-left">{1}</span>'
            '</span>',
            icon,
            label,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        object_list = context.get(self.context_object_name) or context.get("object_list", [])
        paginator = context.get("paginator")

        context.update(
            {
                "page_title": self.page_title,
                "page_icon": self.page_icon,
                "intro_text": self.intro_text,
                "table_headers": self.get_table_headers(),
                "table_rows": self.get_table_rows(object_list),
                "table_caption": self.get_table_caption(),
                "result_count": paginator.count if paginator else len(object_list),
                "filter_active": self._filter_is_active(),
                "filter_querystring": self._build_filter_querystring(),
            }
        )
        return context

    def _filter_is_active(self) -> bool:
        params = self.request.GET.copy()
        params.pop("page", None)
        return bool(params)

    def _build_filter_querystring(self) -> str:
        params = self.request.GET.copy()
        params.pop("page", None)
        encoded = params.urlencode()
        if not encoded:
            return ""
        return f"&{encoded}"


class CompletedTransectListView(BonesListView):
    """List completed transects with filter support."""

    model = CompletedTransect
    template_name = "bones/completed_transect_list.html"
    context_object_name = "transects"
    filterset_class = CompletedTransectFilterSet
    page_icon = "fa-solid fa-route"
    page_title = "Completed transects"
    intro_text = _(
        "Review completed transects, their templates, and the number of occurrences gathered in the field."
    )
    detail_route_name = "transects:detail"
    history_route_name = "history:transects"

    def get_queryset(self):
        self.queryset = (
            CompletedTransect.objects.select_related("transect_template")
            .with_occurrence_counts()
            .order_by("-start_time")
        )
        return super().get_queryset()

    def get_table_headers(self):
        return [
            {"label": _("Transect")},
            {"label": _("Template")},
            {"label": _("Started")},
            {"label": _("Ended")},
            {"label": _("State")},
            {"label": _("Occurrences"), "classes": "w3-center"},
            {"label": _("Actions"), "classes": "w3-center"},
        ]

    def get_table_rows(self, transects: Iterable[CompletedTransect]):
        rows = []
        for transect in transects:
            occurrence_count = getattr(transect, "occurrence_count", None)
            if occurrence_count is None and hasattr(transect, "occurrences"):
                occurrence_count = transect.occurrences.count()
            occurrence_count = occurrence_count or 0
            rows.append(
                [
                    {"value": transect.name, "url": self.get_detail_url(transect)},
                    {"value": format_value(getattr(transect.transect_template, "name", transect.transect_template))},
                    {"value": format_datetime(transect.start_time)},
                    {"value": format_datetime(transect.end_time)},
                    {"value": format_value(transect.state)},
                    {"value": occurrence_count, "classes": "w3-center"},
                    {"value": self.get_action_buttons(transect), "classes": "w3-center"},
                ]
            )
        return rows


class CompletedOccurrenceListView(BonesListView):
    """List completed occurrences with filter support."""

    model = CompletedOccurrence
    template_name = "bones/completed_occurrence_list.html"
    context_object_name = "occurrences"
    filterset_class = CompletedOccurrenceFilterSet
    page_icon = "fa-solid fa-frog"
    page_title = "Completed occurrences"
    intro_text = _(
        "Inspect recorded occurrences, their associated transects, and captured responses."
    )
    detail_route_name = "occurrences:detail"
    history_route_name = "history:occurrences"

    def get_queryset(self):
        self.queryset = (
            CompletedOccurrence.objects.select_related("transect", "transect__transect_template")
            .with_response_counts()
            .order_by("-recording_start_time")
        )
        return super().get_queryset()

    def get_table_headers(self):
        return [
            {"label": _("Occurrence")},
            {"label": _("Transect")},
            {"label": _("Started")},
            {"label": _("Ended")},
            {"label": _("State")},
            {"label": _("Responses"), "classes": "w3-center"},
            {"label": _("Actions"), "classes": "w3-center"},
        ]

    def get_table_rows(self, occurrences: Iterable[CompletedOccurrence]):
        rows = []
        for occurrence in occurrences:
            response_count = getattr(occurrence, "response_count", None)
            if response_count is None and hasattr(occurrence, "responses"):
                response_count = occurrence.responses.count()
            response_count = response_count or 0
            transect = occurrence.transect
            transect_label = transect.name if transect else EM_DASH
            if transect and transect.transect_template:
                transect_label = f"{transect.name} ({transect.transect_template})"
            rows.append(
                [
                    {
                        "value": _( "Occurrence {number}").format(number=occurrence.occurrence_number),
                        "url": self.get_detail_url(occurrence),
                    },
                    {"value": transect_label},
                    {"value": format_datetime(occurrence.recording_start_time)},
                    {"value": format_datetime(occurrence.recording_end_time)},
                    {"value": format_value(occurrence.state)},
                    {"value": response_count, "classes": "w3-center"},
                    {"value": self.get_action_buttons(occurrence), "classes": "w3-center"},
                ]
            )
        return rows


class CompletedWorkflowListView(BonesListView):
    """List completed workflows with filter support."""

    model = CompletedWorkflow
    template_name = "bones/completed_workflow_list.html"
    context_object_name = "workflows"
    filterset_class = CompletedWorkflowFilterSet
    page_icon = "fa-solid fa-diagram-project"
    page_title = "Completed workflows"
    intro_text = _(
        "Track workflow progress, assigned users, and originating occurrences for QA reviews."
    )
    detail_route_name = "workflows:detail"
    history_route_name = "history:workflows"

    def get_queryset(self):
        self.queryset = (
            CompletedWorkflow.objects.select_related(
                "occurrence",
                "occurrence__transect",
                "template_workflow",
            )
            .with_templates()
            .order_by("-instance_number")
        )
        return super().get_queryset()

    def get_table_headers(self):
        return [
            {"label": _("Template workflow")},
            {"label": _("Occurrence")},
            {"label": _("Completed by")},
            {"label": _("Instance")},
            {"label": _("Actions"), "classes": "w3-center"},
        ]

    def get_table_rows(self, workflows: Iterable[CompletedWorkflow]):
        rows = []
        for workflow in workflows:
            occurrence = workflow.occurrence
            if occurrence and occurrence.transect:
                occurrence_label = _(
                    "Occurrence {number} – {transect}"
                ).format(number=occurrence.occurrence_number, transect=occurrence.transect)
            elif occurrence:
                occurrence_label = _(
                    "Occurrence {number}"
                ).format(number=occurrence.occurrence_number)
            else:
                occurrence_label = EM_DASH
            rows.append(
                [
                    {
                        "value": format_value(
                            getattr(workflow.template_workflow, "name", workflow.template_workflow)
                        ),
                        "url": self.get_detail_url(workflow),
                    },
                    {"value": occurrence_label},
                    {"value": format_value(workflow.completed_by)},
                    {"value": workflow.instance_number},
                    {"value": self.get_action_buttons(workflow), "classes": "w3-center"},
                ]
            )
        return rows


class TemplateTransectListView(BonesListView):
    """List template transects."""

    model = TemplateTransect
    template_name = "bones/template_transect_list.html"
    context_object_name = "template_transects"
    filterset_class = TemplateTransectFilterSet
    page_icon = "fa-solid fa-layer-group"
    page_title = "Template transects"
    intro_text = _(
        "Browse scheduled transect templates and confirm coverage ahead of deployments."
    )
    detail_route_name = "templates:detail"
    history_route_name = "history:templates"

    def get_queryset(self):
        self.queryset = TemplateTransect.objects.order_by("-scheduled_time")
        return super().get_queryset()

    def get_table_headers(self):
        return [
            {"label": _("Template")},
            {"label": _("Scheduled time")},
            {"label": _("Distance (km)")},
            {"label": _("Open ended")},
            {"label": _("Dynamic")},
            {"label": _("Actions"), "classes": "w3-center"},
        ]

    def get_table_rows(self, templates: Iterable[TemplateTransect]):
        rows = []
        for template in templates:
            rows.append(
                [
                    {"value": template.name, "url": self.get_detail_url(template)},
                    {"value": format_datetime(template.scheduled_time)},
                    {"value": format_value(template.distance_km)},
                    {"value": format_boolean(template.open_ended)},
                    {"value": format_boolean(template.created_dynamically)},
                    {"value": self.get_action_buttons(template), "classes": "w3-center"},
                ]
            )
        return rows


class QuestionListView(BonesListView):
    """List question definitions."""

    model = Question
    template_name = "bones/question_list.html"
    context_object_name = "questions"
    filterset_class = QuestionFilterSet
    page_icon = "fa-solid fa-circle-question"
    page_title = "Questions"
    intro_text = _(
        "Audit template questions, their workflows, and expected data types."
    )
    detail_route_name = "templates:question_detail"
    history_route_name = "history:questions"

    def get_queryset(self):
        self.queryset = Question.objects.with_related().order_by("prompt")
        return super().get_queryset()

    def get_table_headers(self):
        return [
            {"label": _("Prompt")},
            {"label": _("Workflow")},
            {"label": _("Data type")},
            {"label": _("Data type name")},
            {"label": _("Actions"), "classes": "w3-center"},
        ]

    def get_table_rows(self, questions: Iterable[Question]):
        rows = []
        for question in questions:
            rows.append(
                [
                    {"value": format_value(question.prompt), "url": self.get_detail_url(question)},
                    {"value": format_value(getattr(question.workflow, "name", question.workflow))},
                    {"value": format_value(getattr(question.data_type, "name", question.data_type))},
                    {"value": format_value(question.data_type_name)},
                    {"value": self.get_action_buttons(question), "classes": "w3-center"},
                ]
            )
        return rows


class DataTypeListView(BonesListView):
    """List data types."""

    model = DataType
    template_name = "bones/data_type_list.html"
    context_object_name = "data_types"
    filterset_class = DataTypeFilterSet
    page_icon = "fa-solid fa-database"
    page_title = "Data types"
    intro_text = _(
        "Review data types that power questions and reference options."
    )
    detail_route_name = "reference:data_type_detail"
    history_route_name = "history:data_types"

    def get_queryset(self):
        self.queryset = DataType.objects.with_options().order_by("name")
        return super().get_queryset()

    def get_table_headers(self):
        return [
            {"label": _("Data type")},
            {"label": _("Identifier")},
            {"label": _("User data type")},
            {"label": _("Options"), "classes": "w3-center"},
            {"label": _("Actions"), "classes": "w3-center"},
        ]

    def get_table_rows(self, data_types: Iterable[DataType]):
        rows = []
        for data_type in data_types:
            options = data_type.options.all() if hasattr(data_type, "options") else []
            rows.append(
                [
                    {"value": data_type.name, "url": self.get_detail_url(data_type)},
                    {"value": data_type.id},
                    {"value": format_boolean(data_type.is_user_data_type)},
                    {"value": len(list(options)), "classes": "w3-center"},
                    {"value": self.get_action_buttons(data_type), "classes": "w3-center"},
                ]
            )
        return rows


class DataTypeOptionListView(BonesListView):
    """List data type options."""

    model = DataTypeOption
    template_name = "bones/data_type_option_list.html"
    context_object_name = "data_type_options"
    filterset_class = DataTypeOptionFilterSet
    page_icon = "fa-solid fa-list-check"
    page_title = "Data type options"
    intro_text = _(
        "Inspect selectable values associated with each data type."
    )
    detail_route_name = "reference:data_type_option_detail"
    history_route_name = "history:data_type_options"

    def get_queryset(self):
        self.queryset = DataTypeOption.objects.select_related("data_type").order_by("data_type__name", "code")
        return super().get_queryset()

    def get_table_headers(self):
        return [
            {"label": _("Data type")},
            {"label": _("Code")},
            {"label": _("Text")},
            {"label": _("Actions"), "classes": "w3-center"},
        ]

    def get_table_rows(self, options: Iterable[DataTypeOption]):
        rows = []
        for option in options:
            rows.append(
                [
                    {
                        "value": format_value(getattr(option.data_type, "name", option.data_type)),
                        "url": self.get_detail_url(option),
                    },
                    {"value": option.code},
                    {"value": format_value(option.text)},
                    {"value": self.get_action_buttons(option), "classes": "w3-center"},
                ]
            )
        return rows


class ProjectConfigListView(BonesListView):
    """List project configuration files."""

    model = ProjectConfig
    template_name = "bones/project_config_list.html"
    context_object_name = "project_configs"
    filterset_class = ProjectConfigFilterSet
    page_icon = "fa-solid fa-gear"
    page_title = "Project configuration"
    intro_text = _(
        "Audit published project configuration bundles and deployment dates."
    )
    detail_route_name = "reference:project_config_detail"
    history_route_name = "history:project_configs"

    def get_queryset(self):
        self.queryset = ProjectConfig.objects.order_by("-publish_date")
        return super().get_queryset()

    def get_table_headers(self):
        return [
            {"label": _("Project")},
            {"label": _("Publish date")},
            {"label": _("Config folder")},
            {"label": _("Actions"), "classes": "w3-center"},
        ]

    def get_table_rows(self, configs: Iterable[ProjectConfig]):
        rows = []
        for config in configs:
            rows.append(
                [
                    {"value": config.project, "url": self.get_detail_url(config)},
                    {"value": format_datetime(config.publish_date)},
                    {"value": format_value(config.config_folder)},
                    {"value": self.get_action_buttons(config), "classes": "w3-center"},
                ]
            )
        return rows


class DataLogFileListView(BonesListView):
    """List uploaded data log files."""

    model = DataLogFile
    template_name = "bones/data_log_file_list.html"
    context_object_name = "data_log_files"
    filterset_class = DataLogFileFilterSet
    page_icon = "fa-solid fa-file-arrow-down"
    page_title = "Data log files"
    intro_text = _(
        "Review uploaded log files before associating them with transects."
    )
    detail_route_name = "logs:detail"
    history_route_name = "history:data_logs"

    def get_queryset(self):
        self.queryset = DataLogFile.objects.order_by("-upload_date")
        return super().get_queryset()

    def get_table_headers(self):
        return [
            {"label": _("Log file")},
            {"label": _("Uploaded")},
            {"label": _("Uploaded by")},
            {"label": _("Actions"), "classes": "w3-center"},
        ]

    def get_table_rows(self, logs: Iterable[DataLogFile]):
        rows = []
        for log in logs:
            rows.append(
                [
                    {"value": format_value(str(log)), "url": self.get_detail_url(log)},
                    {"value": format_datetime(log.upload_date)},
                    {"value": format_value(log.uploaded_by)},
                    {"value": self.get_action_buttons(log), "classes": "w3-center"},
                ]
            )
        return rows

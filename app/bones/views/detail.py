"""Detail view archetypes for the Bones application."""
from __future__ import annotations

from typing import Any, Iterable, List, Mapping

from django.contrib import messages
from django import forms
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.views.generic import UpdateView

from django_select2.forms import Select2Widget

from ..forms import DataLogFileForm, DataTypeForm, ProjectConfigForm, QuestionForm
from ..models import DataLogFile, DataType, ProjectConfig, Question
from .mixins import BonesAuthMixin

EM_DASH = "\u2014"


def safe_reverse(name: str | None, *, kwargs: Mapping[str, Any] | None = None) -> str | None:
    """Resolve a URL name if it exists, otherwise return ``None``."""

    if not name:
        return None

    try:
        if kwargs:
            return reverse(name, kwargs=kwargs)
        return reverse(name)
    except NoReverseMatch:
        return None


def format_value(value: Any) -> str:
    """Render scalar values with an em dash fallback."""

    if value in (None, ""):
        return EM_DASH
    return str(value)


def format_datetime(value) -> str:
    """Render datetimes in the active locale."""

    if not value:
        return EM_DASH

    if timezone.is_aware(value):
        value = timezone.localtime(value)

    return date_format(value, "DATETIME_FORMAT")


def format_boolean(value: bool | None) -> str:
    """Render boolean values with translated labels."""

    if value is None:
        return EM_DASH
    return _("Yes") if value else _("No")


def format_pre(value: Any) -> str:
    """Render multi-line text in a styled block."""

    if value in (None, ""):
        return EM_DASH
    return format_html('<pre class="w3-code w3-small w3-round w3-light-grey">{}</pre>', value)


class BonesDetailView(BonesAuthMixin, UpdateView):
    """Base class for detail-oriented pages with inline editing."""

    page_icon: str = ""
    page_title_template: str = "{object}"  # Use the object's ``__str__`` by default.
    intro_text: str = ""
    submit_label: str = _("Save changes")
    success_message: str = _("Changes saved successfully.")
    list_route_name: str | None = None
    history_route_name: str | None = None
    breadcrumb_list_label: str = ""

    def get_page_title(self) -> str:
        return self.page_title_template.format(object=self.object)

    def get_intro_text(self) -> str:
        return self.intro_text

    def get_submit_label(self) -> str:
        return self.submit_label

    def get_success_url(self) -> str:
        return self.request.get_full_path()

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.success_message:
            messages.success(self.request, self.success_message)
        return response

    # Ensure W3.CSS styling is applied to widgets, while preserving select2 hooks.
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            widget = field.widget
            classes: List[str]
            if isinstance(widget, Select2Widget):
                classes = ["w3-select", "w3-border", "w3-round"]
            elif getattr(widget, "input_type", None) == "checkbox":
                classes = ["w3-check"]
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                classes = ["w3-select", "w3-border", "w3-round"]
            else:
                classes = ["w3-input", "w3-border", "w3-round"]
            existing = widget.attrs.get("class", "").split()
            for css_class in classes:
                if css_class not in existing:
                    existing.append(css_class)
            widget.attrs["class"] = " ".join(existing).strip()
        return form

    def get_permission_required(self):  # type: ignore[override]
        perms = super().get_permission_required()
        if perms:
            return perms
        if getattr(self, "model", None):
            meta = self.model._meta  # type: ignore[attr-defined]
            return (f"{meta.app_label}.change_{meta.model_name}",)
        return ()

    def get_detail_sections(self) -> Iterable[Mapping[str, Any]]:
        """Return metadata sections for the current object."""

        return []

    def get_extra_actions(self) -> Iterable[Mapping[str, Any]]:
        """Return additional action buttons beyond list/history."""

        return []

    def get_list_url(self) -> str | None:
        return safe_reverse(self.list_route_name)

    def get_history_url(self) -> str | None:
        return safe_reverse(self.history_route_name, kwargs=self.get_history_kwargs())

    def get_history_kwargs(self) -> Mapping[str, Any] | None:
        if not self.object:
            return None
        return {"pk": getattr(self.object, "pk", None)}

    def get_breadcrumbs(self) -> list[dict[str, str | None]]:
        breadcrumbs: list[dict[str, str | None]] = [
            {"label": _("Dashboard"), "url": safe_reverse("dashboard")},
        ]
        list_url = self.get_list_url()
        if self.breadcrumb_list_label:
            breadcrumbs.append({"label": self.breadcrumb_list_label, "url": list_url})
        elif list_url:
            breadcrumbs.append({"label": list_url, "url": list_url})
        breadcrumbs.append({"label": self.get_page_title(), "url": None})
        return breadcrumbs

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        form = context.get("form")
        if form is None:
            form = self.get_form()
            context["form"] = form
        context.update(
            {
                "page_title": self.get_page_title(),
                "page_icon": self.page_icon,
                "intro_text": self.get_intro_text(),
                "detail_sections": list(self.get_detail_sections()),
                "list_url": self.get_list_url(),
                "history_url": self.get_history_url(),
                "extra_actions": list(self.get_extra_actions()),
                "submit_label": self.get_submit_label(),
                "form_enctype": "multipart/form-data" if form.is_multipart() else None,
                "breadcrumbs": self.get_breadcrumbs(),
            }
        )
        return context


class DataLogFileDetailView(BonesDetailView):
    """Display and edit uploaded data log files."""

    model = DataLogFile
    form_class = DataLogFileForm
    template_name = "bones/data_log_file_detail.html"
    page_icon = "fa-solid fa-file-arrow-down"
    page_title_template = _("Data log file {object}")
    intro_text = _("Review metadata and correct upload information for this data log file.")
    success_message = _("Data log file updated successfully.")
    list_route_name = "logs:list"
    breadcrumb_list_label = _("Data logs")

    def get_detail_sections(self) -> Iterable[Mapping[str, Any]]:
        obj = self.object
        return [
            {
                "title": _("File metadata"),
                "icon": "fa-solid fa-circle-info",
                "items": [
                    {"label": _("Identifier"), "value": format_value(obj.pk)},
                    {"label": _("Uploaded"), "value": format_datetime(obj.upload_date)},
                    {"label": _("Uploaded by"), "value": format_value(obj.uploaded_by)},
                ],
            },
            {
                "title": _("Contents"),
                "icon": "fa-solid fa-code",
                "items": [
                    {"label": _("Payload"), "value": format_pre(obj.contents)},
                ],
            },
        ]


class DataTypeDetailView(BonesDetailView):
    """Display and edit reference data type definitions."""

    model = DataType
    form_class = DataTypeForm
    template_name = "bones/data_type_detail.html"
    page_icon = "fa-solid fa-database"
    page_title_template = _("Data type {object}")
    intro_text = _("Adjust the configuration of this reference data type.")
    success_message = _("Data type updated successfully.")
    list_route_name = "reference:data_types"
    breadcrumb_list_label = _("Data types")

    def get_detail_sections(self) -> Iterable[Mapping[str, Any]]:
        obj = self.object
        return [
            {
                "title": _("Attributes"),
                "icon": "fa-solid fa-list",
                "items": [
                    {"label": _("Identifier"), "value": format_value(obj.pk)},
                    {"label": _("Name"), "value": format_value(obj.name)},
                    {"label": _("User data type"), "value": format_boolean(obj.is_user_data_type)},
                    {"label": _("C# type"), "value": format_value(obj.csharp_type)},
                ],
            },
            {
                "title": _("Usage"),
                "icon": "fa-solid fa-chart-network",
                "items": [
                    {
                        "label": _("Questions using this type"),
                        "value": format_value(obj.questions.count()),
                    },
                ],
            },
        ]


class ProjectConfigDetailView(BonesDetailView):
    """Display and edit project configuration records."""

    model = ProjectConfig
    form_class = ProjectConfigForm
    template_name = "bones/project_config_detail.html"
    page_icon = "fa-solid fa-gear"
    page_title_template = _("Project config {object}")
    intro_text = _("Manage publish metadata and configuration payloads for this project.")
    success_message = _("Project configuration updated successfully.")
    list_route_name = "reference:project_config"
    breadcrumb_list_label = _("Project configs")

    def get_detail_sections(self) -> Iterable[Mapping[str, Any]]:
        obj = self.object
        return [
            {
                "title": _("Metadata"),
                "icon": "fa-solid fa-circle-info",
                "items": [
                    {"label": _("Identifier"), "value": format_value(obj.pk)},
                    {"label": _("Publish date"), "value": format_datetime(obj.publish_date)},
                    {"label": _("Project"), "value": format_value(obj.project)},
                ],
            },
            {
                "title": _("Configuration payloads"),
                "icon": "fa-solid fa-file-code",
                "items": [
                    {"label": _("Config folder"), "value": format_value(obj.config_folder)},
                    {"label": _("Config file"), "value": format_pre(obj.config_file)},
                    {"label": _("Image"), "value": format_pre(obj.image)},
                    {"label": _("Transects file"), "value": format_pre(obj.transects_file)},
                ],
            },
        ]


class QuestionDetailView(BonesDetailView):
    """Display and edit survey question definitions."""

    model = Question
    form_class = QuestionForm
    template_name = "bones/question_detail.html"
    page_icon = "fa-solid fa-circle-question"
    page_title_template = _("Question {object}")
    intro_text = _("Update the prompt, data type, or workflow assignment for this question.")
    success_message = _("Question updated successfully.")
    list_route_name = "templates:questions"
    breadcrumb_list_label = _("Questions")

    def get_extra_actions(self) -> Iterable[Mapping[str, Any]]:
        obj = self.object
        actions: list[Mapping[str, Any]] = []
        if obj.data_type_id:
            actions.append(
                {
                    "label": _("View data type"),
                    "url": safe_reverse("reference:data_type_detail", kwargs={"pk": obj.data_type_id}),
                    "icon": "fa-solid fa-database",
                }
            )
        if obj.workflow_id:
            actions.append(
                {
                    "label": _("Workflow detail coming soon"),
                    "url": None,
                    "icon": "fa-solid fa-diagram-project",
                }
            )
        return actions

    def get_detail_sections(self) -> Iterable[Mapping[str, Any]]:
        obj = self.object
        return [
            {
                "title": _("Question metadata"),
                "icon": "fa-solid fa-circle-info",
                "items": [
                    {"label": _("Identifier"), "value": format_value(obj.pk)},
                    {"label": _("Prompt"), "value": format_pre(obj.prompt)},
                    {"label": _("Data type"), "value": format_value(obj.data_type)},
                    {"label": _("Workflow"), "value": format_value(obj.workflow)},
                ],
            },
            {
                "title": _("Data type mapping"),
                "icon": "fa-solid fa-code-branch",
                "items": [
                    {"label": _("Data type name"), "value": format_value(obj.data_type_name)},
                ],
            },
        ]

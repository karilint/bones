"""Forms for the bones application with select2 widgets.

These forms expose the reorganized models introduced in the refactor and
apply select2 widgets to relationship fields so large datasets remain
searchable from the UI, matching the Django app guidelines.
"""
from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _
from django_select2.forms import ModelSelect2Widget

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

SELECT2_BASE_ATTRS = {
    "style": "width: 100%",
    "data-minimum-input-length": 0,
}


def select2_widget_attrs(placeholder: str) -> dict[str, str]:
    """Return base select2 attributes with a context-specific placeholder."""

    return {
        **SELECT2_BASE_ATTRS,
        "data-placeholder": placeholder,
    }


class TemplateTransectSelect2Widget(ModelSelect2Widget):
    """Reusable widget for template transect lookups."""

    model = TemplateTransect
    search_fields = ["name__icontains", "id__icontains"]


class CompletedTransectSelect2Widget(ModelSelect2Widget):
    """Reusable widget for completed transect lookups."""

    model = CompletedTransect
    search_fields = ["name__icontains", "uid__icontains"]


class CompletedOccurrenceSelect2Widget(ModelSelect2Widget):
    """Reusable widget for completed occurrence lookups."""

    model = CompletedOccurrence
    search_fields = [
        "transect__name__icontains",
        "transect__uid__icontains",
        "occurrence_number__icontains",
    ]


class TemplateWorkflowSelect2Widget(ModelSelect2Widget):
    """Reusable widget for template workflow lookups."""

    model = TemplateWorkflow
    search_fields = ["name__icontains", "id__icontains"]


class DataTypeSelect2Widget(ModelSelect2Widget):
    """Reusable widget for data type lookups."""

    model = DataType
    search_fields = ["name__icontains", "id__icontains"]


class DataLogFileSelect2Widget(ModelSelect2Widget):
    """Reusable widget for data log file lookups."""

    model = DataLogFile
    search_fields = ["id__icontains", "uploaded_by__icontains"]


class Select2ModelFormMixin:
    """Mixin that ensures select2 widgets include consistent styling."""

    select2_fields: tuple[str, ...] = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.select2_fields:
            field = self.fields.get(field_name)
            if field and isinstance(field.widget, ModelSelect2Widget):
                placeholder = field.widget.attrs.get(
                    "data-placeholder", field.label or _("Select an option")
                )
                field.widget.attrs = {
                    **select2_widget_attrs(placeholder),
                    **field.widget.attrs,
                }


class CompletedTransectForm(Select2ModelFormMixin, forms.ModelForm):
    """ModelForm for completed transects."""

    select2_fields = ("transect_template",)

    class Meta:
        model = CompletedTransect
        fields = [
            "name",
            "transect_template",
            "start_time",
            "turn_time",
            "end_time",
            "lat_from",
            "long_from",
            "lat_turn",
            "long_turn",
            "lat_to",
            "long_to",
            "distance_km",
            "angle_degrees",
            "state",
            "paused_for_minutes",
        ]
        widgets = {
            "transect_template": TemplateTransectSelect2Widget(
                attrs=select2_widget_attrs(_("Search template transects"))
            ),
            "start_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "turn_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class CompletedOccurrenceForm(Select2ModelFormMixin, forms.ModelForm):
    """ModelForm for completed occurrences."""

    select2_fields = ("transect",)

    class Meta:
        model = CompletedOccurrence
        fields = [
            "transect",
            "occurrence_number",
            "recording_start_time",
            "recording_end_time",
            "lat",
            "long",
            "note",
            "state",
        ]
        widgets = {
            "transect": CompletedTransectSelect2Widget(
                attrs=select2_widget_attrs(_("Search completed transects"))
            ),
            "recording_start_time": forms.DateTimeInput(
                attrs={"type": "datetime-local"}
            ),
            "recording_end_time": forms.DateTimeInput(
                attrs={"type": "datetime-local"}
            ),
        }


class CompletedWorkflowForm(Select2ModelFormMixin, forms.ModelForm):
    """ModelForm for completed workflows."""

    select2_fields = ("occurrence", "template_workflow")

    class Meta:
        model = CompletedWorkflow
        fields = [
            "occurrence",
            "template_workflow",
            "instance_number",
            "completed_by",
        ]
        widgets = {
            "occurrence": CompletedOccurrenceSelect2Widget(
                attrs=select2_widget_attrs(_("Search occurrences"))
            ),
            "template_workflow": TemplateWorkflowSelect2Widget(
                attrs=select2_widget_attrs(_("Search template workflows"))
            ),
        }


class TemplateTransectForm(forms.ModelForm):
    """ModelForm for template transects."""

    class Meta:
        model = TemplateTransect
        fields = [
            "name",
            "scheduled_time",
            "lat_from",
            "long_from",
            "lat_to",
            "long_to",
            "open_ended",
            "distance_km",
            "angle_degrees",
            "note",
            "created_dynamically",
        ]
        widgets = {
            "scheduled_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class TemplateWorkflowForm(forms.ModelForm):
    """ModelForm for template workflows."""

    class Meta:
        model = TemplateWorkflow
        fields = ["name", "date_added", "added_by"]
        widgets = {
            "date_added": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class QuestionForm(Select2ModelFormMixin, forms.ModelForm):
    """ModelForm for question definitions."""

    select2_fields = ("data_type", "workflow")

    class Meta:
        model = Question
        fields = ["prompt", "data_type", "data_type_name", "workflow"]
        widgets = {
            "data_type": DataTypeSelect2Widget(
                attrs=select2_widget_attrs(_("Search data types"))
            ),
            "workflow": TemplateWorkflowSelect2Widget(
                attrs=select2_widget_attrs(_("Search template workflows"))
            ),
        }


class DataTypeForm(forms.ModelForm):
    """ModelForm for data types."""

    class Meta:
        model = DataType
        fields = ["name", "is_user_data_type", "csharp_type"]


class DataTypeOptionForm(Select2ModelFormMixin, forms.ModelForm):
    """ModelForm for data type options."""

    select2_fields = ("data_type",)

    class Meta:
        model = DataTypeOption
        fields = ["data_type", "code", "text"]
        widgets = {
            "data_type": DataTypeSelect2Widget(
                attrs=select2_widget_attrs(_("Search data types"))
            ),
        }


class ProjectConfigForm(forms.ModelForm):
    """ModelForm for project configuration records."""

    class Meta:
        model = ProjectConfig
        fields = [
            "publish_date",
            "project",
            "config_folder",
            "config_file",
            "image",
            "transects_file",
        ]
        widgets = {
            "publish_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class DataLogFileForm(forms.ModelForm):
    """ModelForm for uploaded data log files."""

    class Meta:
        model = DataLogFile
        fields = ["upload_date", "uploaded_by", "contents"]
        widgets = {
            "upload_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class TransectDataLogForm(Select2ModelFormMixin, forms.ModelForm):
    """ModelForm linking data log files to transects."""

    select2_fields = ("data_log_file", "transect")

    class Meta:
        model = TransectDataLog
        fields = ["data_log_file", "transect", "is_primary", "username"]
        widgets = {
            "data_log_file": DataLogFileSelect2Widget(
                attrs=select2_widget_attrs(_("Search data log files"))
            ),
            "transect": CompletedTransectSelect2Widget(
                attrs=select2_widget_attrs(_("Search completed transects"))
            ),
        }

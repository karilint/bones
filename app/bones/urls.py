from django.urls import include, path

from .views import (
    CompletedOccurrenceListView,
    CompletedTransectListView,
    CompletedWorkflowListView,
    DashboardView,
    DataLogFileListView,
    DataTypeListView,
    DataTypeOptionListView,
    ProjectConfigListView,
    QuestionListView,
    TemplateTransectListView,
)

app_name = "bones"

transect_patterns = (
    [
        path("", CompletedTransectListView.as_view(), name="list"),
    ],
    "transects",
)

occurrence_patterns = (
    [
        path("", CompletedOccurrenceListView.as_view(), name="list"),
    ],
    "occurrences",
)

workflow_patterns = (
    [
        path("", CompletedWorkflowListView.as_view(), name="list"),
    ],
    "workflows",
)

template_patterns = (
    [
        path("", TemplateTransectListView.as_view(), name="list"),
        path("questions/", QuestionListView.as_view(), name="questions"),
    ],
    "templates",
)

reference_patterns = (
    [
        path("", DataTypeListView.as_view(), name="list"),
        path("data-types/", DataTypeListView.as_view(), name="data_types"),
        path("data-type-options/", DataTypeOptionListView.as_view(), name="data_type_options"),
        path("project-configs/", ProjectConfigListView.as_view(), name="project_config"),
    ],
    "reference",
)

log_patterns = (
    [
        path("", DataLogFileListView.as_view(), name="list"),
    ],
    "logs",
)

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("transects/", include(transect_patterns)),
    path("occurrences/", include(occurrence_patterns)),
    path("workflows/", include(workflow_patterns)),
    path("templates/", include(template_patterns)),
    path("reference/", include(reference_patterns)),
    path("logs/", include(log_patterns)),
]

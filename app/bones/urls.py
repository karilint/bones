from django.urls import include, path

from .views import (
    CompletedOccurrenceDetailView,
    CompletedOccurrenceListView,
    CompletedTransectDetailView,
    CompletedTransectListView,
    CompletedWorkflowListView,
    DashboardView,
    DataLogFileDetailView,
    DataLogFileListView,
    DataTypeDetailView,
    DataTypeListView,
    DataTypeOptionListView,
    ProjectConfigDetailView,
    ProjectConfigListView,
    QuestionDetailView,
    QuestionListView,
    TemplateTransectListView,
)

app_name = "bones"

transect_patterns = (
    [
        path("", CompletedTransectListView.as_view(), name="list"),
        path("<int:pk>/", CompletedTransectDetailView.as_view(), name="detail"),
    ],
    "transects",
)

occurrence_patterns = (
    [
        path("", CompletedOccurrenceListView.as_view(), name="list"),
        path("<int:pk>/", CompletedOccurrenceDetailView.as_view(), name="detail"),
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
        path("questions/<str:pk>/", QuestionDetailView.as_view(), name="question_detail"),
    ],
    "templates",
)

reference_patterns = (
    [
        path("", DataTypeListView.as_view(), name="list"),
        path("data-types/", DataTypeListView.as_view(), name="data_types"),
        path("data-types/<str:pk>/", DataTypeDetailView.as_view(), name="data_type_detail"),
        path("data-type-options/", DataTypeOptionListView.as_view(), name="data_type_options"),
        path("project-configs/", ProjectConfigListView.as_view(), name="project_config"),
        path("project-configs/<int:pk>/", ProjectConfigDetailView.as_view(), name="project_config_detail"),
    ],
    "reference",
)

log_patterns = (
    [
        path("", DataLogFileListView.as_view(), name="list"),
        path("<int:pk>/", DataLogFileDetailView.as_view(), name="detail"),
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

from django.urls import include, path
from django.views.generic import RedirectView

from .image_views import ImageDeleteView, ImageUploadView, ProtectedImageView
from .map_views import (
    AllCompletedTransectsMapDataView, AllCompletedTransectsMapView,
    OccurrenceMapDataView, TransectMapDataView,
)

from .views import (
    CompletedOccurrenceDetailView,
    CompletedInstanceDetailView,
    CompletedOccurrenceHistoryEntryView,
    CompletedOccurrenceHistoryListView,
    CompletedOccurrenceHistoryRecordView,
    CompletedOccurrenceListView,
    CompletedTransectDetailView,
    CompletedTransectHistoryEntryView,
    CompletedTransectHistoryListView,
    CompletedTransectHistoryRecordView,
    CompletedTransectListView,
    CompletedWorkflowHistoryEntryView,
    CompletedWorkflowHistoryListView,
    CompletedWorkflowHistoryRecordView,
    CompletedWorkflowListView,
    CarnivoreReportView,
    BoneDistributionReportView,
    TeethDistributionReportView,
    TransectDetectionReportView,
    DashboardView,
    DataLogFileDetailView,
    DataLogFilePayloadView,
    DataLogFileListView,
    DataReconciliationReportView,
    DataTypeDetailView,
    DataTypeListView,
    DataTypeOptionListView,
    EntityImageHistoryEntryView,
    EntityImageHistoryListView,
    EntityImageHistoryRecordView,
    HistoryIndexView,
    ImageGalleryView,
    MNISummaryView,
    MNIAnalysisExportView,
    WeatheringReportView,
    ProjectConfigDetailView,
    ProjectConfigListView,
    QuestionDetailView,
    QuestionHistoryEntryView,
    QuestionHistoryListView,
    QuestionHistoryRecordView,
    QuestionListView,
    TemplateTransectListView,
)

app_name = "bones"

transect_patterns = (
    [
        path("", CompletedTransectListView.as_view(), name="list"),
        path("map/", AllCompletedTransectsMapView.as_view(), name="map"),
        path("map-data/", AllCompletedTransectsMapDataView.as_view(), name="all_map_data"),
        path("<int:pk>/map-data/", TransectMapDataView.as_view(), name="map_data"),
        path("<int:pk>/", CompletedTransectDetailView.as_view(), name="detail"),
    ],
    "transects",
)

occurrence_patterns = (
    [
        path("", CompletedOccurrenceListView.as_view(), name="list"),
        path("<int:pk>/map-data/", OccurrenceMapDataView.as_view(), name="map_data"),
        path("<int:pk>/", CompletedOccurrenceDetailView.as_view(), name="detail"),
        path("<int:occurrence_pk>/instances/<int:instance_number>/", CompletedInstanceDetailView.as_view(), name="instance_detail"),
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
        path("<int:pk>/payload/", DataLogFilePayloadView.as_view(), name="payload"),
        path("<int:pk>/", DataLogFileDetailView.as_view(), name="detail"),
    ],
    "logs",
)

history_patterns = (
    [
        path("", HistoryIndexView.as_view(), name="index"),
        path("transects/", CompletedTransectHistoryListView.as_view(), name="transects"),
        path(
            "transects/<int:pk>/",
            CompletedTransectHistoryRecordView.as_view(),
            name="transect_record",
        ),
        path(
            "transects/<int:pk>/<int:history_id>/",
            CompletedTransectHistoryEntryView.as_view(),
            name="transect_entry",
        ),
        path("occurrences/", CompletedOccurrenceHistoryListView.as_view(), name="occurrences"),
        path(
            "occurrences/<int:pk>/",
            CompletedOccurrenceHistoryRecordView.as_view(),
            name="occurrence_record",
        ),
        path(
            "occurrences/<int:pk>/<int:history_id>/",
            CompletedOccurrenceHistoryEntryView.as_view(),
            name="occurrence_entry",
        ),
        path("workflows/", CompletedWorkflowHistoryListView.as_view(), name="workflows"),
        path(
            "workflows/<str:pk>/",
            CompletedWorkflowHistoryRecordView.as_view(),
            name="workflow_record",
        ),
        path(
            "workflows/<str:pk>/<int:history_id>/",
            CompletedWorkflowHistoryEntryView.as_view(),
            name="workflow_entry",
        ),
        path("images/", EntityImageHistoryListView.as_view(), name="images"),
        path(
            "images/<uuid:pk>/",
            EntityImageHistoryRecordView.as_view(),
            name="image_record",
        ),
        path(
            "images/<uuid:pk>/<int:history_id>/",
            EntityImageHistoryEntryView.as_view(),
            name="image_entry",
        ),
        path("questions/", QuestionHistoryListView.as_view(), name="questions"),
        path(
            "questions/<str:pk>/",
            QuestionHistoryRecordView.as_view(),
            name="question_record",
        ),
        path(
            "questions/<str:pk>/<int:history_id>/",
            QuestionHistoryEntryView.as_view(),
            name="question_entry",
        ),
    ],
    "history",
)

report_patterns = ([
    path("mni/", MNISummaryView.as_view(), name="mni"),
    path("weathering/", WeatheringReportView.as_view(), name="weathering"),
    path("carnivore-damage/", CarnivoreReportView.as_view(), name="carnivore"),
    path("bone-distribution/", BoneDistributionReportView.as_view(), name="bone_distribution"),
    path("teeth-distribution/", TeethDistributionReportView.as_view(), name="teeth_distribution"),
    path("transect-detection/", TransectDetectionReportView.as_view(), name="transect_detection"),
    path("mni-analysis/", MNIAnalysisExportView.as_view(), name="mni_analysis"),
    path("data-reconciliation/", DataReconciliationReportView.as_view(), name="data_reconciliation"),
], "reports")

urlpatterns = [
    path(
        "",
        RedirectView.as_view(
            pattern_name=f"{app_name}:dashboard",
            permanent=False,
        ),
    ),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("transects/", include(transect_patterns)),
    path("occurrences/", include(occurrence_patterns)),
    path("workflows/", include(workflow_patterns)),
    path("templates/", include(template_patterns)),
    path("reference/", include(reference_patterns)),
    path("logs/", include(log_patterns)),
    path("history/", include(history_patterns)),
    path("images/", ImageGalleryView.as_view(), name="images"),
    path("reports/", include(report_patterns)),
    path("select2/", include("django_select2.urls")),
    path("images/upload/<str:entity_type>/<path:entity_id>/", ImageUploadView.as_view(), name="image_upload"),
    path("images/<uuid:pk>/delete/", ImageDeleteView.as_view(), name="image_delete"),
    path("images/<uuid:pk>/<str:variant>/", ProtectedImageView.as_view(), name="image_file"),
]

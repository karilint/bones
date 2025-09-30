"""View package exports for the Bones application."""
from .dashboard import DashboardView
from .detail import (
    DataLogFileDetailView,
    DataTypeDetailView,
    ProjectConfigDetailView,
    QuestionDetailView,
)
from .lists import (
    CompletedOccurrenceListView,
    CompletedTransectListView,
    CompletedWorkflowListView,
    DataLogFileListView,
    DataTypeListView,
    DataTypeOptionListView,
    ProjectConfigListView,
    QuestionListView,
    TemplateTransectListView,
)
from .master_detail import (
    CompletedOccurrenceDetailView,
    CompletedTransectDetailView,
)

__all__ = [
    "DashboardView",
    "CompletedTransectListView",
    "CompletedOccurrenceListView",
    "CompletedWorkflowListView",
    "TemplateTransectListView",
    "QuestionListView",
    "CompletedTransectDetailView",
    "CompletedOccurrenceDetailView",
    "DataTypeListView",
    "DataTypeOptionListView",
    "ProjectConfigListView",
    "DataLogFileListView",
    "DataLogFileDetailView",
    "DataTypeDetailView",
    "ProjectConfigDetailView",
    "QuestionDetailView",
]

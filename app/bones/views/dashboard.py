"""Dashboard view implementations for the Bones application."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.views.generic import TemplateView

from ..models import (
    CompletedOccurrence,
    CompletedTransect,
    CompletedWorkflow,
    DataLogFile,
    Question,
)
from .mixins import BonesAuthMixin


def _safe_reverse(url_name: Optional[str], *, kwargs: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Resolve ``url_name`` to a URL string when available.

    The dashboard links reference routes that will be introduced later in the
    implementation plan. This helper mirrors the navigation behaviour by
    swallowing :class:`~django.urls.NoReverseMatch` errors so templates can
    render stable ``href`` attributes while the URL map evolves. It also
    retries with the ``bones:`` namespace when callers provide shorthand route
    names so that existing helpers continue to work during the transition.
    """

    if not url_name:
        return None

    candidate_names = [url_name]
    if not url_name.startswith("bones:"):
        candidate_names.append(f"bones:{url_name}")

    for candidate in candidate_names:
        try:
            return reverse(candidate, kwargs=kwargs)
        except NoReverseMatch:
            continue
    return None


def _fallback_url() -> str:
    """Return a guaranteed-resolvable URL for dashboard fallbacks."""

    return _safe_reverse("bones:dashboard") or "/"


class DashboardView(BonesAuthMixin, TemplateView):
    """Aggregate survey activity metrics for the landing page."""

    template_name = "bones/dashboard.html"
    permission_required: tuple[str, ...] = ()

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)

        metrics = self._build_metrics()
        recent_transects = self._fetch_recent_transects()
        recent_occurrences = self._fetch_recent_occurrences()
        recent_uploads = self._fetch_recent_uploads()
        recent_history = self._fetch_recent_history()
        pending_audits = self._count_pending_audits()

        context.update(
            {
                "metrics": metrics,
                "recent_transects": recent_transects,
                "recent_occurrences": recent_occurrences,
                "recent_uploads": recent_uploads,
                "recent_history": recent_history,
                "quick_links": self._build_quick_links(
                    pending_audits=pending_audits,
                    history_count=len(recent_history),
                ),
                "pending_audits": pending_audits,
            }
        )
        return context

    # ------------------------------------------------------------------
    # Metric helpers
    # ------------------------------------------------------------------
    def _build_metrics(self) -> List[Dict[str, Any]]:
        """Return the dashboard metric cards with icons and URLs."""

        completed_transects = self._safe_count(CompletedTransect.objects)
        completed_occurrences = self._safe_count(CompletedOccurrence.objects)
        completed_workflows = self._safe_count(CompletedWorkflow.objects)
        outstanding_tasks = self._calculate_outstanding_tasks()

        return [
            {
                "label": "Completed Transects",
                "icon": "fa-solid fa-route",
                "count": completed_transects,
                "url": _safe_reverse("bones:transects:list") or _fallback_url(),
            },
            {
                "label": "Completed Occurrences",
                "icon": "fa-solid fa-frog",
                "count": completed_occurrences,
                "url": _safe_reverse("bones:occurrences:list") or _fallback_url(),
            },
            {
                "label": "Completed Workflows",
                "icon": "fa-solid fa-diagram-project",
                "count": completed_workflows,
                "url": _safe_reverse("bones:workflows:list") or _fallback_url(),
            },
            {
                "label": "Outstanding Tasks",
                "icon": "fa-solid fa-clipboard-list",
                "count": outstanding_tasks,
                "url": _safe_reverse("bones:workflows:list") or _fallback_url(),
            },
        ]

    def _calculate_outstanding_tasks(self) -> Optional[int]:
        """Combine open workflow and occurrence counts for a headline metric."""

        open_workflows = self._safe_count(
            CompletedWorkflow.objects.filter(completed_by__isnull=True)
        )
        open_occurrences = self._safe_count(
            CompletedOccurrence.objects.filter(recording_end_time__isnull=True)
        )

        if open_workflows is None and open_occurrences is None:
            return None

        total = (open_workflows or 0) + (open_occurrences or 0)
        return total

    def _safe_count(self, queryset: Any) -> Optional[int]:
        """Return ``queryset.count()`` while shielding database errors."""

        try:
            return queryset.count()
        except (DatabaseError, ImproperlyConfigured):
            return None

    # ------------------------------------------------------------------
    # Data retrieval helpers
    # ------------------------------------------------------------------
    def _fetch_recent_transects(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Return the most recent completed transects for the activity feed."""

        try:
            transects = list(
                CompletedTransect.objects.for_dashboard()
                .order_by("-start_time")[:limit]
            )
        except (DatabaseError, ImproperlyConfigured):
            return []

        results: List[Dict[str, Any]] = []
        for transect in transects:
            results.append(
                {
                    "name": transect.name,
                    "start_time": transect.start_time,
                    "state": transect.state,
                    "url": _safe_reverse(
                        "bones:transects:detail", kwargs={"pk": transect.pk}
                    )
                    or _fallback_url(),
                }
            )
        return results

    def _fetch_recent_occurrences(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Return the latest occurrences with preloaded relationships."""

        try:
            occurrences = list(
                CompletedOccurrence.objects.with_related_data()
                .order_by("-recording_start_time")[:limit]
            )
        except (DatabaseError, ImproperlyConfigured):
            return []

        results: List[Dict[str, Any]] = []
        for occurrence in occurrences:
            results.append(
                {
                    "occurrence_number": occurrence.occurrence_number,
                    "transect_name": getattr(occurrence.transect, "name", None),
                    "state": occurrence.state,
                    "url": _safe_reverse(
                        "bones:occurrences:detail", kwargs={"pk": occurrence.pk}
                    )
                    or _fallback_url(),
                }
            )
        return results

    def _fetch_recent_uploads(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Return metadata about the latest uploaded data log files."""

        try:
            uploads = list(
                DataLogFile.objects.order_by("-upload_date").values(
                    "id", "upload_date", "uploaded_by"
                )[:limit]
            )
        except (DatabaseError, ImproperlyConfigured):
            return []

        for upload in uploads:
            upload["url"] = _safe_reverse(
                "bones:logs:detail", kwargs={"pk": upload["id"]}
            ) or _fallback_url()
        return uploads

    def _fetch_recent_history(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Collate recent history entries across audited models."""

        history_sources: Iterable[Dict[str, Any]] = (
            {"label": "Transect", "manager": CompletedTransect.history},
            {"label": "Occurrence", "manager": CompletedOccurrence.history},
            {"label": "Workflow", "manager": CompletedWorkflow.history},
            {"label": "Question", "manager": Question.history},
        )

        collected: List[Dict[str, Any]] = []
        for source in history_sources:
            manager = source["manager"]
            try:
                records = list(
                    manager.all()
                    .select_related("history_user")
                    .order_by("-history_date")[:limit]
                )
            except (DatabaseError, ImproperlyConfigured):
                return []

            for record in records:
                history_type = getattr(
                    record, "get_history_type_display", lambda: record.history_type
                )()
                try:
                    history_object = record.history_object
                except Exception:  # pragma: no cover - defensive fall-back
                    history_object = None

                collected.append(
                    {
                        "label": source["label"],
                        "history_date": record.history_date,
                        "history_user": record.history_user,
                        "history_type": history_type,
                        "object_repr": str(history_object or record),
                    }
                )

        collected.sort(
            key=lambda item: item.get("history_date") or timezone.now(), reverse=True
        )
        return collected[:limit]

    # ------------------------------------------------------------------
    # Quick link helpers
    # ------------------------------------------------------------------
    def _count_pending_audits(self) -> Optional[int]:
        """Count transects flagged for audit or review."""

        try:
            return CompletedTransect.objects.filter(state__icontains="audit").count()
        except (DatabaseError, ImproperlyConfigured):
            return None

    def _build_quick_links(
        self, *, pending_audits: Optional[int], history_count: int
    ) -> List[Dict[str, Any]]:
        """Return quick navigation cards for key follow-up actions."""

        quick_links: List[Dict[str, Any]] = [
            {
                "label": "Review Pending Audits",
                "description": "Transects awaiting post-survey audit.",
                "icon": "fa-solid fa-clipboard-check",
                "url": _safe_reverse("bones:transects:list") or _fallback_url(),
                "count": pending_audits,
            },
            {
                "label": "Browse History Timeline",
                "description": "Inspect recent changes across survey data.",
                "icon": "fa-solid fa-clock-rotate-left",
                "url": _safe_reverse("bones:history:index") or _fallback_url(),
                "count": history_count,
            },
        ]
        return quick_links

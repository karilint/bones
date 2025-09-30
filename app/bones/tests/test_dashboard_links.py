from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Iterable

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch

from ..models import CompletedOccurrence, CompletedTransect, DataLogFile
from ..views.dashboard import DashboardView


class _SliceableList(list):
    """List-like helper that supports ``order_by``/``values`` chains in tests."""

    def order_by(self, *args: Any, **kwargs: Any) -> "_SliceableList":  # pragma: no cover - simple passthrough
        return self


class _ValueList(list):
    """Emulate Django's ``QuerySet.values()`` return object for slicing."""

    def __getitem__(self, key: Any):  # type: ignore[override]
        if isinstance(key, slice):
            return list(super().__getitem__(key))
        return super().__getitem__(key)


class _OrderByStub:
    """Stub the ``order_by``/``values`` chain used for uploads."""

    def __init__(self, rows: Iterable[dict]):
        self._rows = list(rows)

    def order_by(self, *args: Any, **kwargs: Any) -> "_OrderByStub":  # pragma: no cover - passthrough
        return self

    def values(self, *fields: str) -> _ValueList:
        return _ValueList(
            [{field: row[field] for field in fields} for row in self._rows]
        )


class DashboardLinkTests(TestCase):
    def setUp(self) -> None:
        self.view = DashboardView()

    def test_metric_links_resolve_to_collection_views(self):
        with patch.object(DashboardView, "_safe_count", side_effect=[1, 2, 3, 0, 0]):
            metrics = self.view._build_metrics()

        self.assertEqual(metrics[0]["url"], reverse("bones:transects:list"))
        self.assertEqual(metrics[1]["url"], reverse("bones:occurrences:list"))
        self.assertEqual(metrics[2]["url"], reverse("bones:workflows:list"))
        self.assertEqual(metrics[3]["url"], reverse("bones:workflows:list"))

    def test_quick_links_point_to_operational_pages(self):
        links = self.view._build_quick_links(pending_audits=5, history_count=3)

        self.assertEqual(links[0]["url"], reverse("bones:transects:list"))
        self.assertEqual(links[1]["url"], reverse("bones:history:index"))

    def test_recent_transects_link_to_detail_pages(self):
        transect = SimpleNamespace(
            pk=11,
            name="Transect 11",
            start_time=timezone.now(),
            state="completed",
        )
        queryset = _SliceableList([transect])

        with patch.object(CompletedTransect.objects, "for_dashboard", return_value=queryset):
            results = self.view._fetch_recent_transects()

        self.assertEqual(
            results[0]["url"],
            reverse("bones:transects:detail", kwargs={"pk": transect.pk}),
        )

    def test_recent_occurrences_link_to_detail_pages(self):
        occurrence = SimpleNamespace(
            pk=7,
            occurrence_number=7,
            transect=SimpleNamespace(name="Evening Survey"),
            state="verified",
        )
        queryset = _SliceableList([occurrence])

        with patch.object(
            CompletedOccurrence.objects,
            "with_related_data",
            return_value=queryset,
        ):
            results = self.view._fetch_recent_occurrences()

        self.assertEqual(
            results[0]["url"],
            reverse("bones:occurrences:detail", kwargs={"pk": occurrence.pk}),
        )

    def test_recent_uploads_link_to_log_detail(self):
        upload = {
            "id": 5,
            "upload_date": timezone.now(),
            "uploaded_by": "Lead Scientist",
        }

        with patch.object(
            DataLogFile.objects,
            "order_by",
            return_value=_OrderByStub([upload]),
        ):
            uploads = self.view._fetch_recent_uploads()

        self.assertEqual(
            uploads[0]["url"],
            reverse("bones:logs:detail", kwargs={"pk": upload["id"]}),
        )

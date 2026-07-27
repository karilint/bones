"""Authenticated and cached GeoJSON endpoints for completed records."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.cache import patch_cache_control
from django.utils.translation import get_language, gettext as _
from django.views import View
from django.views.generic import TemplateView

from .maps import (
    line_feature, map_context, occurrence_url, point_feature,
    transect_url, valid_coordinate,
)
from .models import CompletedOccurrence, CompletedTransect
from .views.mixins import BonesAuthMixin


def _feature_collection(features: list[dict[str, Any] | None]) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": [feature for feature in features if feature is not None],
    }


def _track_feature(transect: CompletedTransect, *, kind: str = "track"):
    coordinates = [
        coordinate
        for latitude, longitude in transect.track_points.order_by("time", "pk").values_list(
            "lat", "long"
        )
        if (coordinate := valid_coordinate(latitude, longitude)) is not None
    ]
    return line_feature(
        coordinates,
        kind=kind,
        label=_("Transect {transect}").format(transect=transect),
    )


def _landmark_features(transect: CompletedTransect) -> list[dict[str, Any] | None]:
    record_url = transect_url(transect.pk)
    return [
        point_feature(
            valid_coordinate(transect.lat_from, transect.long_from),
            kind="start",
            label=_("Start"),
        ),
        point_feature(
            valid_coordinate(transect.lat_turn, transect.long_turn),
            kind="turn",
            label=_("Turn"),
        ),
        point_feature(
            valid_coordinate(transect.lat_to, transect.long_to),
            kind="end",
            label=_("End"),
        ),
    ]


def _occurrence_feature(
    occurrence_id: Any,
    occurrence_number: Any,
    latitude: Any,
    longitude: Any,
) -> dict[str, Any] | None:
    return point_feature(
        valid_coordinate(latitude, longitude),
        kind="occurrence",
        label=_("Occurrence {number}").format(number=occurrence_number),
        url=occurrence_url(occurrence_id),
        occurrence_id=occurrence_id,
    )


def build_transect_map_data(transect: CompletedTransect) -> dict[str, Any]:
    """Build full-resolution GeoJSON with narrow coordinate-only relation queries."""
    features: list[dict[str, Any] | None] = [_track_feature(transect)]
    features.extend(_landmark_features(transect))
    features.extend(
        _occurrence_feature(pk, number, latitude, longitude)
        for pk, number, latitude, longitude in transect.occurrences.order_by(
            "occurrence_number", "pk"
        ).values_list("pk", "occurrence_number", "lat", "long")
    )
    return _feature_collection(features)


def _cache_key(transect_id: Any) -> str:
    language = get_language() or "default"
    version = getattr(settings, "MAP_DATA_CACHE_VERSION", 1)
    return f"bones:map:transect:{transect_id}:{language}:v{version}"


def get_transect_map_data(transect: CompletedTransect) -> dict[str, Any]:
    timeout = getattr(settings, "MAP_DATA_CACHE_TIMEOUT", 3600)
    return cache.get_or_set(
        _cache_key(transect.pk),
        lambda: build_transect_map_data(transect),
        timeout=timeout,
    )


def occurrence_map_data(
    transect_data: dict[str, Any], occurrence_id: Any
) -> dict[str, Any]:
    """Reuse parent GeoJSON while highlighting one occurrence for its detail page."""
    payload = deepcopy(transect_data)
    for feature in payload["features"]:
        properties = feature.get("properties", {})
        if properties.get("kind") == "track":
            properties["kind"] = "parent_track"
        if properties.get("occurrence_id") == occurrence_id:
            properties["kind"] = "selected_occurrence"
    return payload


class PrivateGeoJsonMixin:
    """Prevent sensitive field observations from being cached publicly."""

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        patch_cache_control(response, private=True, no_store=True)
        return response



def build_all_transects_map_data() -> dict[str, Any]:
    """Build the compact overview map without occurrences or GPS tracks."""
    features: list[dict[str, Any] | None] = []
    rows = CompletedTransect.objects.order_by("pk").values_list(
        "pk", "name", "start_time", "transect_template__name",
        "lat_from", "long_from", "lat_turn", "long_turn", "lat_to", "long_to",
    )
    for (
        pk, name, started, template_name, lat_from, long_from,
        lat_turn, long_turn, lat_to, long_to,
    ) in rows:
        start = valid_coordinate(lat_from, long_from)
        turn = valid_coordinate(lat_turn, long_turn)
        end = valid_coordinate(lat_to, long_to)
        record_url = transect_url(pk)
        transect_label = template_name or name or str(pk)
        walked = started.date().isoformat() if started else ""
        common = {
            "url": record_url,
            "transect_uid": pk,
            "template_name": transect_label,
            "walked": walked,
        }
        features.extend([
            point_feature(start, kind="start", label=_("{transect} — Start").format(transect=transect_label), **common),
            point_feature(turn, kind="turn", label=_("{transect} — Turn").format(transect=transect_label), **common),
            point_feature(end, kind="end", label=_("{transect} — End").format(transect=transect_label), **common),
        ])
        destination = turn or end
        destination_name = "turn" if turn else "end"
        features.append(
            line_feature(
                [coordinate for coordinate in (start, destination) if coordinate],
                kind="summary_line",
                label=_("{transect} route").format(transect=transect_label),
                line_destination=destination_name,
                **common,
            )
        )
    return _feature_collection(features)


def get_all_transects_map_data() -> dict[str, Any]:
    timeout = getattr(settings, "MAP_DATA_CACHE_TIMEOUT", 3600)
    language = get_language() or "default"
    version = getattr(settings, "MAP_DATA_CACHE_VERSION", 1)
    key = f"bones:map:all-transects:{language}:v{version}"
    return cache.get_or_set(key, build_all_transects_map_data, timeout=timeout)


class AllCompletedTransectsMapView(BonesAuthMixin, TemplateView):
    template_name = "bones/all_completed_transects_map.html"
    permission_required = "bones.view_completedtransect"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": _("Completed transects map"),
            "page_icon": "fa-solid fa-map-location-dot",
            "intro_text": _("Start, turn, and end points for all completed transects."),
            "list_url": reverse("bones:transects:list"),
            "breadcrumbs": [
                {"label": _("Dashboard"), "url": reverse("bones:dashboard")},
                {"label": _("Completed transects"), "url": reverse("bones:transects:list")},
                {"label": _("Map"), "url": None},
            ],
        })
        context.update(map_context(reverse("bones:transects:all_map_data"), title=_("Completed transects map")))
        context["map_legend"] = [
            {"label": _("Start"), "color": "#43a047"},
            {"label": _("Turn"), "color": "#fb8c00"},
            {"label": _("End"), "color": "#e53935"},
        ]
        return context


class AllCompletedTransectsMapDataView(
    PrivateGeoJsonMixin, LoginRequiredMixin, PermissionRequiredMixin, View
):
    permission_required = "bones.view_completedtransect"

    def get(self, request) -> JsonResponse:
        return JsonResponse(
            get_all_transects_map_data(), content_type="application/geo+json"
        )

class TransectMapDataView(
    PrivateGeoJsonMixin, LoginRequiredMixin, PermissionRequiredMixin, View
):
    permission_required = "bones.view_completedtransect"

    def get(self, request, pk: int) -> JsonResponse:
        transect = get_object_or_404(
            CompletedTransect.objects.only(
                "uid", "name", "lat_from", "long_from", "lat_turn", "long_turn",
                "lat_to", "long_to"
            ),
            pk=pk,
        )
        return JsonResponse(
            get_transect_map_data(transect), content_type="application/geo+json"
        )


class OccurrenceMapDataView(
    PrivateGeoJsonMixin, LoginRequiredMixin, PermissionRequiredMixin, View
):
    permission_required = "bones.view_completedoccurrence"

    def get(self, request, pk: int) -> JsonResponse:
        occurrence = get_object_or_404(
            CompletedOccurrence.objects.only("id", "transect_id"), pk=pk
        )
        transect = get_object_or_404(
            CompletedTransect.objects.only(
                "uid", "name", "lat_from", "long_from", "lat_turn", "long_turn",
                "lat_to", "long_to"
            ),
            pk=occurrence.transect_id,
        )
        payload = occurrence_map_data(get_transect_map_data(transect), occurrence.pk)
        return JsonResponse(payload, content_type="application/geo+json")
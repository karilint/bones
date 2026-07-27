"""GeoJSON and template helpers for completed-record maps."""
from __future__ import annotations

import math
from typing import Any, Iterable

from django.conf import settings
from django.templatetags.static import static
from django.urls import reverse


DEFAULT_TILE_URL = "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"
DEFAULT_TILE_ATTRIBUTION = (
    "Map data: &copy; OpenStreetMap contributors, SRTM | "
    "Map display: &copy; OpenTopoMap (CC-BY-SA)"
)


def valid_coordinate(latitude: Any, longitude: Any) -> list[float] | None:
    """Return a GeoJSON coordinate or None for missing/invalid database data."""
    if latitude in (None, "") or longitude in (None, ""):
        return None
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(lat) or not math.isfinite(lon):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    if lat == 0 and lon == 0:
        return None
    return [lon, lat]


def point_feature(
    coordinate: list[float] | None,
    *,
    kind: str,
    label: str,
    **properties: Any,
) -> dict[str, Any] | None:
    if coordinate is None:
        return None
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": coordinate},
        "properties": {"kind": kind, "label": label, **properties},
    }


def line_feature(
    coordinates: Iterable[list[float]],
    *,
    kind: str,
    label: str,
    **properties: Any,
) -> dict[str, Any] | None:
    points = list(coordinates)
    if len(points) < 2:
        return None
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": points},
        "properties": {"kind": kind, "label": label, **properties},
    }


def map_context(data_url: str, *, title: str) -> dict[str, Any]:
    """Build the common context consumed by the reusable map tab."""
    return {
        "map_data_url": data_url,
        "map_title": title,
        "map_tile_url": getattr(settings, "MAP_TILE_URL", DEFAULT_TILE_URL),
        "map_tile_attribution": getattr(
            settings, "MAP_TILE_ATTRIBUTION", DEFAULT_TILE_ATTRIBUTION
        ),
        "map_tile_max_zoom": getattr(settings, "MAP_TILE_MAX_ZOOM", 17),
        "map_leaflet_css_url": static("vendor/leaflet/leaflet.css"),
        "map_leaflet_js_url": static("vendor/leaflet/leaflet.js"),
    }


def transect_url(pk: Any) -> str:
    return reverse("bones:transects:detail", kwargs={"pk": pk})


def occurrence_url(pk: Any) -> str:
    return reverse("bones:occurrences:detail", kwargs={"pk": pk})

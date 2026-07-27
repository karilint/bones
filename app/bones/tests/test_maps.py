import json
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings

from ..map_views import (
    AllCompletedTransectsMapDataView,
    AllCompletedTransectsMapView,
    OccurrenceMapDataView,
    TransectMapDataView,
    build_all_transects_map_data,
    get_transect_map_data,
)
from ..maps import map_context, valid_coordinate


class OrderedManager:
    def __init__(self, items):
        self.items = list(items)
        self.ordering = None

    def order_by(self, *fields):
        self.ordering = fields
        self.items = sorted(
            self.items,
            key=lambda item: tuple(getattr(item, field) for field in fields),
        )
        return self

    def values_list(self, *fields):
        return [tuple(getattr(item, field) for field in fields) for item in self.items]


class MapHelperTests(SimpleTestCase):
    def test_valid_coordinate_uses_geojson_longitude_latitude_order(self):
        self.assertEqual(valid_coordinate(-0.123, 36.987), [36.987, -0.123])

    def test_invalid_coordinates_are_omitted(self):
        self.assertIsNone(valid_coordinate(None, 36))
        self.assertIsNone(valid_coordinate(91, 36))
        self.assertIsNone(valid_coordinate(-1, 181))
        self.assertIsNone(valid_coordinate(0, 0))

    @override_settings(
        MAP_TILE_URL="https://tiles.test/{z}/{x}/{y}.png",
        MAP_TILE_MAX_ZOOM=15,
    )
    def test_map_context_uses_configured_tile_source(self):
        context = map_context("/map-data/", title="Test map")
        self.assertEqual(context["map_data_url"], "/map-data/")
        self.assertEqual(context["map_tile_max_zoom"], 15)
        self.assertIn("tiles.test", context["map_tile_url"])


class AllTransectsMapTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    @patch("bones.map_views.CompletedTransect.objects")
    def test_overview_uses_turn_and_falls_back_to_end(self, objects):
        rows = [
            (101, "First", None, "Template A", 1, 36, 2, 37, 3, 38),
            (102, "Second", None, "Template B", 4, 39, None, None, 5, 40),
        ]
        objects.order_by.return_value.values_list.return_value = rows

        payload = build_all_transects_map_data()
        features = payload["features"]
        lines = [f for f in features if f["properties"]["kind"] == "summary_line"]

        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["geometry"]["coordinates"], [[36.0, 1.0], [37.0, 2.0]])
        self.assertEqual(lines[0]["properties"]["line_destination"], "turn")
        self.assertEqual(lines[1]["geometry"]["coordinates"], [[39.0, 4.0], [40.0, 5.0]])
        self.assertEqual(lines[1]["properties"]["line_destination"], "end")
        self.assertNotIn("occurrence", [f["properties"]["kind"] for f in features])
        self.assertTrue(all(f["properties"].get("url") for f in features))

    def test_page_and_data_endpoint_require_transect_permission(self):
        self.assertEqual(
            AllCompletedTransectsMapView.permission_required,
            "bones.view_completedtransect",
        )
        self.assertEqual(
            AllCompletedTransectsMapDataView.permission_required,
            "bones.view_completedtransect",
        )
        request = self.factory.get("/transects/map/")
        request.user = AnonymousUser()
        response = AllCompletedTransectsMapView.as_view()(request)
        self.assertEqual(response.status_code, 302)

class MapDataViewTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    @staticmethod
    def _point(pk, lat, lon, when):
        return SimpleNamespace(pk=pk, lat=lat, long=lon, time=when)

    @staticmethod
    def _transect(track, occurrences):
        return SimpleNamespace(
            pk=123, name="Example", lat_from=-0.1, long_from=36.7,
            lat_turn=None, long_turn=None, lat_to=-0.2, long_to=36.8,
            track_points=track, occurrences=occurrences,
        )

    def test_transect_geojson_orders_track_and_omits_invalid_points(self):
        track = OrderedManager([
            self._point(2, -0.2, 36.8, "2020-01-01T10:01:00Z"),
            self._point(3, 200, 36.9, "2020-01-01T10:02:00Z"),
            self._point(1, -0.1, 36.7, "2020-01-01T10:00:00Z"),
        ])
        occurrences = OrderedManager([
            SimpleNamespace(pk=7, occurrence_number=1, lat=-0.15, long=36.75)
        ])
        transect = self._transect(track, occurrences)
        request = self.factory.get("/transects/123/map-data/")

        with patch("bones.map_views.get_object_or_404", return_value=transect):
            response = TransectMapDataView().get(request, pk=123)

        payload = json.loads(response.content)
        line = next(
            feature for feature in payload["features"]
            if feature["geometry"]["type"] == "LineString"
        )
        self.assertEqual(line["geometry"]["coordinates"], [[36.7, -0.1], [36.8, -0.2]])
        self.assertEqual(track.ordering, ("time", "pk"))
        self.assertEqual(payload["type"], "FeatureCollection")

    def test_occurrence_map_marks_selected_occurrence(self):
        selected = SimpleNamespace(pk=7, occurrence_number=2, lat=-0.15, long=36.75)
        other = SimpleNamespace(pk=8, occurrence_number=3, lat=-0.16, long=36.76)
        track = OrderedManager([
            self._point(1, -0.1, 36.7, "2020-01-01T10:00:00Z"),
            self._point(2, -0.2, 36.8, "2020-01-01T10:01:00Z"),
        ])
        transect = self._transect(track, OrderedManager([selected, other]))
        selected.transect = transect
        selected.transect_id = transect.pk
        request = self.factory.get("/occurrences/7/map-data/")

        with patch(
            "bones.map_views.get_object_or_404",
            side_effect=[selected, transect],
        ):
            response = OccurrenceMapDataView().get(request, pk=7)

        kinds = [feature["properties"]["kind"] for feature in json.loads(response.content)["features"]]
        self.assertEqual(kinds.count("selected_occurrence"), 1)
        self.assertIn("parent_track", kinds)


    @override_settings(MAP_DATA_CACHE_TIMEOUT=60, MAP_DATA_CACHE_VERSION=99)
    def test_transect_geojson_is_reused_from_cache(self):
        transect = SimpleNamespace(pk=987)
        payload = {"type": "FeatureCollection", "features": []}
        with patch("bones.map_views.build_transect_map_data", return_value=payload) as build:
            self.assertEqual(get_transect_map_data(transect), payload)
            self.assertEqual(get_transect_map_data(transect), payload)
        build.assert_called_once_with(transect)
    def test_map_endpoints_require_login(self):
        request = self.factory.get("/transects/123/map-data/")
        request.user = AnonymousUser()
        response = TransectMapDataView.as_view()(request, pk=123)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TransectMapDataView.permission_required, "bones.view_completedtransect")
        self.assertEqual(OccurrenceMapDataView.permission_required, "bones.view_completedoccurrence")
from datetime import datetime
from types import SimpleNamespace

from django.test import SimpleTestCase

from ..management.commands.reconcile_data_logs import legacy_track_slot_key
from ..management.commands.recover_gps_tracks import collect_candidates


def parsed(*points, log_id=1, error="", transects=None):
    return SimpleNamespace(
        log_id=log_id, error=error, track_points=list(points),
        transects=list(transects or []),
    )


def point(**overrides):
    values = {
        "transect_uid": 17,
        "event": "CHECKPOINT",
        "time": datetime(2025, 1, 1, 10, 39, 48),
        "lat": -0.0407316667,
        "long": 36.8723816667,
        "user": "Briana",
        "source": "line 12",
    }
    values.update(overrides)
    return values


class GPSRecoveryCandidateTests(SimpleTestCase):
    def test_keeps_devices_separate_and_deduplicates_repeated_logs(self):
        briana = point()
        fire = point(user="Fire")
        candidates, skipped = collect_candidates(
            [parsed(briana, fire), parsed(briana, log_id=2)],
            current_ids={17}, deleted_ids=set(), existing_keys=set(),
        )

        self.assertEqual([item.user for item in candidates], ["Briana", "Fire"])
        self.assertEqual(skipped["already_present_or_repeated"], 1)

    def test_existing_legacy_database_slot_suppresses_coordinate_variant(self):
        slot = legacy_track_slot_key(
            17, "Briana", datetime(2025, 1, 1, 10, 40), "CHECKPOINT",
        )
        candidates, skipped = collect_candidates(
            [parsed(point(lat=-0.040700))],
            current_ids={17}, deleted_ids=set(), existing_keys=set(),
            existing_slots={slot},
        )

        self.assertEqual(candidates, [])
        self.assertEqual(skipped["already_present_or_repeated"], 1)

    def test_only_safe_events_with_live_parents_and_complete_data_are_selected(self):
        candidates, skipped = collect_candidates(
            [parsed(
                point(event="PAUSETRANSECT"),
                point(transect_uid=18),
                point(transect_uid=19),
                point(user=""),
                point(lat=91),
                point(event="TURNAROUND", time=datetime(2025, 1, 1, 10, 41)),
            )],
            current_ids={17, 19}, deleted_ids={19}, existing_keys=set(),
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].event, "TURNAROUND")
        self.assertEqual(skipped["unsupported_event"], 1)
        self.assertEqual(skipped["missing_parent"], 1)
        self.assertEqual(skipped["deleted_parent"], 1)
        self.assertEqual(skipped["missing_identity_or_time"], 1)
        self.assertEqual(skipped["invalid_coordinates"], 1)

    def test_transect_filter_is_applied_before_skip_reporting(self):
        candidates, skipped = collect_candidates(
            [parsed(point(transect_uid=17), point(transect_uid=18))],
            current_ids={17, 18}, deleted_ids=set(), existing_keys=set(),
            selected_ids={18},
        )

        self.assertEqual([item.transect_id for item in candidates], [18])
        self.assertEqual(skipped, {})

    def test_cancelled_parent_is_not_reported_as_missing(self):
        candidates, skipped = collect_candidates(
            [parsed(point(transect_uid=18))],
            current_ids=set(), deleted_ids=set(), existing_keys=set(),
            cancelled_ids={18},
        )

        self.assertEqual(candidates, [])
        self.assertEqual(skipped["cancelled_parent"], 1)
        self.assertNotIn("missing_parent", skipped)

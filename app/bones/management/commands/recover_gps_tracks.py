"""Safely recover checkpoint and turnaround points from field data logs."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from bones.management.commands.reconcile_data_logs import (
    legacy_track_key, legacy_track_slot_key,
)
from bones.models import (
    CompletedTransect, CompletedTransectTrack, DataLogFile, TransectDeletion,
)
from bones.reports.data_log_reconciliation import parse_log


SUPPORTED_EVENTS = {"CHECKPOINT", "TURNAROUND"}
WRITE_BATCH_SIZE = 100


def _chunks(items, size=WRITE_BATCH_SIZE):
    for start in range(0, len(items), size):
        yield items[start:start + size]


@dataclass(frozen=True)
class RecoveryPoint:
    log_id: int
    source: str
    transect_id: int
    user: str
    time: object
    lat: Decimal
    long: Decimal
    event: str

    @property
    def legacy_key(self):
        return legacy_track_key(
            self.transect_id, self.user, self.time, self.lat, self.long, self.event,
        )

    @property
    def slot_key(self):
        return legacy_track_slot_key(
            self.transect_id, self.user, self.time, self.event,
        )


def _event_for_database_point(point):
    if point["is_turn_point"]:
        return "TURNAROUND"
    if point["is_checkpoint"]:
        return "CHECKPOINT"
    return "OTHER"


def database_legacy_keys(points):
    """Return device-aware keys matching SQL Server's legacy precision."""
    return {
        legacy_track_key(
            point["transect_id"], point["user"], point["time"],
            point["lat"], point["long"], _event_for_database_point(point),
        )
        for point in points
    }


def database_slot_keys(points):
    return {
        legacy_track_slot_key(
            point["transect_id"], point["user"], point["time"],
            _event_for_database_point(point),
        )
        for point in points
    }


def collect_candidates(
    parsed_logs, current_ids, deleted_ids, existing_keys, selected_ids=None,
    existing_slots=None, cancelled_ids=None,
):
    """Select deterministic, valid, non-duplicate recovery points."""
    selected_ids = set(selected_ids or [])
    cancelled_ids = set(cancelled_ids or [])
    seen = set(existing_keys)
    seen_slots = set(existing_slots or [])
    candidates = []
    skipped = Counter()

    for parsed in parsed_logs:
        if parsed.error:
            skipped["unparseable_log"] += 1
            continue
        for raw in parsed.track_points:
            uid = raw.get("transect_uid")
            if selected_ids and uid not in selected_ids:
                continue
            event = str(raw.get("event") or "").upper()
            if event not in SUPPORTED_EVENTS:
                skipped["unsupported_event"] += 1
                continue
            if uid in deleted_ids:
                skipped["deleted_parent"] += 1
                continue
            if uid not in current_ids:
                reason = "cancelled_parent" if uid in cancelled_ids else "missing_parent"
                skipped[reason] += 1
                continue
            user = str(raw.get("user") or "").strip()
            if not user or not raw.get("time"):
                skipped["missing_identity_or_time"] += 1
                continue
            try:
                lat = Decimal(str(raw.get("lat")))
                long = Decimal(str(raw.get("long")))
            except (InvalidOperation, TypeError, ValueError):
                skipped["invalid_coordinates"] += 1
                continue
            if (not (-90 <= lat <= 90 and -180 <= long <= 180)
                    or (lat == 0 and long == 0)):
                skipped["invalid_coordinates"] += 1
                continue
            point = RecoveryPoint(
                log_id=parsed.log_id,
                source=str(raw.get("source") or "unknown source"),
                transect_id=uid,
                user=user,
                time=raw["time"],
                lat=lat,
                long=long,
                event=event,
            )
            if point.legacy_key in seen or point.slot_key in seen_slots:
                skipped["already_present_or_repeated"] += 1
                continue
            seen.add(point.legacy_key)
            seen_slots.add(point.slot_key)
            candidates.append(point)
    return candidates, skipped


class Command(BaseCommand):
    help = (
        "Recover valid checkpoint/turnaround points from data logs. "
        "Dry-run is the default; use --commit with --actor to write."
    )

    def add_arguments(self, parser):
        parser.add_argument("--log-id", action="append", type=int, dest="log_ids")
        parser.add_argument("--transect-id", action="append", type=int, dest="transect_ids")
        parser.add_argument("--limit", type=int)
        parser.add_argument("--commit", action="store_true")
        parser.add_argument("--actor", help="Username recorded in simple-history")

    def handle(self, *args, **options):
        if options["limit"] is not None and options["limit"] < 1:
            raise CommandError("--limit must be a positive integer")
        actor = self._actor(options)
        candidates, skipped = self._load_candidates(options)
        if options["limit"]:
            candidates = candidates[:options["limit"]]

        mode = "COMMIT" if options["commit"] else "DRY RUN"
        self.stdout.write(f"{mode}: {len(candidates)} GPS point(s) selected")
        for reason, count in sorted(skipped.items()):
            self.stdout.write(f"Skipped {reason}: {count}")
        if not options["commit"]:
            self.stdout.write("No database changes made. Add --commit --actor USERNAME to import.")
            return

        created, race_skips = self._commit(candidates, actor)
        self.stdout.write(self.style.SUCCESS(f"Imported {created} GPS point(s)."))
        if race_skips:
            self.stdout.write(f"Skipped during final locked check: {race_skips}")

    def _actor(self, options):
        if not options["commit"]:
            return None
        if not options.get("actor"):
            raise CommandError("--actor is required with --commit")
        try:
            return get_user_model().objects.get(username=options["actor"], is_active=True)
        except get_user_model().DoesNotExist as exc:
            raise CommandError("--actor must name an active application user") from exc

    def _load_candidates(self, options):
        logs = DataLogFile.objects.order_by("id")
        if options.get("log_ids"):
            logs = logs.filter(pk__in=options["log_ids"])
        parsed = [parse_log(row["id"], row["contents"]) for row in logs.values("id", "contents")]
        cancelled_ids = {
            entry["uid"] for item in parsed for entry in item.transects
            if entry.get("uid") is not None and entry.get("state") == "cancelled"
        }
        current_ids = set(CompletedTransect.objects.values_list("pk", flat=True))
        deleted_ids = set(TransectDeletion.objects.values_list("transect_uid", flat=True))
        point_rows = list(CompletedTransectTrack.objects.values(
            "transect_id", "user", "time", "lat", "long",
            "is_checkpoint", "is_turn_point",
        ))
        return collect_candidates(
            parsed, current_ids, deleted_ids, database_legacy_keys(point_rows),
            options.get("transect_ids"), database_slot_keys(point_rows),
            cancelled_ids,
        )

    @transaction.atomic
    def _commit(self, candidates, actor):
        if not candidates:
            return 0, 0
        transect_ids = {point.transect_id for point in candidates}
        list(CompletedTransect.objects.select_for_update().filter(pk__in=transect_ids))
        point_rows = list(
            CompletedTransectTrack.objects.select_for_update().filter(
                transect_id__in=transect_ids,
            ).values(
                "transect_id", "user", "time", "lat", "long",
                "is_checkpoint", "is_turn_point",
            )
        )
        existing = database_legacy_keys(point_rows)
        existing_slots = database_slot_keys(point_rows)
        # This legacy table does not generate its declared AutoField value.
        # Hold a table lock while reserving sequential IDs to avoid collisions
        # with another importer or the field application.
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COALESCE(MAX([ID]), 0) "
                "FROM [CompletedTransectsTrack] WITH (TABLOCKX, HOLDLOCK)"
            )
            next_id = cursor.fetchone()[0] + 1
        base_rows = []
        history_rows = []
        race_skips = 0
        history_model = CompletedTransectTrack.history.model
        for point in candidates:
            if point.legacy_key in existing or point.slot_key in existing_slots:
                race_skips += 1
                continue
            # Persist the same minute precision used by the legacy SQL column.
            stored_time = point.legacy_key[2]
            if timezone.is_naive(stored_time):
                stored_time = timezone.make_aware(
                    stored_time, timezone.get_current_timezone(),
                )
            values = {
                "id": next_id, "transect_id": point.transect_id,
                "user": point.user, "time": stored_time,
                "lat": point.lat, "long": point.long,
                "is_start": False,
                "is_checkpoint": point.event == "CHECKPOINT",
                "is_occurrence": False,
                "is_turn_point": point.event == "TURNAROUND",
                "is_end": False,
            }
            reason = (
                f"GPS recovery: data log {point.log_id}, {point.source}"
            )[:100]
            base_rows.append([
                values["id"], values["user"], values["transect_id"],
                values["time"], values["lat"], values["long"],
                values["is_start"], values["is_checkpoint"],
                values["is_occurrence"], values["is_turn_point"],
                values["is_end"],
            ])
            history_rows.append(history_model(
                **values, history_date=timezone.now(),
                history_change_reason=reason, history_type="+",
                history_user=actor,
            ))
            next_id += 1
            existing.add(point.legacy_key)
            existing_slots.add(point.slot_key)

        # Django assumes the unmanaged AutoField is an IDENTITY. Use bounded,
        # parameterized multi-row inserts for the application-assigned IDs.
        columns = (
            "([ID], [User], [CompletedTransectUID], [Time], [Lat], [Long], "
            "[isStart], [isCheckPoint], [isOccurrence], [isTurnPoint], [isEnd])"
        )
        row_sql = "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        with connection.cursor() as cursor:
            for batch in _chunks(base_rows):
                cursor.execute(
                    f"INSERT INTO [CompletedTransectsTrack] {columns} VALUES "
                    + ", ".join([row_sql] * len(batch)),
                    [value for row in batch for value in row],
                )
        history_model.objects.bulk_create(
            history_rows, batch_size=WRITE_BATCH_SIZE,
        )
        return len(base_rows), race_skips

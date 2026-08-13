"""Export a read-only comparison of field logs and completed survey tables."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from bones.models import (
    CompletedOccurrence, CompletedResponse, CompletedTransect,
    CompletedTransectTrack, CompletedWorkflow, DataLogFile, InstanceDeletion,
    OccurrenceDeletion, TemplateTransect, TemplateWorkflow, TransectDataLog, TransectDeletion,
)
from bones.reports.data_log_reconciliation import (
    gps_status, parse_log, summary_rows, write_workbook,
)


def merged_occurrence_candidate(entry, logged_instances, workflows_by_uid, occurrences_by_id):
    """Return the one current occurrence containing every logged workflow UID."""
    workflow_uids = {item.get("workflow_uid") for item in logged_instances if item.get("workflow_uid")}
    if not workflow_uids or not workflow_uids.issubset(workflows_by_uid):
        return None
    occurrence_ids = {workflows_by_uid[uid].occurrence_id for uid in workflow_uids}
    if len(occurrence_ids) != 1:
        return None
    current = occurrences_by_id.get(occurrence_ids.pop())
    return current


def cross_device_occurrence_candidate(
    entry, logged_occurrences, occurrences_by_parent_number,
):
    """Match a device-number alias using unique nearby substantive evidence."""
    required = ("transect_uid", "number", "start_time", "lat", "long", "user")
    if any(entry.get(field) is None for field in required):
        return None
    matches = {}
    for peer in logged_occurrences:
        if (
            peer is entry
            or peer.get("log_id") == entry.get("log_id")
            or str(peer.get("user") or "").casefold()
            == str(entry.get("user") or "").casefold()
            or peer.get("transect_uid") != entry["transect_uid"]
            or peer.get("number") == entry["number"]
            or peer.get("state") != "completed"
            or peer.get("evidence_count", 0) <= 0
            or any(peer.get(field) is None for field in ("start_time", "lat", "long"))
        ):
            continue
        seconds = abs((peer["start_time"] - entry["start_time"]).total_seconds())
        if (
            seconds > 120
            or abs(float(peer["lat"]) - float(entry["lat"])) > 0.0001
            or abs(float(peer["long"]) - float(entry["long"])) > 0.0001
        ):
            continue
        candidates = occurrences_by_parent_number[
            (entry["transect_uid"], peer["number"])
        ]
        if len(candidates) == 1:
            matches[candidates[0].id] = candidates[0]
    return next(iter(matches.values())) if len(matches) == 1 else None


def is_empty_logged_occurrence(entry, instance_count):
    """Identify a line-log occurrence shell containing no answers or workflows."""
    return entry.get("evidence_count") == 0 and instance_count == 0


def logged_parent_transect_cancelled(entry, cancelled_transects):
    """Check the exact line-log session, falling back for older formats."""
    parent_transect = entry.get("parent_transect")
    if parent_transect:
        return parent_transect.get("state") == "cancelled"
    return entry.get("transect_uid") in cancelled_transects


def omit_logged_occurrence(
    entry, instance_count, cancelled_transects, deleted=None,
    parent_deleted=None, merged_current=None, alias_current=None,
):
    """Omit non-actionable occurrence shells while retaining valid merges."""
    cancelled = logged_parent_transect_cancelled(entry, cancelled_transects)
    return (
        cancelled or bool(deleted)
        or (bool(parent_deleted) and not merged_current)
        or (
            is_empty_logged_occurrence(entry, instance_count)
            and not (merged_current or alias_current)
        )
    )


def omit_logged_instance(
    entry, cancelled_transects, deleted=None, parent_deleted=None,
    current_matches=None,
):
    """Keep cancelled, deleted, and empty workflow shells out of report work."""
    empty_shell = (
        entry.get("state") != "completed"
        and entry.get("response_count", 0) == 0
    )
    cancelled = logged_parent_transect_cancelled(entry, cancelled_transects)
    return (
        (cancelled and not current_matches)
        or bool(deleted) or bool(parent_deleted) or empty_shell
    )


def legacy_track_key(uid, user, time, lat, long, event):
    """Match SQL legacy minute/coordinate precision without merging devices."""
    if time:
        time = (time.replace(tzinfo=None) + timedelta(seconds=30)).replace(
            second=0, microsecond=0,
        )
    return (
        uid, str(user or "").strip().casefold(), time,
        round(float(lat), 6) if lat is not None else None,
        round(float(long), 6) if long is not None else None,
        event,
    )


def legacy_track_slot_key(uid, user, time, event):
    """Represent the fields in the legacy table's unique constraint."""
    key = legacy_track_key(uid, user, time, None, None, event)
    return key[0], key[1], key[2], key[5]


def is_recoverable_track_event(event):
    """Only events with an exact legacy track flag are recovery records."""
    return event in {"CHECKPOINT", "TURNAROUND"}


def has_valid_track_coordinates(lat, long):
    """Reject absent, out-of-range, and GPS-failure zero coordinates."""
    return (
        lat is not None and long is not None
        and -90 <= lat <= 90 and -180 <= long <= 180
        and not (lat == 0 and long == 0)
    )


def collect_reconciliation_rows(options):
    """Run the shared read-only extraction used by CLI and web exports."""
    logs = DataLogFile.objects.all().order_by("id")
    if options.get("log_ids"):
        logs = logs.filter(pk__in=options["log_ids"])
    log_rows = list(logs.values("id", "upload_date", "uploaded_by", "contents"))
    parsed = [parse_log(row["id"], row["contents"]) for row in log_rows]
    command = Command()
    rows = command._reconcile(parsed, log_rows, options)
    # Cancelled field work is a parser safeguard, not a recovery candidate.
    rows["Recovery candidates"] = [
        row for row in rows["Recovery candidates"]
        if row[2] != "CANCELLED_IN_LOG"
    ]
    rows["Summary"] = summary_rows(rows) + [
        ["Logs selected", len(log_rows)],
        ["Logs parsed without issues", len(log_rows) - len(rows["Log parse issues"])],
        ["GPS required from year", options.get("gps_required_from_year") or "Not specified"],
    ]
    recovery_counts = Counter(row[2] for row in rows["Recovery candidates"])
    rows["Summary"].extend([[f"Recovery: {status}", count] for status, count in sorted(recovery_counts.items())])
    rows["Methodology"] = command._methodology(options)
    return rows, len(log_rows)


def filter_reconciliation_rows(rows, included_statuses):
    """Apply presentation status choices without changing summary totals."""
    # Permanent deletions are audit evidence, never outstanding report work.
    selected = set(included_statuses) - {"DELETED_CONFIRMED"}
    for sheet, status_column in (("Transects", 5), ("Occurrences", 5), ("Instances", 7)):
        rows[sheet] = [row for row in rows[sheet] if row[status_column] in selected]
    rows["GPS"] = [row for row in rows["GPS"] if row[5] in selected]
    rows["Critical findings"] = [row for row in rows["Critical findings"] if row[2] in selected]
    return rows


class Command(BaseCommand):
    help = "Create a read-only Excel reconciliation of data logs and completed data."

    def add_arguments(self, parser):
        parser.add_argument("--output", default="data-log-reconciliation.xlsx")
        parser.add_argument("--from-year", type=int)
        parser.add_argument("--to-year", type=int)
        parser.add_argument("--log-id", action="append", type=int, dest="log_ids")
        parser.add_argument("--gps-required-from-year", type=int)
        parser.add_argument("--strict", action="store_true")

    def handle(self, *args, **options):
        rows, log_count = collect_reconciliation_rows(options)
        if options["strict"] and rows["Log parse issues"]:
            raise CommandError(f"{len(rows['Log parse issues'])} log file(s) could not be parsed; no workbook written")
        filter_reconciliation_rows(rows, {"MISSING", "AMBIGUOUS", "DELETED_CONFIRMED", "HISTORICAL_ONLY", "CURRENT_PROBABLE", "GPS_MISSING", "GPS_PARTIAL", "GPS_OUTSIDE_TIME_RANGE", "GPS_INVALID_COORDINATES", "GPS_HISTORY_ONLY", "GPS_EXPECTATION_UNKNOWN", "GPS_NOT_EXPECTED_EARLY_MANUAL"})
        target = write_workbook(options["output"], rows)
        statuses = Counter(row[2] for row in rows["Critical findings"])
        self.stdout.write(self.style.SUCCESS(f"Reconciliation workbook: {target}"))
        self.stdout.write(f"Logs: {log_count}; parse issues: {len(rows['Log parse issues'])}")
        self.stdout.write(f"Critical findings: {len(rows['Critical findings'])}; ambiguous: {statuses.get('AMBIGUOUS', 0)}")
        self.stdout.write(f"Database-only records: {len(rows['Database only'])}; suspicious GPS: {sum(1 for row in rows['GPS'] if row[5] == 'GPS_MISSING')}")

    def _reconcile(self, parsed, log_rows, options):
        rows = {name: [] for name in (
            "Summary", "Critical findings", "Transects", "Occurrences", "Instances", "GPS",
            "Recovery candidates", "Database only", "Deleted evidence", "Log parse issues", "Methodology",
        )}
        metadata = {row["id"]: row for row in log_rows}
        for item in parsed:
            if item.error:
                meta = metadata[item.log_id]
                rows["Log parse issues"].append([item.log_id, meta["upload_date"], meta["uploaded_by"], item.format, item.error])

        transects = list(CompletedTransect.objects.select_related("transect_template").all())
        occurrences = list(CompletedOccurrence.objects.all())
        workflows = list(CompletedWorkflow.objects.select_related("template_workflow").all())
        response_counts = Counter({row["workflow_id"]: row["count"] for row in CompletedResponse.objects.values("workflow_id").annotate(count=Count("id"))})
        track_counts = Counter({row["transect_id"]: row["count"] for row in CompletedTransectTrack.objects.values("transect_id").annotate(count=Count("id"))})
        database_track_keys = set()
        database_legacy_track_keys = set()
        database_legacy_track_slots = set()
        for point in CompletedTransectTrack.objects.values("transect_id", "user", "time", "lat", "long", "is_checkpoint", "is_turn_point"):
            event = "TURNAROUND" if point["is_turn_point"] else "CHECKPOINT" if point["is_checkpoint"] else "OTHER"
            time = point["time"].replace(tzinfo=None) if point["time"] else None
            user = str(point["user"] or "").strip().casefold()
            database_track_keys.add((point["transect_id"], user, time, round(float(point["lat"]), 8), round(float(point["long"]), 8), event))
            database_legacy_track_keys.add(legacy_track_key(
                point["transect_id"], user, time, point["lat"], point["long"], event,
            ))
            database_legacy_track_slots.add(legacy_track_slot_key(
                point["transect_id"], user, time, event,
            ))
        links = defaultdict(set)
        for log_id, transect_id in TransectDataLog.objects.values_list("data_log_file_id", "transect_id"):
            links[log_id].add(transect_id)

        by_transect = {item.uid: item for item in transects}
        occurrences_by_id = {item.id: item for item in occurrences}
        occurrences_by_parent_number = defaultdict(list)
        for item in occurrences:
            occurrences_by_parent_number[(item.transect_id, item.occurrence_number)].append(item)
        workflows_by_uid = {str(item.uid): item for item in workflows}
        workflows_by_instance = defaultdict(list)
        for item in workflows:
            workflows_by_instance[(item.occurrence_id, item.instance_number)].append(item)
        transect_template_ids = {str(value).casefold() for value in TemplateTransect.objects.values_list("id", flat=True)}
        workflow_template_ids = {str(value).casefold() for value in TemplateWorkflow.objects.values_list("id", flat=True)}

        transect_deletions = {item.transect_uid: item for item in TransectDeletion.objects.all()}
        occurrence_deletions_id = {item.occurrence_id: item for item in OccurrenceDeletion.objects.all()}
        occurrence_deletions_key = {(item.transect_uid, item.occurrence_number): item for item in OccurrenceDeletion.objects.all()}
        instance_deletions = {(item.occurrence_id, item.instance_number): item for item in InstanceDeletion.objects.all() if item.restoration_status != "restored"}
        logged_transect_keys = {entry["uid"] for item in parsed for entry in item.transects if entry.get("uid") is not None}
        logged_occurrence_keys = {entry["id"] for item in parsed for entry in item.occurrences if entry.get("id") is not None}
        logged_workflow_keys = {entry["workflow_uid"] for item in parsed for entry in item.instances if entry.get("workflow_uid")}
        historical_transects = set(CompletedTransect.history.filter(uid__in=logged_transect_keys).values_list("uid", flat=True).distinct())
        historical_occurrences = set(CompletedOccurrence.history.filter(id__in=logged_occurrence_keys).values_list("id", flat=True).distinct())
        historical_workflows = set(str(uid) for uid in CompletedWorkflow.history.filter(uid__in=logged_workflow_keys).values_list("uid", flat=True).distinct())
        for item in transect_deletions.values():
            rows["Deleted evidence"].append(["Transect", item.transect_uid, "", item.deleted_at, item.reason, "TransectDeletion"])
        for item in occurrence_deletions_id.values():
            rows["Deleted evidence"].append(["Occurrence", item.occurrence_id, item.transect_uid, item.deleted_at, item.reason, "OccurrenceDeletion"])
        for item in instance_deletions.values():
            rows["Deleted evidence"].append(["Instance", item.instance_number, item.occurrence_id, item.deleted_at, item.reason, "InstanceDeletion"])

        logged_transect_ids, logged_occurrence_ids, logged_workflow_ids = set(), set(), set()
        logged_transect_years = {}
        log_occurrence_counts = Counter()
        log_instance_counts = Counter()
        log_track_counts = Counter()
        all_logged_occurrences = [entry for item in parsed for entry in item.occurrences]
        all_logged_instances = [entry for item in parsed for entry in item.instances]
        for item in parsed:
            for entry in item.transects:
                if entry.get("uid") is not None and entry.get("start_time"):
                    logged_transect_years[entry["uid"]] = entry["start_time"].year
            for point in item.track_points:
                log_track_counts[point["transect_uid"]] += 1
            # A link is strong import evidence even when an old payload lacks a recognizable wrapper.
            existing = {entry["uid"] for entry in item.transects}
            for uid in links[item.log_id] - existing:
                item.transects.append({"log_id": item.log_id, "uid": uid, "name": None, "start_time": None, "source": "xTransectDataLog"})

        selected_transect_scope = {
            entry["uid"] for item in parsed for entry in item.transects
            if entry.get("uid") is not None
        }
        cancelled_transects = {entry["uid"] for item in parsed for entry in item.transects if entry.get("state") == "cancelled"}

        for entry in all_logged_occurrences:
            log_occurrence_counts[entry["transect_uid"]] += 1
        logged_instances_by_occurrence = defaultdict(list)
        for entry in all_logged_instances:
            key = entry["occurrence_id"] or (entry["transect_uid"], entry["occurrence_number"])
            log_instance_counts[key] += 1
            logged_instances_by_occurrence[key].append(entry)

        for entry in [entry for item in parsed for entry in item.transects]:
            year = entry.get("start_time").year if entry.get("start_time") else None
            if not self._in_year(year, options):
                continue
            current = by_transect.get(entry["uid"])
            deleted = transect_deletions.get(entry["uid"])
            if deleted:
                continue
            if entry.get("state") == "cancelled":
                status, confidence, reason = "LOG_CANCELLED", "Exact", "Transect was cancelled in the field log"
            elif current:
                status, confidence, reason = "CURRENT_EXACT", "Exact", "Matched by transect UID"
                logged_transect_ids.add(current.uid)
            elif entry["uid"] in historical_transects:
                status, confidence, reason = "HISTORICAL_ONLY", "Exact", "Transect UID exists only in django-simple-history"
            else:
                candidates = [t for t in transects if entry.get("name") and t.name.strip().casefold() == str(entry["name"]).strip().casefold()]
                if len(candidates) == 1:
                    current = candidates[0]; status, confidence, reason = "CURRENT_PROBABLE", "Probable", "Unique normalized name match"; logged_transect_ids.add(current.uid)
                elif len(candidates) > 1:
                    status, confidence, reason = "AMBIGUOUS", "None", f"Multiple name matches: {[t.uid for t in candidates]}"
                else:
                    status, confidence, reason = "MISSING", "None", "Logged transect not found in current or deletion tables"
            db_uid = current.uid if current else None
            db_occurrences = sum(1 for occurrence in occurrences if occurrence.transect_id == db_uid)
            gps = gps_status(year or (current.start_time.year if current else None), track_counts[db_uid], log_track_counts[entry["uid"]], options["gps_required_from_year"])
            transect_name = entry.get("name") or (current.name if current else "")
            field_label = f"Transect {transect_name} (UID {entry['uid']})" if transect_name else f"Transect UID {entry['uid']}"
            rows["Transects"].append([entry["log_id"], entry["uid"], db_uid, transect_name, year, status, confidence, log_occurrence_counts[entry["uid"]], db_occurrences, gps, bool(deleted), reason, field_label])
            if status != "CURRENT_EXACT":
                template_ok = str(entry.get("template") or "").casefold() in transect_template_ids
                if status == "LOG_CANCELLED":
                    recovery, blocker = "CANCELLED_IN_LOG", "Field log explicitly cancelled this transect."
                elif status == "DELETED_CONFIRMED":
                    recovery, blocker = "INTENTIONALLY_DELETED", "Permanent deletion audit blocks automatic recovery."
                elif status == "HISTORICAL_ONLY":
                    recovery, blocker = "REVIEW_REQUIRED", "Historical record exists; determine whether absence is intentional."
                elif not template_ok:
                    recovery, blocker = "TEMPLATE_NOT_FOUND", "Logged transect template is not present in current configuration."
                else:
                    recovery, blocker = "REVIEW_REQUIRED", "Transect naming, distance, angle, and derived fields require an approved import rule."
                rows["Recovery candidates"].append(["Transect", field_label, recovery, "High" if status in {"LOG_CANCELLED", "DELETED_CONFIRMED"} else "Review", entry["log_id"], entry.get("source"), "", 1, bool(current), bool(deleted) or status == "HISTORICAL_ONLY", blocker, entry.get("start_time"), entry.get("lat_from"), entry.get("long_from"), entry["uid"]])
            if status in ("MISSING", "AMBIGUOUS", "DELETED_CONFIRMED"):
                rows["Critical findings"].append(["Critical" if status == "MISSING" else "Warning", "Transect", status, entry["log_id"], entry["uid"], reason, "Current and deletion audit tables checked"])

        for entry in all_logged_occurrences:
            if not self._in_year(logged_transect_years.get(entry["transect_uid"]), options):
                continue
            key = entry["id"] or (entry["transect_uid"], entry["number"])
            candidates = []
            if entry["id"] in occurrences_by_id:
                candidates = [occurrences_by_id[entry["id"]]]
            elif entry["transect_uid"] is not None and entry["number"] is not None:
                candidates = occurrences_by_parent_number[(entry["transect_uid"], entry["number"])]
            deleted = occurrence_deletions_id.get(entry["id"]) or occurrence_deletions_key.get((entry["transect_uid"], entry["number"]))
            parent_deleted = transect_deletions.get(entry["transect_uid"])
            alias_current = cross_device_occurrence_candidate(
                entry, all_logged_occurrences, occurrences_by_parent_number,
            ) if not deleted else None
            merged_current = merged_occurrence_candidate(
                entry, logged_instances_by_occurrence[key], workflows_by_uid,
                occurrences_by_id,
            ) if not deleted and not candidates else None
            if omit_logged_occurrence(
                entry, log_instance_counts[key], cancelled_transects,
                deleted, parent_deleted, merged_current, alias_current,
            ):
                continue
            if entry.get("state") == "cancelled":
                current = None; status, confidence, reason = "LOG_CANCELLED", "Exact", "Occurrence was cancelled in the field log"
            elif alias_current:
                current = alias_current
                status, confidence = "CURRENT_EXACT", "Exact"
                reason = "Matched cross-device occurrence alias by unique time and coordinates"
                logged_occurrence_ids.add(current.id)
            elif len(candidates) == 1:
                current = candidates[0]; status, confidence, reason = "CURRENT_EXACT", "Exact", "Matched by occurrence ID or transect and occurrence number"; logged_occurrence_ids.add(current.id)
            elif len(candidates) > 1:
                current = None; status, confidence, reason = "AMBIGUOUS", "None", f"Multiple candidates: {[x.id for x in candidates]}"
            elif deleted:
                current = None; status, confidence, reason = "DELETED_CONFIRMED", "Exact", "Matched permanent occurrence deletion evidence"
            elif merged_current:
                current = merged_current; status, confidence, reason = "CURRENT_EXACT", "Exact", "Matched current occurrence via all logged workflow UIDs after an occurrence merge"; logged_occurrence_ids.add(current.id)
            elif parent_deleted:
                current = None; status, confidence, reason = "DELETED_CONFIRMED", "Exact", "Matched permanent parent transect deletion evidence"
            elif entry["id"] in historical_occurrences:
                current = None; status, confidence, reason = "HISTORICAL_ONLY", "Exact", "Occurrence ID exists only in django-simple-history"
            else:
                current = None; status, confidence, reason = "MISSING", "None", "Logged occurrence not found in current or deletion tables"
            db_instances = len({w.instance_number for w in workflows if current and w.occurrence_id == current.id})
            parent = by_transect.get(entry["transect_uid"])
            parent_label = parent.name if parent else f"UID {entry['transect_uid']}"
            field_label = f"Transect {parent_label} — occurrence {entry['number']}"
            rows["Occurrences"].append([entry["log_id"], entry["transect_uid"], entry["id"], entry["number"], current.id if current else None, status, confidence, log_instance_counts[key], db_instances, bool(deleted or parent_deleted), reason, field_label])
            if status != "CURRENT_EXACT":
                complete = all(value is not None for value in (entry.get("number"), entry.get("start_time"), entry.get("lat"), entry.get("long"))) and entry.get("state") == "completed"
                parent_exists = entry["transect_uid"] in by_transect
                if status == "LOG_CANCELLED" or logged_parent_transect_cancelled(entry, cancelled_transects):
                    recovery, blocker = "CANCELLED_IN_LOG", "Field log explicitly cancelled this occurrence."
                elif status == "DELETED_CONFIRMED":
                    recovery, blocker = "INTENTIONALLY_DELETED", "Permanent deletion audit blocks automatic recovery."
                elif status == "HISTORICAL_ONLY":
                    recovery, blocker = "REVIEW_REQUIRED", "Historical record exists; determine whether absence is intentional."
                elif not complete:
                    recovery, blocker = "INSUFFICIENT_LOG_DATA", "Occurrence lacks a completed state, coordinates, number, or start time."
                elif not parent_exists:
                    recovery, blocker = "READY_AFTER_PARENT", "Import or approve the parent transect first."
                else:
                    recovery, blocker = "READY_FOR_IMPORT", "Required occurrence values and current parent transect are available."
                rows["Recovery candidates"].append(["Occurrence", field_label, recovery, "High" if recovery.startswith("READY") else "Review", entry["log_id"], entry.get("source"), f"Transect {entry['transect_uid']}", 4, bool(current), bool(deleted or parent_deleted) or status == "HISTORICAL_ONLY", blocker, entry.get("start_time"), entry.get("lat"), entry.get("long"), entry.get("id") or entry.get("number")])
            if status in ("MISSING", "AMBIGUOUS", "DELETED_CONFIRMED", "HISTORICAL_ONLY"):
                rows["Critical findings"].append(["Critical" if status == "MISSING" else "Warning", "Occurrence", status, entry["log_id"], entry["id"] or entry["number"], reason, f"Transect {entry['transect_uid']}"])

        for entry in all_logged_instances:
            if not self._in_year(logged_transect_years.get(entry["transect_uid"]), options):
                continue
            occurrence = occurrences_by_id.get(entry["occurrence_id"])
            if not occurrence and entry["transect_uid"] is not None:
                candidates = occurrences_by_parent_number[(entry["transect_uid"], entry["occurrence_number"])]
                occurrence = candidates[0] if len(candidates) == 1 else None
            candidates = [workflows_by_uid[entry["workflow_uid"]]] if entry["workflow_uid"] in workflows_by_uid else (workflows_by_instance[(occurrence.id, entry["number"])] if occurrence and entry["number"] is not None else [])
            deleted = instance_deletions.get((occurrence.id, entry["number"])) if occurrence else None
            parent_deleted = transect_deletions.get(entry["transect_uid"])
            if omit_logged_instance(
                entry, cancelled_transects, deleted, parent_deleted, candidates,
            ):
                continue
            if entry.get("parent_occurrence", {}).get("state") == "cancelled":
                status, confidence, reason = "LOG_CANCELLED", "Exact", "Parent occurrence was cancelled in the field log"
                candidates = []
            elif candidates:
                status, confidence, reason = "CURRENT_EXACT", "Exact", "Matched workflow UID or logical occurrence instance"
                logged_workflow_ids.update(str(item.uid) for item in candidates)
            elif deleted:
                status, confidence, reason = "DELETED_CONFIRMED", "Exact", "Matched permanent instance deletion evidence"
            elif parent_deleted:
                status, confidence, reason = "DELETED_CONFIRMED", "Exact", "Matched permanent parent transect deletion evidence"
            elif entry["workflow_uid"] and entry["workflow_uid"] in historical_workflows:
                status, confidence, reason = "HISTORICAL_ONLY", "Exact", "Workflow UID exists only in django-simple-history"
            else:
                status, confidence, reason = "MISSING", "None", "Logged instance not found in current or deletion tables"
            parent = by_transect.get(entry["transect_uid"])
            parent_label = parent.name if parent else f"UID {entry['transect_uid']}"
            field_label = f"Transect {parent_label} — occurrence {entry['occurrence_number']} — instance {entry['number']}"
            rows["Instances"].append([entry["log_id"], entry["transect_uid"], entry["occurrence_id"], entry["occurrence_number"], entry["number"], entry["workflow_uid"], [str(x.uid) for x in candidates], status, confidence, sum(response_counts[str(x.uid)] for x in candidates), bool(deleted or parent_deleted), reason, field_label])
            if status != "CURRENT_EXACT":
                template_ok = str(entry.get("template") or "").casefold() in workflow_template_ids
                source_complete = entry.get("state") == "completed" and entry.get("response_count", 0) > 0 and bool(entry.get("parent_occurrence", {}).get("user"))
                if status == "LOG_CANCELLED" or logged_parent_transect_cancelled(entry, cancelled_transects):
                    recovery, blocker = "CANCELLED_IN_LOG", "Parent occurrence was cancelled in the field log."
                elif status == "DELETED_CONFIRMED":
                    recovery, blocker = "INTENTIONALLY_DELETED", "Permanent instance deletion audit blocks automatic recovery."
                elif status == "HISTORICAL_ONLY":
                    recovery, blocker = "REVIEW_REQUIRED", "Historical workflow exists; determine whether absence is intentional."
                elif not template_ok:
                    recovery, blocker = "TEMPLATE_NOT_FOUND", "Logged workflow template is not present in current configuration."
                elif not source_complete:
                    recovery, blocker = "INSUFFICIENT_LOG_DATA", "Workflow completion, collector, or response evidence is incomplete."
                elif not occurrence:
                    recovery, blocker = "READY_AFTER_PARENT", "Import or approve the parent occurrence first."
                else:
                    recovery, blocker = "READY_FOR_IMPORT", "Workflow identity, template, collector, responses, and current parent are available."
                rows["Recovery candidates"].append(["Instance", field_label, recovery, "High" if recovery.startswith("READY") else "Review", entry["log_id"], entry.get("source"), f"Occurrence {entry['occurrence_id'] or entry['occurrence_number']}", 6, bool(candidates), bool(deleted or parent_deleted) or status == "HISTORICAL_ONLY", blocker, None, None, None, entry.get("workflow_uid")])
            if status in ("MISSING", "AMBIGUOUS", "DELETED_CONFIRMED", "HISTORICAL_ONLY"):
                rows["Critical findings"].append(["Critical" if status == "MISSING" else "Warning", "Instance", status, entry["log_id"], entry["number"], reason, f"Occurrence {entry['occurrence_id'] or entry['occurrence_number']}"])

        seen_recovery_tracks = set()
        seen_recovery_track_slots = set()
        for item in parsed:
            for point in item.track_points:
                uid, event = point["transect_uid"], point.get("event") or "OTHER"
                if not self._in_year(logged_transect_years.get(uid), options):
                    continue
                # Pause/resume commands remain parsed evidence but have no
                # matching legacy database flag and are not recovery work.
                if not is_recoverable_track_event(event):
                    continue
                time = point.get("time")
                time_key = time.replace(tzinfo=None) if time and time.tzinfo else time
                lat, long = point.get("lat"), point.get("long")
                # These remain visible in source/deletion evidence, but are
                # not actionable recovery records.
                if uid in transect_deletions or not has_valid_track_coordinates(lat, long):
                    continue
                user = str(point.get("user") or "").strip().casefold()
                if lat is None or long is None:
                    key = (uid, user, time_key, lat, long, event)
                else:
                    key = (uid, user, time_key, round(float(lat), 8), round(float(long), 8), event)
                legacy_key = legacy_track_key(uid, user, time_key, lat, long, event)
                legacy_slot = legacy_track_slot_key(uid, user, time_key, event)
                if (key in database_track_keys or legacy_key in database_legacy_track_keys
                        or legacy_slot in database_legacy_track_slots
                        or key in seen_recovery_tracks
                        or legacy_slot in seen_recovery_track_slots):
                    continue
                seen_recovery_tracks.add(key)
                seen_recovery_track_slots.add(legacy_slot)
                parent = by_transect.get(uid)
                if uid in cancelled_transects:
                    recovery, blocker = "CANCELLED_IN_LOG", "Parent transect was cancelled in the field log."
                elif uid in transect_deletions:
                    recovery, blocker = "INTENTIONALLY_DELETED", "Parent transect has permanent deletion evidence."
                elif uid in historical_transects and not parent:
                    recovery, blocker = "REVIEW_REQUIRED", "Parent transect exists only in history."
                elif not time or not point.get("user"):
                    recovery, blocker = "INSUFFICIENT_LOG_DATA", "GPS point requires a timestamp and collector."
                elif not parent:
                    recovery, blocker = "READY_AFTER_PARENT", "Import or approve the parent transect first."
                else:
                    recovery, blocker = "READY_FOR_IMPORT", "Complete unique GPS evidence and current parent transect are available."
                parent_name = parent.name if parent else f"UID {uid}"
                field_label = f"Transect {parent_name} — {event.casefold()} at {time or 'unknown time'}"
                rows["Recovery candidates"].append(["GPS point", field_label, recovery, "High" if recovery.startswith("READY") else "Review", point["log_id"], point.get("source"), f"Transect {uid}", 3, False, uid in transect_deletions or (uid in historical_transects and not parent), blocker, time, lat, long, event])

        for transect in transects:
            year = transect.start_time.year if transect.start_time else None
            if not self._in_year(year, options):
                continue
            if options.get("log_ids") and transect.uid not in selected_transect_scope:
                continue
            status = gps_status(year, track_counts[transect.uid], log_track_counts[transect.uid], options["gps_required_from_year"])
            reason = "Track points present" if status == "GPS_PRESENT" else "No database track points"
            rows["GPS"].append([transect.uid, transect.name, year, track_counts[transect.uid], log_track_counts[transect.uid], status, reason, f"Transect {transect.name} (UID {transect.uid})"])
            if status == "GPS_MISSING":
                rows["Critical findings"].append(["Critical", "GPS", status, "", transect.uid, reason, f"Year {year}"])
            if transect.uid not in logged_transect_ids:
                rows["Database only"].append(["Transect", transect.uid, "", "No successfully parsed log match; not proof that the record is erroneous"])
        for occurrence in occurrences:
            if options.get("log_ids") and occurrence.transect_id not in selected_transect_scope:
                continue
            parent = by_transect.get(occurrence.transect_id)
            year = parent.start_time.year if parent and parent.start_time else None
            if not self._in_year(year, options):
                continue
            if occurrence.id not in logged_occurrence_ids:
                rows["Database only"].append(["Occurrence", occurrence.id, occurrence.transect_id, "No successfully parsed log match; not proof that the record is erroneous"])
        for workflow in workflows:
            occurrence = occurrences_by_id.get(workflow.occurrence_id)
            if options.get("log_ids") and (not occurrence or occurrence.transect_id not in selected_transect_scope):
                continue
            parent = by_transect.get(occurrence.transect_id) if occurrence else None
            year = parent.start_time.year if parent and parent.start_time else None
            if not self._in_year(year, options):
                continue
            if str(workflow.uid) not in logged_workflow_ids:
                rows["Database only"].append(["Workflow", workflow.uid, workflow.occurrence_id, "No successfully parsed log match; logical instances may contain multiple workflows"])
        return rows

    @staticmethod
    def _in_year(year, options):
        return not year or ((not options["from_year"] or year >= options["from_year"]) and (not options["to_year"] or year <= options["to_year"]))

    @staticmethod
    def _methodology(options):
        return [
            ["Scope", "Read-only comparison of stored log contents, current completed tables, link records, and permanent deletion audits."],
            ["Transect match", "Exact UID/link first; unique normalized name is labelled probable; multiple candidates remain ambiguous."],
            ["Occurrence match", "Exact ID first, then unique cross-device time/coordinate aliases, then exact transect UID plus occurrence number."],
            ["Instance match", "Workflow UID first, then logical occurrence plus instance number. Multiple workflows may form one instance."],
            ["GPS cutoff", options["gps_required_from_year"] or "Not supplied; trackless records have unknown expectation."],
            ["Limitation", "Database-only does not mean erroneous: source logs may be missing, incomplete, or manually edited."],
            ["History limitation", "Permanent deletion audits were introduced later and cannot prove that an unmatched record never existed."],
            ["Recovery meaning", "Ready for import means the log contains sufficient structured evidence and dependencies; this report never writes data."],
            ["Recovery safeguards", "Cancelled records and permanent deletion evidence block automatic recovery. Existing GPS signatures are excluded from candidates."],
            ["GPS mapping", "Checkpoint and turnaround events have direct database flag mappings. Pause and resume events require review."],
        ]

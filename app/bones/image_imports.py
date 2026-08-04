from __future__ import annotations

import re
from pathlib import Path

from .models import CompletedOccurrence, CompletedTransect, CompletedWorkflow
from .models.images import safe_template_folder


def norm(value):
    value = " ".join(str(value).strip().split())
    return str(int(value)) if value.isdigit() else value.casefold()


def parse_filename(filename):
    stem = Path(filename).stem

    parts = stem.rsplit("_", 3)
    if (
        len(parts) == 4
        and parts[0]
        and all(part.isdigit() for part in parts[1:3])
        and re.fullmatch(r"\d+-\d+", parts[3])
    ):
        transect_name, uid, occurrence, instance_range = parts
        first, last = (int(value) for value in instance_range.split("-", 1))
        if first < 1 or last < first or last - first + 1 > 250:
            return "invalid_instance_range", {
                "transect_name": transect_name,
                "transect_uid": int(uid),
                "occurrence_number": int(occurrence),
                "instance_range": instance_range,
            }
        return "instance_range", {
            "transect_name": transect_name,
            "transect_uid": int(uid),
            "occurrence_number": int(occurrence),
            "instance_range": instance_range,
            "instance_numbers": list(range(first, last + 1)),
        }

    if len(parts) == 4 and parts[0] and all(part.isdigit() for part in parts[1:]):
        transect_name, uid, occurrence, instance = parts
        return "full_hierarchy", {
            "transect_name": transect_name,
            "transect_uid": int(uid),
            "occurrence_number": int(occurrence),
            "instance_number": int(instance),
        }

    parts = stem.split(".")
    if len(parts) >= 3 and parts[0].isdigit() and parts[-1].isdigit() and len(parts[-1]) == 2:
        return "historical_occurrence", {
            "occurrence_number": int(parts[0]),
            "transect_name": ".".join(parts[1:-1]),
            "year": 2000 + int(parts[-1]),
        }

    match = re.fullmatch(r"(.+)_(\d+)_(Start.*|Turn.*)", stem, re.IGNORECASE)
    if match:
        transect_name, uid, label = match.groups()
        return "transect_location", {
            "transect_name": transect_name,
            "transect_uid": int(uid),
            "photo_role": "start" if label.casefold().startswith("start") else "turn",
            "source_label": label,
        }
    return "unknown", {}


def canonical_metadata(transect):
    template_name = transect.transect_template.name if transect.transect_template else "Unknown template"
    return {
        "transect_name": transect.name,
        "template_name": template_name,
        "template_folder": safe_template_folder(template_name),
        "transect_uid": transect.pk,
        "transect_date": transect.start_time.date().isoformat() if transect.start_time else "unknown-date",
    }


def _transect_name_matches(transect, name):
    return norm(transect.name) == norm(name)


def resolve_filename(filename):
    schema, data = parse_filename(filename)
    result = {"filename": filename, "schema": schema, "metadata": data, "status": "invalid", "candidates": []}
    if schema in {"unknown", "invalid_instance_range"}:
        return result

    source_transect_name = data.get("transect_name", "")
    if schema in {"full_hierarchy", "instance_range", "transect_location"}:
        try:
            transect = CompletedTransect.objects.select_related("transect_template").get(pk=data["transect_uid"])
        except CompletedTransect.DoesNotExist:
            result["status"] = "unmatched"
            return result
        if not _transect_name_matches(transect, source_transect_name):
            result["status"] = "transect_name_mismatch"
            result["actual_transect_name"] = transect.name
            result["actual_template_name"] = transect.transect_template.name if transect.transect_template else "Unknown template"
            result["transect_uid"] = transect.pk
            return result
        data["source_transect_name"] = source_transect_name
        data.update(canonical_metadata(transect))
        if schema == "transect_location":
            result.update(status="ready", entity_type="transect", entity_id=str(transect.pk))
            return result
        try:
            occurrence = CompletedOccurrence.objects.get(
                transect=transect, occurrence_number=data["occurrence_number"]
            )
        except CompletedOccurrence.DoesNotExist:
            result["status"] = "unmatched"
            return result
        if schema == "instance_range":
            requested = data["instance_numbers"]
            existing = set(
                CompletedWorkflow.objects.filter(
                    occurrence=occurrence,
                    instance_number__in=requested,
                ).values_list("instance_number", flat=True)
            )
            missing = [number for number in requested if number not in existing]
            if missing:
                result["status"] = "missing_instances"
                result["missing_instances"] = missing
                return result
            data["occurrence_id"] = occurrence.pk
            result.update(
                status="ready",
                entity_type="occurrence",
                entity_id=str(occurrence.pk),
                targets=[
                    {"entity_type": "instance", "entity_id": f"{occurrence.pk}:{number}"}
                    for number in requested
                ],
            )
            return result
        if not CompletedWorkflow.objects.filter(
            occurrence=occurrence, instance_number=data["instance_number"]
        ).exists():
            result["status"] = "unmatched"
            return result
        data["occurrence_id"] = occurrence.pk
        result.update(
            status="ready",
            entity_type="instance",
            entity_id=f"{occurrence.pk}:{data['instance_number']}",
        )
        return result

    candidates = []
    queryset = CompletedOccurrence.objects.select_related(
        "transect__transect_template"
    ).filter(
        occurrence_number=data["occurrence_number"],
        transect__start_time__year=data["year"],
    )
    for occurrence in queryset:
        if _transect_name_matches(occurrence.transect, source_transect_name):
            metadata = canonical_metadata(occurrence.transect)
            candidates.append(
                {
                    "id": occurrence.pk,
                    "label": f"Transect {metadata['transect_name']} — template {metadata['template_name']} — {metadata['transect_date']} — UID {occurrence.transect_id}, occurrence {occurrence.occurrence_number}",
                    **metadata,
                }
            )
    result["candidates"] = candidates
    if len(candidates) == 1:
        candidate = candidates[0]
        data.update(candidate)
        data["occurrence_id"] = candidate["id"]
        data["source_transect_name"] = source_transect_name
        result.update(status="ready", entity_type="occurrence", entity_id=str(candidate["id"]))
    elif candidates:
        result["status"] = "ambiguous"
    else:
        result["status"] = "unmatched"
    return result

"""Transect effort and occurrence detection detail report."""
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..models import (CompletedOccurrence, CompletedOccurrenceInfo,
                      CompletedWorkflow)
from .mni_service import build_report, clean, rows_in_batches


ASSUMED_SEARCH_WIDTH_M = 50

CALCULATION_RULES = (
    "Population: all completed transects and their completed occurrences are eligible, including 2008 and every 2024 habitat. User-selected report filters are then applied.",
    "Habitat and Old reserve: the unique Pre responses to 'Transect physical habitat' and 'On old reserve?'. Conflicting or missing values are left blank.",
    "Sector: Eastern when Old reserve is Yes, Western when Old reserve is No, otherwise blank.",
    "Coordinates: recorded latitude and longitude from CompletedTransects and CompletedOccurrences; turn coordinates may be blank.",
    "Search width: 50 m for every transect. This is an analytical assumption, not a historically recorded field.",
    "Occurrence count: eligible completed occurrences belonging to the transect.",
    "Bone NISP: completed Bone workflow instances belonging to eligible completed occurrences.",
    "Dentition specimen count: completed Dentition workflow instances belonging to eligible completed occurrences.",
    "Calculated MNI: existing MNI rules applied independently per transect and summed across taxa; taxa selected in Excluded taxa do not contribute.",
    "Occurrence attributes: Post responses are preferred over Pre responses when both exist; otherwise the available Pre response is used.",
    "Excluded taxa: none are selected by default, so an unfiltered report includes every eligible occurrence. If a user explicitly selects taxa, matching canonical occurrence-detail rows are omitted; transect-level effort counts remain totals, while Calculated MNI also applies the explicit exclusions.",
    "Recording time: occurrence recording start time.",
    "Missing or blank Scatter diameter is treated as numeric 0.",
    "Other missing values are exported as blank and are not imputed, except for the explicitly assumed 50 m search width.",
)


@dataclass
class TransectDetectionResult:
    transect_headers: list[str]
    transect_rows: list[list]
    occurrence_headers: list[str]
    occurrence_rows: list[list]
    warnings: list[str] = field(default_factory=list)


def _answer(mapping, question):
    return clean(mapping.get(f"post: {question}".casefold())) or clean(
        mapping.get(f"pre: {question}".casefold())
    )


def build_transect_detection_report(cleaned_data, note_filters=()):
    mni_result, transects, _ = build_report(
        cleaned_data, note_filters, apply_population_rules=False
    )
    occurrence_ids = list(mni_result.occurrence_metadata)
    occurrences = rows_in_batches(
        CompletedOccurrence.objects.filter(state__iexact="Completed"),
        "pk", occurrence_ids,
    )
    occurrence_by_id = {row.pk: row for row in occurrences}
    occurrence_info = defaultdict(dict)
    info_rows = rows_in_batches(
        CompletedOccurrenceInfo.objects.values(
            "occurrence_id", "pre_or_post", "question_text", "response"
        ),
        "occurrence_id", occurrence_ids,
    )
    for row in info_rows:
        key = f'{row["pre_or_post"]}: {row["question_text"]}'.casefold()
        occurrence_info[row["occurrence_id"]][key] = row["response"]

    workflows = rows_in_batches(
        CompletedWorkflow.objects.filter(
            template_workflow__name__in=("Bone", "Dentition")
        ).select_related("template_workflow"),
        "occurrence_id", occurrence_ids,
    )
    bone_by_transect = Counter()
    teeth_by_transect = Counter()
    bone_by_occurrence = Counter()
    teeth_by_occurrence = Counter()
    for workflow in workflows:
        occurrence = occurrence_by_id.get(workflow.occurrence_id)
        if not occurrence:
            continue
        target_transect = bone_by_transect if workflow.template_workflow.name.casefold() == "bone" else teeth_by_transect
        target_occurrence = bone_by_occurrence if workflow.template_workflow.name.casefold() == "bone" else teeth_by_occurrence
        target_transect[occurrence.transect_id] += 1
        target_occurrence[occurrence.pk] += 1

    occurrence_count = Counter(row.transect_id for row in occurrences)
    mni_by_transect = Counter()
    for row in mni_result.transect_rows:
        mni_by_transect[row["transect_id"]] += row["mni"]
    transect_headers = [
        "Transect UID", "Transect name", "Date", "Year", "Habitat",
        "Old reserve", "Sector", "State", "Start latitude",
        "Start longitude", "Turn latitude", "Turn longitude", "End latitude",
        "End longitude", "Recorded distance (km)", "Search width (m, assumed)",
        "Occurrence count", "Bone NISP", "Dentition specimen count",
        "Calculated MNI",
    ]
    transect_rows = []
    for transect in transects:
        metadata = mni_result.transect_metadata.get(transect.pk, {})
        reserve = clean(metadata.get("reserve"))
        transect_rows.append([
            transect.pk, transect.name, transect.start_time.date() if transect.start_time else None,
            transect.start_time.year if transect.start_time else None,
            metadata.get("habitat", ""), reserve,
            "Eastern" if reserve.casefold() == "yes" else "Western" if reserve.casefold() == "no" else "",
            transect.state,
            transect.lat_from, transect.long_from, transect.lat_turn, transect.long_turn,
            transect.lat_to, transect.long_to, transect.distance_km,
            ASSUMED_SEARCH_WIDTH_M,
            occurrence_count[transect.pk], bone_by_transect[transect.pk],
            teeth_by_transect[transect.pk], mni_by_transect[transect.pk],
        ])

    occurrence_headers = [
        "Transect UID", "Occurrence ID", "Occurrence number", "Latitude",
        "Longitude", "Recording time", "Distance spotted", "Taxon",
        "Size class", "Age", "Sex", "Patch of bones?", "Scatter diameter",
        "Bone specimen count", "Dentition specimen count",
    ]
    occurrence_rows = []
    excluded_taxa = {
        clean(value).casefold() for value in cleaned_data.get("excluded_taxa", [])
    }
    for occurrence in sorted(occurrences, key=lambda row: (row.transect_id, row.occurrence_number, row.pk)):
        details = occurrence_info[occurrence.pk]
        taxon = mni_result.occurrence_metadata.get(occurrence.pk, {}).get("taxon") or _answer(details, "Taxon Guess?") or _answer(details, "Taxon")
        if clean(taxon).casefold() in excluded_taxa:
            continue
        occurrence_rows.append([
            occurrence.transect_id, occurrence.pk, occurrence.occurrence_number,
            occurrence.lat, occurrence.long, occurrence.recording_start_time,
            _answer(details, "Distance spotted"),
            taxon,
            _answer(details, "Size class"), _answer(details, "Age"),
            _answer(details, "Sex"), _answer(details, "Patch of Bones?"),
            _answer(details, "Scatter Diameter") or 0,
            bone_by_occurrence[occurrence.pk],
            teeth_by_occurrence[occurrence.pk],
        ])
    return TransectDetectionResult(
        transect_headers, transect_rows, occurrence_headers, occurrence_rows
    )

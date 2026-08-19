"""Habitat-level weathering and taphonomic report calculations."""
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..models import CompletedResponse, CompletedWorkflow
from .mni_service import build_report, clean, rows_in_batches


WEATHERING_STAGES = (
    "0", "0-1", "1", "1-2", "2", "2-3",
    "3", "3-4", "4", "4-5", "5", "6",
)
SURVEY_WIDTH_KM = 0.05

CALCULATION_RULES = (
    "Population: completed transects and completed occurrences only; 2008 transects are excluded, and in 2024 only shrubs closed habitat is retained. All selected report filters are then applied.",
    "Habitats: the Pre response to 'Transect physical habitat'. A transect with a missing or conflicting habitat contributes only to All.",
    "# transects: distinct eligible completed transects.",
    "Distance covered (km): sum of CompletedTransect.distance_km for eligible transects.",
    "km² covered: distance covered multiplied by the 0.05 km (50 m) survey width.",
    "Count of occurrences: distinct eligible completed occurrences, including occurrences belonging to taxa excluded from the MNI calculation.",
    "MNI: calculated independently per transect with the existing MNI rules and then summed. Taxa selected in Excluded taxa do not contribute to MNI.",
    "MNI/km²: MNI divided by km² covered.",
    "NISP (# of bones): number of Bone workflow instances belonging to eligible completed occurrences.",
    "NISP/km²: NISP divided by km² covered.",
    "Each weathering percentage: Bone workflow instances whose original 'Weathering class' response exactly matches that stage, divided by NISP, multiplied by 100. Missing or unrecognised stages remain in the NISP denominator.",
    "% bones part buried: Bone workflow instances with 'Buried?' equal to Yes, divided by NISP, multiplied by 100.",
    "% bones with any carnivore damage: Bone workflow instances with 'Carnivore damage' greater than zero, any 'Carn Damage 1–6 Level' greater than zero, or any populated 'Carn Damage 1–6 Portion', divided by NISP, multiplied by 100. A workflow is counted at most once.",
    "All: values are recalculated from all eligible records; percentages and densities are not averages of the habitat columns.",
    "Zero denominators: densities and percentages are displayed as 0.00.",
)


@dataclass
class WeatheringReportResult:
    habitats: list[str]
    rows: list[dict]
    warnings: list[str] = field(default_factory=list)


def _positive_number(value):
    try:
        return float(clean(value)) > 0
    except (TypeError, ValueError):
        return False


def _has_carnivore_damage(answers):
    if _positive_number(answers.get("carnivore damage")):
        return True
    for number in range(1, 7):
        if _positive_number(answers.get(f"carn damage {number} level")):
            return True
        if clean(answers.get(f"carn damage {number} portion")):
            return True
    return False


def _percent(numerator, denominator):
    return 100 * numerator / denominator if denominator else 0.0


def _density(numerator, area):
    return numerator / area if area else 0.0


def _cells(counter, columns):
    return [counter.get(column, 0) for column in columns]


def build_weathering_report(cleaned_data, note_filters=()):
    """Build the matrix using the same eligible population as the MNI report."""
    mni_result, transects, _ = build_report(cleaned_data, note_filters)
    habitat_by_transect = {
        transect.pk: clean(mni_result.transect_metadata[transect.pk].get("habitat"))
        for transect in transects
    }
    habitats = sorted(
        {value for value in habitat_by_transect.values() if value}, key=str.casefold
    )
    columns = habitats + ["All"]

    transect_count = Counter({"All": len(transects)})
    distance = Counter({"All": sum(float(row.distance_km or 0) for row in transects)})
    for transect in transects:
        habitat = habitat_by_transect[transect.pk]
        if habitat:
            transect_count[habitat] += 1
            distance[habitat] += float(transect.distance_km or 0)
    area = Counter({column: distance[column] * SURVEY_WIDTH_KM for column in columns})

    mni = Counter()
    for row in mni_result.transect_rows:
        habitat = habitat_by_transect.get(row["transect_id"], "")
        mni["All"] += row["mni"]
        if habitat:
            mni[habitat] += row["mni"]

    occurrence_count = Counter({"All": len(mni_result.occurrence_metadata)})
    for metadata in mni_result.occurrence_metadata.values():
        habitat = habitat_by_transect.get(metadata.get("transect_id"), "")
        if habitat:
            occurrence_count[habitat] += 1

    occurrence_ids = list(mni_result.occurrence_metadata)
    workflows = rows_in_batches(
        CompletedWorkflow.objects.filter(
            template_workflow__name__iexact="Bone"
        ).select_related("occurrence"),
        "occurrence_id", occurrence_ids,
    )
    workflow_ids = [row.pk for row in workflows]
    response_rows = rows_in_batches(
        CompletedResponse.objects.filter(skipped=False).values(
            "workflow_id", "question_text", "response"
        ),
        "workflow_id", workflow_ids,
    )
    answers = defaultdict(dict)
    for response in response_rows:
        answers[response["workflow_id"]][response["question_text"].casefold()] = response["response"]

    nisp = Counter()
    buried = Counter()
    carnivore = Counter()
    weathering = defaultdict(Counter)
    unknown_weathering = Counter()
    for workflow in workflows:
        habitat = habitat_by_transect.get(workflow.occurrence.transect_id, "")
        groups = ["All"] + ([habitat] if habitat else [])
        values = answers[workflow.pk]
        stage = clean(values.get("weathering class"))
        for group in groups:
            nisp[group] += 1
            if stage in WEATHERING_STAGES:
                weathering[stage][group] += 1
            else:
                unknown_weathering[group] += 1
            if clean(values.get("buried?")).casefold() == "yes":
                buried[group] += 1
            if _has_carnivore_damage(values):
                carnivore[group] += 1

    rows = [
        {"label": "# transects", "kind": "integer", "values": _cells(transect_count, columns)},
        {"label": "km² covered", "kind": "decimal", "values": _cells(area, columns)},
        {"label": "distance covered (km)", "kind": "decimal", "values": _cells(distance, columns)},
        {"label": "Count of occurrences", "kind": "integer", "values": _cells(occurrence_count, columns)},
        {"label": "MNI", "kind": "integer", "values": _cells(mni, columns)},
        {"label": "MNI/km²", "kind": "decimal", "values": [_density(mni[c], area[c]) for c in columns]},
        {"label": "NISP (# of bones)", "kind": "integer", "values": _cells(nisp, columns)},
        {"label": "NISP/km²", "kind": "decimal", "values": [_density(nisp[c], area[c]) for c in columns]},
    ]
    rows.extend({
        "label": f"% bones W{stage}", "kind": "percent",
        "values": [_percent(weathering[stage][c], nisp[c]) for c in columns],
    } for stage in WEATHERING_STAGES)
    rows.extend([
        {"label": "% bones part buried", "kind": "percent", "values": [_percent(buried[c], nisp[c]) for c in columns]},
        {"label": "% bones with any carnivore damage", "kind": "percent", "values": [_percent(carnivore[c], nisp[c]) for c in columns]},
    ])
    warnings = []
    if unknown_weathering["All"]:
        warnings.append(
            f'{unknown_weathering["All"]} Bone workflow instance(s) have a missing or unrecognised Weathering class; they remain in the NISP denominator.'
        )
    return WeatheringReportResult(columns, rows, warnings)

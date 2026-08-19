"""Dentition tooth-type distribution by habitat."""
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..models import CompletedResponse, CompletedWorkflow
from .mni_service import build_report, clean, rows_in_batches


TOOTH_ROWS = (
    ("tooth indet", "indet"), ("C", "C"), ("I", "I"),
    ("I1", "I1"), ("I2", "I2"), ("I3", "I3"),
    ("M", "M"), ("M1", "M1"), ("M2", "M2"), ("M3", "M3"),
    ("PM", "PM"), ("PM2", "PM2"), ("PM3", "PM3"), ("PM4", "PM4"),
)
KNOWN_TYPES = {source.casefold() for _, source in TOOTH_ROWS}

CALCULATION_RULES = (
    "Population: completed transects and completed occurrences only; 2008 transects are excluded, and in 2024 only shrubs closed habitat is retained. All selected report filters are then applied.",
    "Habitats: the Pre response to 'Transect physical habitat'. A specimen with a missing or conflicting habitat contributes only to All.",
    "Number of specimens: number of Dentition workflow instances belonging to eligible completed occurrences.",
    "Tooth type per specimen: the non-skipped Dentition response to 'Tooth type?'. The source value 'indet' is displayed as 'tooth indet' to match Table 6.",
    "Each tooth-type percentage: Dentition workflow specimens matching that tooth type, divided by Number of specimens, multiplied by 100.",
    "Each Dentition workflow specimen contributes to at most one displayed tooth-type row.",
    "All: counts and percentages are recalculated from all eligible specimens; percentages are not averages of habitat columns.",
    "Missing, malformed, or configured tooth types not listed in Table 6 remain in the specimen denominator and are reported as data-quality warnings; they are not silently reassigned.",
    "Zero denominators: percentages are displayed as 0.00.",
)


@dataclass
class TeethDistributionResult:
    habitats: list[str]
    rows: list[dict]
    warnings: list[str] = field(default_factory=list)


def _percent(numerator, denominator):
    return 100 * numerator / denominator if denominator else 0.0


def build_teeth_distribution_report(cleaned_data, note_filters=()):
    mni_result, transects, _ = build_report(
        {**cleaned_data, "excluded_taxa": []}, note_filters
    )
    habitat_by_transect = {
        transect.pk: clean(mni_result.transect_metadata[transect.pk].get("habitat"))
        for transect in transects
    }
    habitats = sorted(
        {value for value in habitat_by_transect.values() if value}, key=str.casefold
    )
    columns = habitats + ["All"]
    workflows = rows_in_batches(
        CompletedWorkflow.objects.filter(
            template_workflow__name__iexact="Dentition"
        ).select_related("occurrence"),
        "occurrence_id", list(mni_result.occurrence_metadata),
    )
    response_rows = rows_in_batches(
        CompletedResponse.objects.filter(
            skipped=False, question_text__iexact="Tooth type?"
        ).values("workflow_id", "response"),
        "workflow_id", [row.pk for row in workflows],
    )
    type_by_workflow = {
        row["workflow_id"]: clean(row["response"]) for row in response_rows
    }
    specimens = Counter()
    tooth_types = defaultdict(Counter)
    unlisted = Counter()
    for workflow in workflows:
        habitat = habitat_by_transect.get(workflow.occurrence.transect_id, "")
        groups = ["All"] + ([habitat] if habitat else [])
        tooth_type = type_by_workflow.get(workflow.pk, "").casefold()
        for group in groups:
            specimens[group] += 1
            if tooth_type:
                tooth_types[tooth_type][group] += 1
        if tooth_type not in KNOWN_TYPES:
            unlisted[tooth_type or "<null>"] += 1

    rows = [{
        "label": "number of specimens", "kind": "count",
        "values": [specimens[column] for column in columns],
    }]
    rows.extend({
        "label": label, "kind": "percent",
        "values": [
            _percent(tooth_types[source.casefold()][column], specimens[column])
            for column in columns
        ],
    } for label, source in TOOTH_ROWS)
    warnings = [
        f"Unlisted tooth type '{value}' occurs in {count} specimen(s); it remains in the denominator but has no Table 6 row."
        for value, count in sorted(unlisted.items())
    ]
    return TeethDistributionResult(columns, rows, warnings)

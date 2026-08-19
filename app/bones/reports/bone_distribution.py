"""Bone element distribution by habitat."""
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..models import CompletedResponse, CompletedWorkflow
from .mni_service import build_report, clean, rows_in_batches


ELEMENT_GROUPS = (
    ("Skull Bones:", ("cranium",)),
    ("Facial Bones:", ("maxilla", "mandible", "hemi-mandible")),
    ("Horn and Shoulder Bones:", ("horn core", "scapula")),
    ("Pelvic Bones:", ("innominate", "hemi-innominate", "acetabulum", "illium")),
    ("Vertebral Column:", ("atlas", "axis", "cervical vertebra", "thoracic vertebra", "lumbar vertebra", "caudal vertebra", "sacrum", "vertebra", "coccyx")),
    ("Ribcage:", ("rib", "sternum")),
    ("Limb Bones (Upper Extremity):", ("femur", "humerus", "radioulna", "radius", "ulna")),
    ("Limb Bones (Lower Extremity):", ("tibia", "metacarpal", "metacarpal II", "metacarpal IV", "metatarsal", "metatarsal II", "metatarsal IV", "patella", "calcaneus", "astragalus", "naviculo-cuboid", "lunar", "pisiform", "magnum", "carpal indet", "tarsal indet", "fibula", "unciform", "cuneiform", "scaphoid", "external and middle cuneiform", "sesamoid")),
    ("Phalanges:", ("proximal forelimb phalanx", "intermediate forelimb phalanx", "distal forelimb phalanx", "proximal hindlimb phalanx", "intermediate hindlimb phalanx", "distal hindlimb phalanx", "proximal phalanx", "intermediate phalanx", "distal phalanx")),
    ("Unidentified Bones:", ("long bone indet", "long bone epiphysis", "long bone shaft", "bone non-identifiable", "long bone near epiphysis", "<null>")),
)

ALIASES = {"bone nonidentifiable": "bone non-identifiable"}
KNOWN_ELEMENTS = {element.casefold() for _, elements in ELEMENT_GROUPS for element in elements if element != "<null>"}

CALCULATION_RULES = (
    "Population: completed transects and completed occurrences only; 2008 transects are excluded, and in 2024 only shrubs closed habitat is retained. All selected report filters are then applied.",
    "Habitats: the Pre response to 'Transect physical habitat'. A specimen with a missing or conflicting habitat contributes only to All.",
    "Number of specimens: number of Bone workflow instances belonging to eligible completed occurrences.",
    "Element per specimen: the non-skipped response to 'What element is this?'. 'bone nonidentifiable' is displayed as 'bone non-identifiable' to match Table 5.",
    "Each element percentage: specimens matching that element divided by Number of specimens, multiplied by 100.",
    "<null>: Bone workflow specimens with a missing or blank 'What element is this?' response, divided by Number of specimens, multiplied by 100.",
    "Subheader rows such as 'Skull Bones:' and 'Facial Bones:' organise elements only; they do not calculate subtotals and have no numeric values.",
    "All: counts and percentages are recalculated from all eligible specimens; percentages are not averages of habitat columns.",
    "Configured or recorded elements not listed in Table 5 remain in the specimen denominator and are reported as data-quality warnings; they are not silently reassigned.",
    "Zero denominators: percentages are displayed as 0.00.",
)


@dataclass
class BoneDistributionResult:
    habitats: list[str]
    rows: list[dict]
    warnings: list[str] = field(default_factory=list)


def _percent(numerator, denominator):
    return 100 * numerator / denominator if denominator else 0.0


def build_bone_distribution_report(cleaned_data, note_filters=()):
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
    occurrence_ids = list(mni_result.occurrence_metadata)
    workflows = rows_in_batches(
        CompletedWorkflow.objects.filter(
            template_workflow__name__iexact="Bone"
        ).select_related("occurrence"),
        "occurrence_id", occurrence_ids,
    )
    response_rows = rows_in_batches(
        CompletedResponse.objects.filter(
            skipped=False, question_text__iexact="What element is this?"
        ).values("workflow_id", "response"),
        "workflow_id", [row.pk for row in workflows],
    )
    element_by_workflow = {
        row["workflow_id"]: clean(row["response"]) for row in response_rows
    }
    specimens = Counter()
    elements = defaultdict(Counter)
    unlisted = Counter()
    for workflow in workflows:
        habitat = habitat_by_transect.get(workflow.occurrence.transect_id, "")
        groups = ["All"] + ([habitat] if habitat else [])
        raw = element_by_workflow.get(workflow.pk, "")
        element = ALIASES.get(raw.casefold(), raw).casefold() if raw else "<null>"
        for group in groups:
            specimens[group] += 1
            elements[element][group] += 1
        if element not in KNOWN_ELEMENTS and element != "<null>":
            unlisted[element] += 1

    rows = [{
        "label": "number of specimens", "kind": "count",
        "values": [specimens[column] for column in columns],
    }]
    for group, group_elements in ELEMENT_GROUPS:
        rows.append({"label": group, "kind": "subheader", "values": []})
        for element in group_elements:
            key = element.casefold()
            rows.append({
                "label": element, "kind": "percent",
                "values": [
                    _percent(elements[key][column], specimens[column])
                    for column in columns
                ],
            })
    warnings = [
        f"Unlisted element '{element}' occurs in {count} specimen(s); it remains in the denominator but has no Table 5 row."
        for element, count in sorted(unlisted.items())
    ]
    return BoneDistributionResult(columns, rows, warnings)

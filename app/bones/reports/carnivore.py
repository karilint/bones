"""Habitat-level carnivore damage report calculations."""
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..models import CompletedResponse, CompletedWorkflow
from .mni_service import build_report, clean, rows_in_batches


DAMAGE_LEVELS = ("0", "1", "2", "3", "4")
MARK_TYPES = ("furrow", "pit", "puncture", "score")
PORTION_FIELDS = (
    "Long Bone Portion", "Innominate Portion", "Mandible Portion",
    "Rib Portion", "Scapula Portion", "Vertebra Portion",
)

CALCULATION_RULES = (
    "Population: completed transects and completed occurrences only; 2008 transects are excluded, and in 2024 only shrubs closed habitat is retained. All selected report filters are then applied.",
    "Habitats: the Pre response to 'Transect physical habitat'. A bone with a missing or conflicting transect habitat contributes only to All.",
    "Bone denominator: number of Bone workflow instances belonging to eligible completed occurrences.",
    "Specimen completeness: the Bone response to 'Complete?'. This describes whether the recorded bone specimen is complete; it is not whole-skeleton completeness.",
    "Each completeness percentage: Bone workflow instances answering Yes or No, divided by the Bone denominator, multiplied by 100. Missing or unrecognised answers remain in the denominator and are reported as warnings.",
    "C level per bone: 'Carn Damage 1 Level' is used for legacy records; when it is blank, the parent 'Carnivore damage' value is used. A bone without a positive recorded level is C0.",
    "Each % bones C0–C4: Bone workflow instances classified at that C level, divided by the Bone denominator, multiplied by 100. Each bone contributes to exactly one C-level row.",
    "Primary tooth-mark type per bone: the response to 'Portion 1: TM Type'. Later portions are additional detail and do not create additional classifications in this report.",
    "Each mark-type percentage: bones whose primary tooth-mark type matches that type, divided by bones with a recognised primary furrow, pit, puncture, or score, multiplied by 100. Bones without a recorded primary tooth-mark type are not in this denominator.",
    "All: values are recalculated from all eligible records; percentages are not averages of the habitat columns.",
    "Missing or unrecognised numeric levels and tooth-mark types are reported as data-quality warnings and are not assigned to a displayed non-zero category.",
    "Specimen preservation detail: one row per Bone workflow instance, including element, side, specimen completeness, applicable element-portion responses, long-bone circumference, weathering, articulation, burial, and the number of populated damage observations.",
    "Damage observation detail: one row for each populated ordinal damage slot 1-6. Level and damaged portion come from 'Carn Damage n Level/Portion'; tooth-mark type and count come from 'Portion n: TM Type/Number'. A legacy parent 'Carnivore damage' value is emitted as observation 1 only when no ordinal slot is populated.",
    "Damage detail is descriptive source data: repeated observations on the same specimen are retained and must not be interpreted as additional specimens.",
    "Zero denominators: percentages are displayed as 0.00.",
)


@dataclass
class CarnivoreReportResult:
    habitats: list[str]
    rows: list[dict]
    warnings: list[str] = field(default_factory=list)
    specimen_headers: list[str] = field(default_factory=list)
    specimen_rows: list[list] = field(default_factory=list)
    damage_headers: list[str] = field(default_factory=list)
    damage_rows: list[list] = field(default_factory=list)


def _number(value):
    try:
        return int(float(clean(value)))
    except (TypeError, ValueError):
        return None


def _damage_level(answers):
    raw = clean(answers.get("carn damage 1 level"))
    if not raw:
        raw = clean(answers.get("carnivore damage"))
    if not raw:
        return 0, False
    value = _number(raw)
    if value is None or value not in range(5):
        return 0, True
    return value, False


def _percent(numerator, denominator):
    return 100 * numerator / denominator if denominator else 0.0


def build_carnivore_report(cleaned_data, note_filters=()):
    # Taxon exclusions are irrelevant to bone-level carnivore observations.
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
        CompletedResponse.objects.filter(skipped=False).values(
            "workflow_id", "question_text", "response"
        ),
        "workflow_id", [row.pk for row in workflows],
    )
    answers = defaultdict(dict)
    for response in response_rows:
        answers[response["workflow_id"]][response["question_text"].casefold()] = response["response"]

    bones = Counter()
    completeness = defaultdict(Counter)
    damage = defaultdict(Counter)
    marks = defaultdict(Counter)
    mark_total = Counter()
    invalid_levels = 0
    invalid_marks = 0
    invalid_completeness = 0
    specimens_with_damage = Counter()
    specimens_with_marks = Counter()
    specimen_headers = [
        "Transect UID", "Transect", "Occurrence ID", "Occurrence number",
        "Bone workflow UID", "Bone instance", "Habitat", "Taxon", "Element",
        "Side", "Specimen complete?", "Recorded anatomical portions",
        "Long bone circumference", "Weathering class", "Articulated?",
        "Buried?", "Damage observation count",
    ]
    damage_headers = [
        "Transect UID", "Transect", "Occurrence ID", "Occurrence number",
        "Bone workflow UID", "Bone instance", "Habitat", "Taxon", "Element",
        "Side", "Specimen complete?", "Damage observation", "Damage level",
        "Damaged portion", "Tooth-mark type", "Tooth-mark count",
    ]
    specimen_rows = []
    damage_rows = []
    for workflow in workflows:
        habitat = habitat_by_transect.get(workflow.occurrence.transect_id, "")
        groups = ["All"] + ([habitat] if habitat else [])
        values = answers[workflow.pk]
        complete = clean(values.get("complete?"))
        complete_key = complete.casefold()
        if complete_key not in {"yes", "no"}:
            invalid_completeness += 1
        level, invalid = _damage_level(values)
        invalid_levels += int(invalid)
        for group in groups:
            bones[group] += 1
            if complete_key in {"yes", "no"}:
                completeness[complete_key][group] += 1
            damage[str(level)][group] += 1
        raw = clean(values.get("portion 1: tm type")).casefold()
        if raw and raw not in MARK_TYPES:
            invalid_marks += 1
        elif raw:
            for group in groups:
                marks[raw][group] += 1
                mark_total[group] += 1

        occurrence = mni_result.occurrence_metadata.get(workflow.occurrence_id, {})
        transect = mni_result.transect_metadata.get(
            workflow.occurrence.transect_id, {}
        )
        identity = [
            workflow.occurrence.transect_id, transect.get("block", ""),
            workflow.occurrence_id, occurrence.get("number", ""), workflow.pk,
            workflow.instance_number, habitat, occurrence.get("taxon", ""),
            clean(values.get("what element is this?")), clean(values.get("side")),
            complete,
        ]
        portions = "; ".join(
            f"{field}: {clean(values.get(field.casefold()))}"
            for field in PORTION_FIELDS if clean(values.get(field.casefold()))
        )
        observation_count = 0
        has_mark_detail = False
        for number in range(1, 7):
            damage_level = clean(values.get(f"carn damage {number} level"))
            damage_portion = clean(values.get(f"carn damage {number} portion"))
            mark_type = clean(values.get(f"portion {number}: tm type"))
            mark_count = clean(values.get(f"portion {number}: tm number"))
            if not any((damage_level, damage_portion, mark_type, mark_count)):
                continue
            observation_count += 1
            has_mark_detail = has_mark_detail or bool(mark_type or mark_count)
            damage_rows.append(identity + [
                number, damage_level, damage_portion, mark_type, mark_count,
            ])
        legacy_level = clean(values.get("carnivore damage"))
        if not observation_count and legacy_level:
            observation_count = 1
            damage_rows.append(identity + [1, legacy_level, "", "", ""])
        if observation_count:
            for group in groups:
                specimens_with_damage[group] += 1
        if has_mark_detail:
            for group in groups:
                specimens_with_marks[group] += 1
        specimen_rows.append(identity + [
            portions, clean(values.get("long bone circumference")),
            clean(values.get("weathering class")),
            clean(values.get("articulated?")), clean(values.get("buried?")),
            observation_count,
        ])

    rows = [
        {"label": "Number of specimens", "kind": "integer",
         "values": [bones[column] for column in columns]},
        {"label": "% complete specimens", "kind": "percent",
         "values": [_percent(completeness["yes"][column], bones[column]) for column in columns]},
        {"label": "% incomplete specimens", "kind": "percent",
         "values": [_percent(completeness["no"][column], bones[column]) for column in columns]},
        {"label": "% specimens with recorded damage detail", "kind": "percent",
         "values": [_percent(specimens_with_damage[column], bones[column]) for column in columns]},
        {"label": "% specimens with tooth-mark detail", "kind": "percent",
         "values": [_percent(specimens_with_marks[column], bones[column]) for column in columns]},
    ]
    rows.extend({
        "label": f"% bones C{level}", "kind": "percent",
        "values": [_percent(damage[level][column], bones[column]) for column in columns],
    } for level in DAMAGE_LEVELS)
    rows.extend({
        "label": f"% {mark}s" if mark != "score" else "% scores",
        "kind": "percent",
        "values": [_percent(marks[mark][column], mark_total[column]) for column in columns],
    } for mark in MARK_TYPES)
    warnings = []
    if invalid_levels:
        warnings.append(f"{invalid_levels} Bone workflow instance(s) contain an unrecognised carnivore damage level; valid levels on the same bone were retained, otherwise the bone was classified C0.")
    if invalid_marks:
        warnings.append(f"{invalid_marks} unrecognised tooth-mark type response(s) were omitted from the mark-type denominator.")
    if invalid_completeness:
        warnings.append(f"{invalid_completeness} Bone workflow instance(s) have a missing or unrecognised 'Complete?' response; they remain in the specimen denominator.")
    specimen_rows.sort(key=lambda row: (row[0], row[3] or 0, row[5] or 0, str(row[4])))
    damage_rows.sort(key=lambda row: (row[0], row[3] or 0, row[5] or 0, row[11]))
    return CarnivoreReportResult(
        columns, rows, warnings, specimen_headers, specimen_rows,
        damage_headers, damage_rows,
    )

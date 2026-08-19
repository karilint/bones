"""Database extraction and normalization for the MNI report."""
import re
from collections import defaultdict
from django.db.models import Q

from ..models import (CompletedOccurrence, CompletedOccurrenceInfo,
                      CompletedResponse, CompletedTransect, CompletedTransectInfo,
                      CompletedWorkflow, MNIElementRule, MNITaxonRule,
                      MNIWeatheringRule)
from .mni import ElementRule, Observation, OccurrenceRecord, calculate_mni

ELIGIBLE_WORKFLOWS = ("Bone", "Dentition")
HABITAT_QUESTION = "Transect physical habitat"
RESERVE_QUESTION = "On old reserve?"
SQL_SERVER_IN_BATCH_SIZE = 1000


def rows_in_batches(queryset, field_name, values,
                    batch_size=SQL_SERVER_IN_BATCH_SIZE):
    """Evaluate an ``IN`` lookup without exceeding SQL Server's parameter cap."""
    values = list(values)
    rows = []
    for offset in range(0, len(values), batch_size):
        batch = values[offset:offset + batch_size]
        rows.extend(queryset.filter(**{f"{field_name}__in": batch}))
    return rows


def clean(value):
    return " ".join(str(value or "").split())


def answer(mapping, *names):
    for name in names:
        value = clean(mapping.get(name.casefold()))
        if value:
            return value
    return ""


def weather_score(value):
    numbers = [int(value) for value in re.findall(r"\d+", clean(value))]
    return max(numbers) if numbers else None


def weather_group(score):
    if score is None:
        return "Unknown"
    if score == 0:
        return "0"
    if score <= 2:
        return "1-2"
    if score <= 4:
        return "3-4"
    return str(score)


def normalize_side(value):
    normalized = clean(value).casefold()
    aliases = {"l": "left", "r": "right", "n/a": "not applicable", "na": "not applicable"}
    normalized = aliases.get(normalized, normalized)
    if normalized in {"left", "right", "not applicable", "unknown"}:
        return normalized, False
    return "unknown", True


def _warning(category, transect_id, occurrence_id=None, instance_number=None,
             raw_value="", treatment="", severity="Warning", workflow=""):
    return {"category": category, "transect_id": transect_id,
            "occurrence_id": occurrence_id, "instance_number": instance_number,
            "raw_value": raw_value, "treatment": treatment,
            "severity": severity, "workflow": workflow}


def _weathering_for_occurrence(workflows, workflow_answers, transect_id,
                               occurrence_id, weathering_rules=None):
    """Return Bone-derived weathering and actionable per-instance warnings."""
    bone_workflows = [
        workflow for workflow in workflows
        if workflow.template_workflow.name.casefold() != "dentition"
    ]
    rules = weathering_rules or {}
    scored = []
    warnings = []
    for workflow in bone_workflows:
        raw = answer(workflow_answers[workflow.pk], "Weathering class")
        rule = rules.get(raw.casefold())
        weathering_class = rule.source_class if rule else clean(raw)
        score = weather_score(weathering_class)
        scored.append((workflow, raw, weathering_class, score))
        if raw and rules and not rule:
            warnings.append(_warning(
                "unmapped_weathering", transect_id, occurrence_id,
                workflow.instance_number, raw, "Retained source value",
                workflow=workflow.template_workflow.name,
            ))
    valid = [(score, weathering_class) for _, _, weathering_class, score in scored if score is not None]
    occurrence_class = max(valid, key=lambda item: item[0])[1] if valid else "Unknown"
    for workflow, raw, weathering_class, score in scored:
        if score is None:
            treatment = (
                "Occurrence weathering derived from another Bone instance"
                if valid else "Retained as Unknown"
            )
            warnings.append(_warning(
                "missing_weathering", transect_id, occurrence_id,
                workflow.instance_number, treatment=treatment,
                severity="Warning", workflow=workflow.template_workflow.name,
            ))
    return occurrence_class, warnings


def _one_value(rows, question):
    values = {clean(row["response"]) for row in rows
              if row["pre_or_post"].casefold() == "pre"
              and row["question_text"].casefold() == question.casefold()
              and clean(row["response"])}
    return (next(iter(values)) if len(values) == 1 else "", len(values) > 1)


def eligible_transects(cleaned_data, note_filters=(), apply_population_rules=True):
    qs = CompletedTransect.objects.filter(state__iexact="Completed")
    if apply_population_rules:
        qs = qs.exclude(start_time__year=2008)
        valid_2024 = Q(details__pre_or_post__iexact="Pre",
                       details__question_text__iexact=HABITAT_QUESTION,
                       details__response__iexact="shrubs closed")
        qs = qs.filter(~Q(start_time__year=2024) | valid_2024)
    if cleaned_data.get("transects"):
        transect_ids = [getattr(row, "pk", row) for row in cleaned_data["transects"]]
        qs = qs.filter(pk__in=transect_ids)
    if cleaned_data.get("years"):
        qs = qs.filter(start_time__year__in=cleaned_data["years"])
    if cleaned_data.get("habitats"):
        qs = qs.filter(details__pre_or_post__iexact="Pre", details__question_text__iexact=HABITAT_QUESTION, details__response__in=cleaned_data["habitats"])
    if cleaned_data.get("reserve"):
        qs = qs.filter(details__pre_or_post__iexact="Pre", details__question_text__iexact=RESERVE_QUESTION, details__response__iexact=cleaned_data["reserve"])
    for row in note_filters:
        criteria = {}
        if row.get("phase"):
            criteria["details__pre_or_post"] = row["phase"]
        if row.get("question"):
            criteria["details__question_text"] = row["question"]
        if row.get("responses"):
            criteria["details__response__in"] = row["responses"]
        if criteria:
            qs = qs.filter(**criteria)
    return qs.select_related("transect_template").order_by("uid").distinct()


def build_report(
    cleaned_data, note_filters=(), apply_population_rules=True,
    element_rule_rows=None,
):
    transects = list(eligible_transects(
        cleaned_data, note_filters,
        apply_population_rules=apply_population_rules,
    ))
    transect_ids = [row.pk for row in transects]
    warnings = []
    info_rows = rows_in_batches(
        CompletedTransectInfo.objects.values(
            "transect_id", "pre_or_post", "question_text", "response"
        ),
        "transect_id", transect_ids,
    )
    by_transect = defaultdict(list)
    for row in info_rows:
        by_transect[row["transect_id"]].append(row)
    habitat_by_transect = {}
    reserve_by_transect = {}
    for transect in transects:
        habitat, conflict = _one_value(by_transect[transect.pk], HABITAT_QUESTION)
        reserve, reserve_conflict = _one_value(by_transect[transect.pk], RESERVE_QUESTION)
        habitat_by_transect[transect.pk] = habitat.casefold()
        reserve_by_transect[transect.pk] = reserve
        if not habitat or conflict:
            warnings.append(_warning("conflicting_habitat" if conflict else "missing_habitat", transect.pk, raw_value=habitat, treatment="Included in All data only"))
        if reserve_conflict:
            warnings.append(_warning("conflicting_reserve", transect.pk, raw_value=reserve, treatment="Reserve grouping omitted"))

    occurrences = rows_in_batches(
        CompletedOccurrence.objects.filter(state__iexact="Completed"),
        "transect_id", transect_ids,
    )
    occurrence_ids = [row.pk for row in occurrences]
    occurrence_info = defaultdict(dict)
    occurrence_info_rows = rows_in_batches(
        CompletedOccurrenceInfo.objects.values(
            "occurrence_id", "pre_or_post", "question_text", "response"
        ),
        "occurrence_id", occurrence_ids,
    )
    for row in occurrence_info_rows:
        key = f'{row["pre_or_post"]}: {row["question_text"]}'.casefold()
        occurrence_info[row["occurrence_id"]][key] = row["response"]

    taxon_rules = {row.source_alias.casefold(): row for row in MNITaxonRule.objects.filter(active=True)}
    def taxon_for(occurrence):
        values = occurrence_info[occurrence.pk]
        raw = answer(values, "Post: Taxon Guess?", "Post: Taxon", "Pre: Taxon")
        if not raw:
            warnings.append(_warning("missing_taxon", occurrence.transect_id, occurrence.pk, treatment="Unknown taxon; excluded from MNI"))
            return "Unknown taxon"
        rule = taxon_rules.get(raw.casefold())
        if not rule:
            warnings.append(_warning("unmapped_taxon", occurrence.transect_id, occurrence.pk, raw_value=raw, treatment="Retained source value"))
            return raw
        return rule.canonical_label

    occurrence_taxa = {row.pk: taxon_for(row) for row in occurrences}
    occurrence_records = [OccurrenceRecord(row.pk, row.transect_id, occurrence_taxa[row.pk], habitat_by_transect.get(row.transect_id, "")) for row in occurrences]
    workflows = rows_in_batches(
        CompletedWorkflow.objects.filter(
            template_workflow__name__in=ELIGIBLE_WORKFLOWS,
        ).select_related("template_workflow"),
        "occurrence_id", occurrence_ids,
    )
    workflow_ids = [row.pk for row in workflows]
    workflow_answers = defaultdict(dict)
    response_rows = rows_in_batches(
        CompletedResponse.objects.filter(skipped=False).values(
            "workflow_id", "question_text", "response"
        ),
        "workflow_id", workflow_ids,
    )
    for row in response_rows:
        workflow_answers[row["workflow_id"]][row["question_text"].casefold()] = row["response"]
    workflows_by_occurrence = defaultdict(list)
    for workflow in workflows:
        workflows_by_occurrence[workflow.occurrence_id].append(workflow)
    for occurrence in occurrences:
        if not workflows_by_occurrence[occurrence.pk]:
            warnings.append(_warning("missing_skeletal_workflow", occurrence.transect_id, occurrence.pk, treatment="Occurrence retained; no MNI contribution"))

    weathering_rules = {
        row.source_class.casefold(): row
        for row in MNIWeatheringRule.objects.filter(active=True, reviewed=True)
    }
    max_weather = {}
    for occurrence_id, rows in workflows_by_occurrence.items():
        occurrence = next(item for item in occurrences if item.pk == occurrence_id)
        max_weather[occurrence_id], weather_warnings = _weathering_for_occurrence(
            rows, workflow_answers, occurrence.transect_id, occurrence.pk,
            weathering_rules,
        )
        warnings.extend(weather_warnings)

    observations = []
    occurrence_map = {row.pk: row for row in occurrences}
    for workflow in workflows:
        occurrence = occurrence_map[workflow.occurrence_id]
        values = workflow_answers[workflow.pk]
        name = workflow.template_workflow.name
        is_dentition = name.casefold() == "dentition"
        element = "teeth" if is_dentition else answer(values, "What element is this?")
        if not element:
            warnings.append(_warning("missing_element", occurrence.transect_id, occurrence.pk, workflow.instance_number, treatment="Excluded from MNI"))
            continue
        side_raw = "not applicable" if is_dentition else answer(values, "Side")
        side, bad_side = normalize_side(side_raw)
        if bad_side:
            warnings.append(_warning("invalid_side", occurrence.transect_id, occurrence.pk, workflow.instance_number, answer(values, "Side"), "Treated as unknown"))
        complete_raw = "Yes" if is_dentition else answer(values, "Complete?", "Complete")
        complete = complete_raw.casefold() == "yes"
        if complete_raw.casefold() not in {"yes", "no"}:
            warnings.append(_warning("missing_completeness", occurrence.transect_id, occurrence.pk, workflow.instance_number, complete_raw, "Treated as incomplete"))
        sex = answer(occurrence_info[occurrence.pk], "Post: Sex", "Pre: Sex") or "Unknown"
        age = answer(occurrence_info[occurrence.pk], "Post: Age", "Pre: Age") or "Unknown"
        weathering = max_weather.get(occurrence.pk, "Unknown")
        observations.append(Observation(occurrence.transect_id, occurrence.pk, workflow.instance_number,
            occurrence_taxa[occurrence.pk], sex, age, weathering, clean(element).casefold(), side,
            complete, habitat_by_transect.get(occurrence.transect_id, "")))

    if element_rule_rows is None:
        element_rule_rows = MNIElementRule.objects.all()
    element_rules = {row.canonical_name.casefold(): ElementRule(row.canonical_name, row.divisor, row.paired, row.excluded, row.active and row.reviewed) for row in element_rule_rows}
    excluded = list(cleaned_data.get("excluded_taxa", []))
    result = calculate_mni(observations, occurrence_records, element_rules, excluded, warnings)
    result.transect_metadata = {
        transect.pk: {
            "date": transect.start_time,
            "block": transect.name,
            "habitat": habitat_by_transect.get(transect.pk, ""),
            "reserve": reserve_by_transect.get(transect.pk, ""),
        }
        for transect in transects
    }
    result.occurrence_metadata = {
        occurrence.pk: {
            "number": occurrence.occurrence_number,
            "transect_id": occurrence.transect_id,
            "taxon": occurrence_taxa.get(occurrence.pk, ""),
        }
        for occurrence in occurrences
    }
    result.weathering_age_max = {
        row.source_class.casefold(): row.age_max
        for row in weathering_rules.values()
    }
    result.weathering_normalised = {
        row.source_class.casefold(): {
            "class": "0-2" if float(row.age_max_corrected) == 5 else "3-5",
            "age_max": row.age_max_corrected,
        }
        for row in weathering_rules.values()
    }
    return result, transects, list(excluded)

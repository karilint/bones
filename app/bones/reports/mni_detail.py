"""Presentation data for MNI sections on completed-record detail pages."""
from collections import Counter

from django.urls import reverse

from ..mni_seed import DEFAULT_EXCLUDED_TAXA
from ..models import MNIElementRule
from .mni_service import build_report


def build_mni_detail(transect_id, occurrence_id=None, instance_number=None):
    """Calculate a transect once and project it onto a detail-page scope."""
    rule_rows = list(MNIElementRule.objects.all())
    result, transects, excluded_taxa = build_report(
        {"transects": [transect_id],
         "excluded_taxa": list(DEFAULT_EXCLUDED_TAXA)},
        apply_population_rules=False,
        element_rule_rows=rule_rows,
    )
    if not transects:
        return empty_mni_detail(
            "This transect is outside the eligible MNI report population."
        )

    observations = [
        row for row in result.observations
        if occurrence_id is None or row.occurrence_id == occurrence_id
    ]
    if instance_number is not None:
        observations = [
            row for row in observations if row.instance_number == instance_number
        ]

    rules = {row.canonical_name.casefold(): row for row in rule_rows}
    excluded = {value.casefold() for value in excluded_taxa}
    usable_keys = {
        (row.occurrence_id, row.instance_number, row.taxon, row.element,
         row.side, row.complete)
        for row in result.usable_observations
    }
    evidence = []
    for row in observations:
        rule = rules.get(row.element.casefold())
        if row.taxon.casefold() in excluded:
            status, reason = "Excluded", "Taxon excluded from MNI"
        elif not rule:
            status, reason = "Excluded", "No element rule"
        elif rule.excluded or not rule.active or not rule.reviewed:
            status, reason = "Excluded", "Element rule is excluded or not reviewed"
        elif (row.occurrence_id, row.instance_number, row.taxon, row.element,
              row.side, row.complete) not in usable_keys:
            status, reason = "Deduplicated", "Conservative incomplete-fragment rule"
        else:
            status, reason = "Included", "Included in the transect calculation"
        evidence.append({
            "occurrence_id": row.occurrence_id,
            "instance_number": row.instance_number,
            "taxon": row.taxon,
            "sex": row.sex,
            "age": row.age,
            "weathering": row.weathering,
            "element": row.element,
            "side": row.side,
            "complete": row.complete,
            "status": status,
            "reason": reason,
            "divisor": getattr(rule, "divisor", None),
            "paired": getattr(rule, "paired", None),
            "instance_url": reverse(
                "bones:occurrences:instance_detail",
                kwargs={"occurrence_pk": row.occurrence_id,
                        "instance_number": row.instance_number},
            ),
        })

    warnings = [
        row for row in result.warnings
        if (occurrence_id is None or row.get("occurrence_id") in (None, occurrence_id))
        and (instance_number is None
             or row.get("instance_number") in (None, instance_number)
             or instance_number in row.get("instance_numbers", []))
    ]
    transect_rows = [
        row for row in result.transect_rows if row["transect_id"] == transect_id
    ]
    occurrence_taxa = {
        (row.occurrence_id, row.taxon) for row in result.observations
        if occurrence_id is None or row.occurrence_id == occurrence_id
    }
    occurrence_counts = Counter(taxon for _, taxon in occurrence_taxa)
    relevant_taxa = {row.taxon for row in observations}
    taxon_rows = [{
        **row,
        "occurrence_count": occurrence_counts.get(row["taxon"], 0),
        "groups": [group for group in result.group_rows
                   if group.transect_id == transect_id
                   and group.taxon == row["taxon"]],
    } for row in transect_rows
        if occurrence_id is None or row["taxon"] in relevant_taxa]

    return {
        "available": True,
        "message": "",
        "total_mni": sum(row["mni"] for row in transect_rows),
        "taxon_count": len(taxon_rows),
        "contributing_instance_count": len({
            (row.occurrence_id, row.instance_number) for row in observations
        }),
        "warning_count": len(warnings),
        "taxon_rows": taxon_rows,
        "evidence_rows": evidence,
        "warnings": warnings,
        "report_url": f'{reverse("bones:reports:mni")}?transects={transect_id}',
    }


def empty_mni_detail(message="No skeletal evidence contributes to MNI."):
    return {
        "available": False, "message": message, "total_mni": 0,
        "taxon_count": 0, "contributing_instance_count": 0,
        "warning_count": 0, "taxon_rows": [], "evidence_rows": [],
        "warnings": [], "report_url": "",
    }

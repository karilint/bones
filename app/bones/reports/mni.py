"""Pure calculation primitives for the Minimum Number of Individuals report."""
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from math import ceil


@dataclass(frozen=True)
class ElementRule:
    name: str
    divisor: int
    paired: bool
    excluded: bool = False
    usable: bool = True


@dataclass(frozen=True)
class Observation:
    transect_id: int
    occurrence_id: int
    instance_number: int
    taxon: str
    sex: str
    age: str
    weathering: str
    element: str
    side: str
    complete: bool
    habitat: str = ""


@dataclass(frozen=True)
class OccurrenceRecord:
    occurrence_id: int
    transect_id: int
    taxon: str
    habitat: str = ""


@dataclass(frozen=True)
class GroupMNI:
    transect_id: int
    taxon: str
    sex: str
    age: str
    weathering: str
    mni: int


@dataclass
class ReportResult:
    habitats: list[str]
    rows: list[dict]
    transect_rows: list[dict]
    group_rows: list[GroupMNI]
    warnings: list[dict] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    usable_observations: list[Observation] = field(default_factory=list)
    transect_metadata: dict = field(default_factory=dict)
    occurrence_metadata: dict = field(default_factory=dict)
    weathering_age_max: dict = field(default_factory=dict)
    weathering_normalised: dict = field(default_factory=dict)


def element_mni(left, right, unknown, not_applicable, rule):
    """Return the conservative individual count for one skeletal element."""
    if rule.divisor < 1:
        raise ValueError("Element divisor must be positive")
    if rule.paired:
        known = max(ceil(left / rule.divisor), ceil(right / rule.divisor))
        balanced = ceil((left + right + unknown + not_applicable) / (2 * rule.divisor))
        return max(known, balanced)
    return ceil((left + right + unknown + not_applicable) / rule.divisor)


def _deduplicate_incomplete(observations):
    incomplete = defaultdict(dict)
    for item in observations:
        if item.complete:
            yield item
            continue
        key = (
            item.occurrence_id, item.taxon, item.sex, item.age, item.weathering,
            item.element,
        )
        incomplete[key].setdefault(item.side, item)

    for by_side in incomplete.values():
        known = [by_side[side] for side in ("left", "right") if side in by_side]
        if known:
            yield from known
            continue
        # An incomplete fragment with an uncertain side can belong to either
        # side and must not, by itself, imply another individual.
        yield next(iter(by_side.values()))


def _occurrence_mni_warnings(observations, rules):
    """Identify occurrences whose skeletal evidence implies multiple individuals."""
    sides = defaultdict(Counter)
    instances = defaultdict(set)
    for item in observations:
        key = (
            item.occurrence_id, item.transect_id, item.taxon, item.sex,
            item.age, item.weathering, item.element.casefold(),
        )
        sides[key][item.side] += 1
        instances[key].add(item.instance_number)

    demographic_groups = defaultdict(list)
    evidence = defaultdict(list)
    for key, counts in sides.items():
        occurrence, transect, taxon, sex, age, weathering, element = key
        value = element_mni(
            counts["left"], counts["right"], counts["unknown"],
            counts["not applicable"], rules[element],
        )
        group = (occurrence, transect, taxon, sex, age, weathering)
        demographic_groups[group].append(value)
        if value > 1:
            side_text = ", ".join(
                f"{side} {count}" for side, count in sorted(counts.items()) if count
            )
            evidence[group].append(f"{element} ({side_text})")

    occurrence_totals = defaultdict(int)
    occurrence_instances = defaultdict(set)
    occurrence_evidence = defaultdict(list)
    for group, values in demographic_groups.items():
        occurrence, transect, taxon, *_ = group
        occurrence_key = (occurrence, transect, taxon)
        occurrence_totals[occurrence_key] += max(values)
        occurrence_evidence[occurrence_key].extend(evidence[group])
        for element_key, element_instances in instances.items():
            if element_key[:6] == group:
                occurrence_instances[occurrence_key].update(element_instances)

    warnings = []
    for (occurrence, transect, taxon), value in sorted(occurrence_totals.items()):
        if value <= 1:
            continue
        instance_numbers = sorted(occurrence_instances[(occurrence, transect, taxon)])
        evidence_text = "; ".join(occurrence_evidence[(occurrence, transect, taxon)])
        warnings.append({
            "category": "occurrence_mni_exceeds_one", "severity": "Critical",
            "transect_id": transect, "occurrence_id": occurrence,
            "instance_number": None, "instance_numbers": instance_numbers,
            "taxon": taxon, "habitat": "", "element_side": evidence_text,
            "occurrence_n": 1, "mni_n": value,
            "raw_value": f"MNI {value} from instances {', '.join(map(str, instance_numbers))}",
            "treatment": "Review whether the instances represent separate individuals or duplicate records.",
            "workflow": "Bone",
        })
    return warnings


def calculate_mni(observations, occurrences, rules, excluded_taxa=(), warnings=None):
    """Calculate per-transect MNI and a taxon-by-habitat summary."""
    observations = list(observations)
    warnings = list(warnings or [])
    excluded = {value.casefold() for value in excluded_taxa}
    usable = []
    for item in _deduplicate_incomplete(observations):
        rule = rules.get(item.element.casefold())
        if not rule or rule.excluded or not rule.usable:
            warnings.append({
                "category": "element_rule", "transect_id": item.transect_id,
                "occurrence_id": item.occurrence_id,
                "instance_number": item.instance_number, "raw_value": item.element,
                "treatment": "Excluded from MNI", "severity": "Warning",
                "workflow": "",
            })
            continue
        if item.taxon.casefold() not in excluded:
            usable.append(item)

    sides = defaultdict(Counter)
    for item in usable:
        key = (item.transect_id, item.taxon, item.sex, item.age,
               item.weathering, item.element.casefold())
        sides[key][item.side] += 1

    group_elements = defaultdict(list)
    for key, counts in sides.items():
        transect, taxon, sex, age, weathering, element = key
        value = element_mni(
            counts["left"], counts["right"], counts["unknown"],
            counts["not applicable"], rules[element],
        )
        group_elements[(transect, taxon, sex, age, weathering)].append(value)

    groups = [
        GroupMNI(*key, max(values))
        for key, values in sorted(group_elements.items())
    ]
    warnings.extend(_occurrence_mni_warnings(usable, rules))
    transect_taxon = Counter()
    for group in groups:
        transect_taxon[(group.transect_id, group.taxon)] += group.mni

    occurrence_count_by_transect_taxon = Counter(
        (occurrence.transect_id, occurrence.taxon) for occurrence in occurrences
    )
    for (transect, taxon), value in sorted(transect_taxon.items()):
        occurrence_count = occurrence_count_by_transect_taxon[(transect, taxon)]
        if value > occurrence_count:
            warnings.append({
                "category": "transect_mni_exceeds_occurrences", "severity": "Critical",
                "transect_id": transect, "occurrence_id": None,
                "instance_number": None, "instance_numbers": [],
                "taxon": taxon, "habitat": "", "element_side": "",
                "occurrence_n": occurrence_count, "mni_n": value,
                "raw_value": f"MNI {value} > {occurrence_count} occurrences",
                "treatment": "Review contributing occurrence and instance warnings.",
                "workflow": "",
            })

    habitat_by_transect = {}
    for occurrence in occurrences:
        if occurrence.habitat:
            habitat_by_transect.setdefault(occurrence.transect_id, occurrence.habitat)
    habitats = sorted({value for value in habitat_by_transect.values() if value}, key=str.casefold)

    occ_counts = Counter((o.taxon, o.habitat) for o in occurrences)
    occ_all = Counter(o.taxon for o in occurrences)
    mni_all = Counter()
    mni_habitat = Counter()
    for (transect, taxon), value in transect_taxon.items():
        mni_all[taxon] += value
        habitat = habitat_by_transect.get(transect, "")
        if habitat:
            mni_habitat[(taxon, habitat)] += value

    taxa = sorted(set(occ_all) | set(mni_all), key=str.casefold)
    overall_occ_total = sum(occ_all.values())
    overall_mni_total = sum(mni_all.values())
    habitat_occ_totals = {h: sum(occ_counts[(t, h)] for t in taxa) for h in habitats}
    habitat_mni_totals = {h: sum(mni_habitat[(t, h)] for t in taxa) for h in habitats}

    def cell(count, total, is_excluded=False, warning=False):
        return {"count": None if is_excluded else count,
                "percent": None if is_excluded else (100 * count / total if total else 0),
                "excluded": is_excluded, "warning": warning}

    rows = []
    for taxon in taxa:
        taxon_excluded = taxon.casefold() in excluded
        rows.append({
            "taxon": taxon,
            "occurrence_all": cell(occ_all[taxon], overall_occ_total),
            "mni_all": cell(mni_all[taxon], overall_mni_total, taxon_excluded, mni_all[taxon] > occ_all[taxon]),
            "habitats": [{
                "name": habitat,
                "occurrence": cell(occ_counts[(taxon, habitat)], habitat_occ_totals[habitat]),
                "mni": cell(mni_habitat[(taxon, habitat)], habitat_mni_totals[habitat], taxon_excluded, mni_habitat[(taxon, habitat)] > occ_counts[(taxon, habitat)]),
            } for habitat in habitats],
        })
        if not taxon_excluded and mni_all[taxon] > occ_all[taxon]:
            warnings.append({
                "category": "summary_mni_exceeds_occurrences", "severity": "Critical",
                "transect_id": None, "occurrence_id": None,
                "instance_number": None, "instance_numbers": [],
                "taxon": taxon, "habitat": "All data", "element_side": "",
                "occurrence_n": occ_all[taxon], "mni_n": mni_all[taxon],
                "raw_value": f"MNI {mni_all[taxon]} > {occ_all[taxon]} occurrences",
                "treatment": "Review transect- and occurrence-level warnings.",
                "workflow": "",
            })
        for habitat in habitats:
            mni_value = mni_habitat[(taxon, habitat)]
            occurrence_value = occ_counts[(taxon, habitat)]
            if not taxon_excluded and mni_value > occurrence_value:
                warnings.append({
                    "category": "summary_mni_exceeds_occurrences", "severity": "Critical",
                    "transect_id": None, "occurrence_id": None,
                    "instance_number": None, "instance_numbers": [],
                    "taxon": taxon, "habitat": habitat, "element_side": "",
                    "occurrence_n": occurrence_value, "mni_n": mni_value,
                    "raw_value": f"MNI {mni_value} > {occurrence_value} occurrences",
                    "treatment": "Review transect- and occurrence-level warnings.",
                    "workflow": "",
                })

    transect_rows = [
        {"transect_id": transect, "taxon": taxon, "mni": value,
         "habitat": habitat_by_transect.get(transect, "")}
        for (transect, taxon), value in sorted(transect_taxon.items())
    ]
    totals = {
        "taxon": "Total", "occurrence_all": cell(overall_occ_total, overall_occ_total),
        "mni_all": cell(overall_mni_total, overall_mni_total),
        "habitats": [{"name": h, "occurrence": cell(habitat_occ_totals[h], habitat_occ_totals[h]),
                      "mni": cell(habitat_mni_totals[h], habitat_mni_totals[h])}
                     for h in habitats],
    }
    return ReportResult(
        habitats, [totals] + rows, transect_rows, groups, warnings,
        observations, usable,
    )

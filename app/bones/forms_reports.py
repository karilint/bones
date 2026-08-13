"""Filter forms for analytical reports."""
from django import forms
from django.db import DatabaseError
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q

from .models import CompletedTransect, DataLogFile, MNITaxonRule


RECONCILIATION_SHEETS = (
    ("Critical findings", "Critical findings"), ("Transects", "Transects"),
    ("Occurrences", "Occurrences"), ("Instances", "Instances"), ("GPS", "GPS issues"),
    ("Recovery candidates", "Recovery candidates"),
    ("Database only", "Database-only records"), ("Deleted evidence", "Deleted and historical evidence"),
    ("Log parse issues", "Log parsing issues"), ("Methodology", "Methodology"),
)
RECONCILIATION_STATUSES = (
    ("MISSING", "Missing"), ("AMBIGUOUS", "Ambiguous"),
    ("HISTORICAL_ONLY", "Historical only"),
    ("CURRENT_PROBABLE", "Probable match"), ("GPS_MISSING", "GPS missing"),
    ("GPS_PARTIAL", "GPS partial"), ("GPS_OUTSIDE_TIME_RANGE", "GPS outside time range"),
    ("GPS_INVALID_COORDINATES", "GPS invalid coordinates"), ("GPS_HISTORY_ONLY", "GPS history only"),
    ("GPS_EXPECTATION_UNKNOWN", "GPS expectation unknown"),
    ("GPS_NOT_EXPECTED_EARLY_MANUAL", "Early manual GPS not expected"),
    ("CURRENT_EXACT", "Current exact"), ("LOG_CANCELLED", "Log cancelled"),
    ("GPS_PRESENT", "GPS present"),
)
RECOVERY_STATUSES = (
    ("READY_FOR_IMPORT", "Ready for import"),
    ("READY_AFTER_PARENT", "Ready after parent"),
    ("REVIEW_REQUIRED", "Review required"),
    ("INSUFFICIENT_LOG_DATA", "Insufficient log data"),
    ("TEMPLATE_NOT_FOUND", "Template not found"),
)


class DataReconciliationReportForm(forms.Form):
    from_year = forms.IntegerField(required=False, min_value=1900, max_value=2200, widget=forms.NumberInput(attrs={"class": "w3-input"}))
    to_year = forms.IntegerField(required=False, min_value=1900, max_value=2200, widget=forms.NumberInput(attrs={"class": "w3-input"}))
    logs = forms.ModelMultipleChoiceField(required=False, queryset=DataLogFile.objects.none(), widget=forms.SelectMultiple(attrs={"class": "w3-select", "aria-label": "Data logs; leave empty for all"}))
    gps_required_from_year = forms.IntegerField(required=False, min_value=1900, max_value=2200, label="GPS expected from year", widget=forms.NumberInput(attrs={"class": "w3-input"}))
    contents = forms.MultipleChoiceField(choices=RECONCILIATION_SHEETS, widget=forms.CheckboxSelectMultiple(attrs={"class": "w3-check"}), initial=[value for value, _ in RECONCILIATION_SHEETS])
    statuses = forms.MultipleChoiceField(choices=RECONCILIATION_STATUSES, widget=forms.CheckboxSelectMultiple(attrs={"class": "w3-check"}), initial=[value for value, _ in RECONCILIATION_STATUSES if value not in {"CURRENT_EXACT", "LOG_CANCELLED", "GPS_PRESENT"}])
    recovery_statuses = forms.MultipleChoiceField(choices=RECOVERY_STATUSES, widget=forms.CheckboxSelectMultiple(attrs={"class": "w3-check"}), initial=["READY_FOR_IMPORT", "READY_AFTER_PARENT", "REVIEW_REQUIRED", "INSUFFICIENT_LOG_DATA", "TEMPLATE_NOT_FOUND"])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.fields["logs"].queryset = (
                DataLogFile.objects.defer("contents").order_by("upload_date", "id")
            )
        except (DatabaseError, ImproperlyConfigured):
            pass

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("from_year"), cleaned.get("to_year")
        if start and end and start > end:
            self.add_error("to_year", "To year must be the same as or later than from year.")
        return cleaned


class MNIReportForm(forms.Form):
    transects = forms.ModelMultipleChoiceField(
        queryset=CompletedTransect.objects.none(), required=False,
        widget=forms.SelectMultiple(attrs={"class": "w3-select bones-select2", "data-placeholder": "All eligible transects"}),
    )
    years = forms.MultipleChoiceField(required=False, widget=forms.SelectMultiple(attrs={"class": "w3-select bones-select2"}))
    habitats = forms.MultipleChoiceField(required=False, widget=forms.SelectMultiple(attrs={"class": "w3-select bones-select2"}))
    reserve = forms.ChoiceField(required=False, choices=(("", "Both"), ("Yes", "Yes"), ("No", "No")), widget=forms.Select(attrs={"class": "w3-select"}))
    excluded_taxa = forms.MultipleChoiceField(required=False, widget=forms.SelectMultiple(attrs={"class": "w3-select bones-select2"}))

    def __init__(self, *args, **kwargs):
        apply_population_rules = kwargs.pop("apply_population_rules", True)
        super().__init__(*args, **kwargs)
        try:
            habitat_2024 = Q(details__pre_or_post__iexact="Pre",
                             details__question_text__iexact="Transect physical habitat",
                             details__response__iexact="shrubs closed")
            eligible = CompletedTransect.objects.filter(state__iexact="Completed")
            if apply_population_rules:
                eligible = (eligible.exclude(start_time__year=2008)
                            .filter(~Q(start_time__year=2024) | habitat_2024))
            eligible = eligible.distinct()
            self.fields["transects"].queryset = eligible.order_by("start_time", "uid")
            years = eligible.dates("start_time", "year")
            self.fields["years"].choices = [(str(v.year), str(v.year)) for v in years]
            habitats = eligible.filter(details__pre_or_post__iexact="Pre", details__question_text__iexact="Transect physical habitat").order_by().values_list("details__response", flat=True).distinct()
            self.fields["habitats"].choices = [(v, v) for v in sorted(filter(None, habitats), key=str.casefold)]
            labels = list(MNITaxonRule.objects.filter(active=True).order_by("canonical_label").values_list("canonical_label", "default_excluded").distinct())
            self.fields["excluded_taxa"].choices = [(v, v) for v, _ in sorted(labels, key=lambda row: row[0].casefold())]
            if not self.is_bound:
                self.initial["excluded_taxa"] = sorted({v for v, excluded in labels if excluded}, key=str.casefold)
        except (DatabaseError, ImproperlyConfigured):
            pass


class BoneCensusExportForm(MNIReportForm):
    include_elements = forms.BooleanField(
        required=False, initial=False,
        label="Include elements",
        widget=forms.CheckboxInput(attrs={"class": "w3-check"}),
    )
    omit_unknown_weathering = forms.BooleanField(
        required=False, initial=True,
        label="Omit rows with unknown weathering stage",
        widget=forms.CheckboxInput(attrs={"class": "w3-check"}),
    )
    use_normalised_weathering = forms.BooleanField(
        required=False, initial=True,
        label="Use normalised weathering stages",
        widget=forms.CheckboxInput(attrs={"class": "w3-check"}),
    )

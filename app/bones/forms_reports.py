"""Filter forms for analytical reports."""
from django import forms
from django.db import DatabaseError
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q

from .models import CompletedTransect, MNITaxonRule


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

from django import forms
from django.core.exceptions import ValidationError
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError
from django.utils.translation import gettext_lazy as _
from PIL import Image

from .models import (
    CompletedOccurrence,
    CompletedOccurrenceInfo,
    CompletedResponse,
    CompletedTransectInfo,
    CompletedWorkflow,
    EntityImage,
)


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def clean(self, data, initial=None):
        clean_one = super().clean
        if isinstance(data, (list, tuple)):
            return [clean_one(item, initial) for item in data]
        return [clean_one(data, initial)]


class EntityImageUploadForm(forms.Form):
    images = MultipleFileField(widget=MultipleFileInput(attrs={"accept": "image/jpeg,image/png,image/webp", "class": "w3-input w3-border"}))
    alt_text = forms.CharField(required=False, max_length=300, widget=forms.TextInput(attrs={"class": "w3-input w3-border"}))

    def clean_images(self):
        uploads = self.cleaned_data["images"]
        for upload in uploads:
            if upload.size > 20 * 1024 * 1024:
                raise ValidationError("Images must be 20 MB or smaller.")
            try:
                image = Image.open(upload)
                image.verify()
            except Exception as exc:
                raise ValidationError("Upload valid JPEG, PNG, or WebP images.") from exc
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValidationError("Only JPEG, PNG, and WebP images are supported.")
            upload.seek(0)
        return uploads


class ImageGalleryFilterForm(forms.Form):
    """Hierarchy-aware filters for the protected image gallery."""

    transect = forms.CharField(
        required=False,
        label=_("Transect name or UID"),
        widget=forms.TextInput(attrs={"class": "w3-input w3-border"}),
    )
    habitat = forms.ChoiceField(
        required=False,
        label=_("Transect habitat"),
        choices=(),
        widget=forms.Select(attrs={"class": "w3-select w3-border"}),
    )
    occurrence = forms.IntegerField(
        required=False,
        min_value=1,
        label=_("Occurrence ID or number"),
        widget=forms.NumberInput(attrs={"class": "w3-input w3-border"}),
    )
    taxon = forms.ChoiceField(
        required=False,
        label=_("Occurrence taxon"),
        choices=(),
        widget=forms.Select(attrs={"class": "w3-select w3-border"}),
    )
    instance = forms.IntegerField(
        required=False,
        min_value=1,
        label=_("Instance number"),
        widget=forms.NumberInput(attrs={"class": "w3-input w3-border"}),
    )
    element = forms.ChoiceField(
        required=False,
        label=_("Instance element"),
        choices=(),
        widget=forms.Select(attrs={"class": "w3-select w3-border"}),
    )

    def __init__(self, *args, **kwargs):
        entity_types = kwargs.pop("entity_types", None)
        super().__init__(*args, **kwargs)
        try:
            values_by_field = self._linked_choice_values(entity_types)
        except (DatabaseError, ImproperlyConfigured):
            values_by_field = {"habitat": [], "taxon": [], "element": []}
        empty_labels = {
            "habitat": _("All habitats"),
            "taxon": _("All taxa"),
            "element": _("All elements"),
        }
        for field_name, empty_label in empty_labels.items():
            choices = values_by_field[field_name]
            self.fields[field_name].choices = [
                ("", empty_label),
                *((value, value[:1].upper() + value[1:]) for value in choices),
            ]

    @classmethod
    def _linked_choice_values(cls, entity_types=None):
        images = EntityImage.objects.filter(
            archived_by_deletion__isnull=True,
            archived_by_transect_deletion__isnull=True,
            archived_by_occurrence_deletion__isnull=True,
        )
        if entity_types is not None:
            images = images.filter(entity_type__in=entity_types)
        images = images.prefetch_related("targets")

        transect_ids, occurrence_ids, instance_keys = set(), set(), set()
        for image in images:
            entities = [(image.entity_type, image.entity_id)] + [
                (target.entity_type, target.entity_id)
                for target in image.targets.all()
            ]
            for entity_type, entity_id in entities:
                try:
                    if entity_type == EntityImage.TRANSECT:
                        transect_ids.add(int(entity_id))
                    elif entity_type == EntityImage.OCCURRENCE:
                        occurrence_ids.add(int(entity_id))
                    elif entity_type == EntityImage.INSTANCE:
                        occurrence_id, number = str(entity_id).split(":", 1)
                        occurrence_ids.add(int(occurrence_id))
                        instance_keys.add((int(occurrence_id), int(number)))
                except (TypeError, ValueError):
                    continue

        occurrence_rows = cls._batched_rows(
            CompletedOccurrence.objects.all(), "pk", occurrence_ids,
            "pk", "transect_id",
        )
        transect_ids.update(row[1] for row in occurrence_rows)
        habitat_rows = cls._batched_rows(
            CompletedTransectInfo.objects.filter(
                pre_or_post__iexact="Pre",
                question_text__iexact="Transect physical habitat",
            ),
            "transect_id", transect_ids, "response",
        )
        taxon_rows = cls._batched_rows(
            CompletedOccurrenceInfo.objects.filter(
                question_text__in=("Taxon Guess?", "Taxon")
            ),
            "occurrence_id", occurrence_ids, "response",
        )

        workflow_rows = cls._batched_rows(
            CompletedWorkflow.objects.all(), "occurrence_id",
            {key[0] for key in instance_keys}, "pk", "occurrence_id", "instance_number",
        )
        workflow_ids = {
            workflow_id
            for workflow_id, occurrence_id, number in workflow_rows
            if (occurrence_id, number) in instance_keys
        }
        element_rows = cls._batched_rows(
            CompletedResponse.objects.filter(
                skipped=False,
                question_text__iexact="What element is this?",
            ),
            "workflow_id", workflow_ids, "response",
        )
        return {
            "habitat": cls._clean_choices(row[0] for row in habitat_rows),
            "taxon": cls._clean_choices(row[0] for row in taxon_rows),
            "element": cls._clean_choices(row[0] for row in element_rows),
        }

    @staticmethod
    def _batched_rows(queryset, field_name, values, *fields, batch_size=900):
        values = list(values)
        rows = []
        for offset in range(0, len(values), batch_size):
            batch = values[offset:offset + batch_size]
            rows.extend(queryset.filter(**{f"{field_name}__in": batch}).values_list(*fields))
        return rows

    @staticmethod
    def _clean_choices(values):
        return sorted({value.strip() for value in values if value and value.strip()}, key=str.casefold)

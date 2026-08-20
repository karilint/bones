"""Filtered thumbnail gallery for images linked to survey entities."""
from __future__ import annotations

from django.db import DatabaseError
from django.db.models import Q
from django.urls import reverse
from django.views.generic import ListView

from ..image_forms import ImageGalleryFilterForm
from ..image_views import ENTITY_PERMISSIONS
from ..models import (
    CompletedOccurrence,
    CompletedOccurrenceInfo,
    CompletedResponse,
    CompletedTransect,
    CompletedTransectInfo,
    CompletedWorkflow,
    EntityImage,
)
from .mixins import BonesAuthMixin


HABITAT_QUESTION = "Transect physical habitat"
TAXON_QUESTIONS = ("Taxon Guess?", "Taxon")
ELEMENT_QUESTION = "What element is this?"


class ImageGalleryView(BonesAuthMixin, ListView):
    """List protected thumbnails filtered through the survey hierarchy."""

    model = EntityImage
    template_name = "bones/images/gallery.html"
    context_object_name = "images"
    paginate_by = 24

    def get_queryset(self):
        self.filter_error = None
        allowed_entity_types = self._allowed_entity_types()
        self.filter_form = ImageGalleryFilterForm(
            self.request.GET or None,
            entity_types=allowed_entity_types,
        )
        queryset = EntityImage.objects.filter(
            archived_by_deletion__isnull=True,
            archived_by_transect_deletion__isnull=True,
            archived_by_occurrence_deletion__isnull=True,
            entity_type__in=allowed_entity_types,
        ).prefetch_related("targets")
        if not self.request.GET:
            return queryset.distinct()
        if not self.filter_form.is_valid():
            return queryset.none()

        try:
            return self._filter_queryset(queryset, self.filter_form.cleaned_data)
        except DatabaseError as exc:
            self.filter_error = exc
            return queryset.none()

    def _allowed_entity_types(self):
        return [
            entity_type
            for entity_type, permission in ENTITY_PERMISSIONS.items()
            if self.request.user.has_perm(permission)
        ]

    @staticmethod
    def _filter_queryset(queryset, filters):
        transects = CompletedTransect.objects.all()
        transect_value = (filters.get("transect") or "").strip()
        if transect_value:
            lookup = Q(name__icontains=transect_value)
            if transect_value.isdigit():
                lookup |= Q(pk=int(transect_value))
            transects = transects.filter(lookup)
        if filters.get("habitat"):
            transects = transects.filter(
                details__pre_or_post__iexact="Pre",
                details__question_text__iexact=HABITAT_QUESTION,
                details__response__iexact=filters["habitat"].strip(),
            )

        occurrences = CompletedOccurrence.objects.filter(transect__in=transects)
        if filters.get("occurrence"):
            value = filters["occurrence"]
            occurrences = occurrences.filter(Q(pk=value) | Q(occurrence_number=value))
        if filters.get("taxon"):
            occurrences = occurrences.filter(
                details__question_text__in=TAXON_QUESTIONS,
                details__response__iexact=filters["taxon"].strip(),
            )

        workflows = CompletedWorkflow.objects.filter(occurrence__in=occurrences)
        if filters.get("instance"):
            workflows = workflows.filter(instance_number=filters["instance"])
        if filters.get("element"):
            workflows = workflows.filter(
                responses__skipped=False,
                responses__question_text__iexact=ELEMENT_QUESTION,
                responses__response__iexact=filters["element"].strip(),
            )

        instance_filter = bool(filters.get("instance") or filters.get("element"))
        occurrence_filter = bool(filters.get("occurrence") or filters.get("taxon"))
        transect_filter = bool(transect_value or filters.get("habitat"))

        if instance_filter:
            allowed = {EntityImage.INSTANCE: {
                f"{occurrence_id}:{number}"
                for occurrence_id, number in workflows.values_list(
                    "occurrence_id", "instance_number"
                ).distinct()
            }}
        elif occurrence_filter:
            allowed = {
                EntityImage.OCCURRENCE: {
                    str(value)
                    for value in occurrences.values_list("pk", flat=True).distinct()
                },
                EntityImage.INSTANCE: {
                    f"{occurrence_id}:{number}"
                    for occurrence_id, number in workflows.values_list(
                        "occurrence_id", "instance_number"
                    ).distinct()
                },
            }
        elif transect_filter:
            allowed = {
                EntityImage.TRANSECT: {
                    str(value)
                    for value in transects.values_list("pk", flat=True).distinct()
                },
                EntityImage.OCCURRENCE: {
                    str(value)
                    for value in occurrences.values_list("pk", flat=True).distinct()
                },
                EntityImage.INSTANCE: {
                    f"{occurrence_id}:{number}"
                    for occurrence_id, number in workflows.values_list(
                        "occurrence_id", "instance_number"
                    ).distinct()
                },
            }
        else:
            return queryset.distinct()
        return [
            image
            for image in queryset.prefetch_related("targets")
            if ImageGalleryView._matches_allowed_entity(image, allowed)
        ]

    @staticmethod
    def _matches_allowed_entity(image, allowed):
        if str(image.entity_id) in allowed.get(image.entity_type, set()):
            return True
        return any(
            str(target.entity_id) in allowed.get(target.entity_type, set())
            for target in image.targets.all()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        context.update(
            {
                "filter_form": self.filter_form,
                "filter_error": self.filter_error,
                "filter_active": bool(params),
                "filter_querystring": f"&{params.urlencode()}" if params else "",
                "result_count": context["paginator"].count,
                "breadcrumbs": [
                    {"label": "Dashboard", "url": reverse("bones:dashboard")},
                    {"label": "Images"},
                ],
            }
        )
        self._add_display_metadata(context["images"])
        return context

    @staticmethod
    def _add_display_metadata(images):
        """Fill legacy metadata gaps from current image links and domain rows."""
        images = list(images)
        occurrence_ids = set()
        transect_ids = set()
        for image in images:
            metadata = dict(image.parsed_metadata or {})
            photo_role = str(
                getattr(image, "photo_role", "") or metadata.get("photo_role", "")
            ).strip().casefold()
            if photo_role in {"start", "turn"}:
                metadata["transect_photo_role"] = photo_role.capitalize()
            entities = [(image.entity_type, image.entity_id)]
            if not image.entity_type or not image.entity_id:
                entities.extend(
                    (target.entity_type, target.entity_id)
                    for target in image.targets.all()
                )
            for entity_type, entity_id in entities:
                try:
                    if entity_type == EntityImage.TRANSECT:
                        metadata["transect_uid"] = int(entity_id)
                    elif entity_type == EntityImage.OCCURRENCE:
                        metadata["occurrence_id"] = int(entity_id)
                        metadata.pop("instance_number", None)
                    elif entity_type == EntityImage.INSTANCE:
                        occurrence_id, number = str(entity_id).split(":", 1)
                        metadata["occurrence_id"] = int(occurrence_id)
                        metadata["instance_number"] = int(number)
                except (TypeError, ValueError):
                    continue
            if metadata.get("occurrence_id"):
                occurrence_ids.add(metadata["occurrence_id"])
            if metadata.get("transect_uid"):
                transect_ids.add(metadata["transect_uid"])
            image.gallery_metadata = metadata

        try:
            occurrences = {
                row.pk: row
                for row in CompletedOccurrence.objects.filter(
                    pk__in=occurrence_ids
                ).only("pk", "occurrence_number", "transect_id")
            }
            for image in images:
                metadata = image.gallery_metadata
                occurrence = occurrences.get(metadata.get("occurrence_id"))
                if occurrence:
                    metadata["occurrence_number"] = occurrence.occurrence_number
                    metadata["transect_uid"] = occurrence.transect_id
                    transect_ids.add(occurrence.transect_id)
            transects = {
                row.pk: row.name
                for row in CompletedTransect.objects.filter(pk__in=transect_ids).only(
                    "pk", "name"
                )
            }
            for image in images:
                metadata = image.gallery_metadata
                name = transects.get(metadata.get("transect_uid"))
                if name:
                    metadata["transect_name"] = name
            related = ImageGalleryView._related_display_values(images)
            for image in images:
                metadata = image.gallery_metadata
                occurrence_id = metadata.get("occurrence_id")
                transect_id = metadata.get("transect_uid")
                instance_key = (occurrence_id, metadata.get("instance_number"))
                metadata["habitat"] = related["habitats"].get(transect_id, "")
                metadata["taxon"] = related["taxa"].get(occurrence_id, "")
                metadata["element"] = related["elements"].get(instance_key, "")
                metadata["side"] = related["sides"].get(instance_key, "")
        except DatabaseError:
            return

    @staticmethod
    def _related_display_values(images):
        metadata_rows = [image.gallery_metadata for image in images]
        transect_ids = {
            row.get("transect_uid") for row in metadata_rows if row.get("transect_uid")
        }
        occurrence_ids = {
            row.get("occurrence_id") for row in metadata_rows if row.get("occurrence_id")
        }
        instance_keys = {
            (row.get("occurrence_id"), row.get("instance_number"))
            for row in metadata_rows
            if row.get("occurrence_id") and row.get("instance_number")
        }

        habitats = {}
        for transect_id, response in CompletedTransectInfo.objects.filter(
            transect_id__in=transect_ids,
            pre_or_post__iexact="Pre",
            question_text__iexact=HABITAT_QUESTION,
        ).values_list("transect_id", "response"):
            if response:
                habitats.setdefault(transect_id, response)

        taxa = {}
        taxon_rows = CompletedOccurrenceInfo.objects.filter(
            occurrence_id__in=occurrence_ids,
            question_text__iexact="Taxon Guess?",
        ).values_list("occurrence_id", "pre_or_post", "response")
        for occurrence_id, _phase, response in sorted(
            taxon_rows, key=lambda row: str(row[1]).casefold() != "post"
        ):
            if response:
                taxa.setdefault(occurrence_id, response)

        workflow_pairs = {}
        workflows = CompletedWorkflow.objects.filter(
            occurrence_id__in={key[0] for key in instance_keys}
        ).values_list("pk", "occurrence_id", "instance_number")
        for workflow_id, occurrence_id, instance_number in workflows:
            key = (occurrence_id, instance_number)
            if key in instance_keys:
                workflow_pairs[workflow_id] = key

        elements, sides = {}, {}
        responses = CompletedResponse.objects.filter(
            workflow_id__in=workflow_pairs,
            skipped=False,
            question_text__in=(ELEMENT_QUESTION, "Side"),
        ).values_list("workflow_id", "question_text", "response")
        for workflow_id, question, response in responses:
            if not response:
                continue
            target = elements if question.casefold() == ELEMENT_QUESTION.casefold() else sides
            target.setdefault(workflow_pairs[workflow_id], response)
        return {"habitats": habitats, "taxa": taxa, "elements": elements, "sides": sides}

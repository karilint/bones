from __future__ import annotations

import json
from io import BytesIO

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from PIL import ExifTags, Image, ImageOps

from .image_catalog import write_image_index
from .image_forms import EntityImageUploadForm
from .image_imports import canonical_metadata
from .models import (
    CompletedOccurrence, CompletedTransect, CompletedWorkflow, EntityImage,
    EntityImageTarget,
)


ENTITY_PERMISSIONS = {
    "transect": "bones.view_completedtransect",
    "occurrence": "bones.view_completedoccurrence",
    "instance": "bones.view_completedworkflow",
}


def instance_key(occurrence_id, instance_number):
    return f"{occurrence_id}:{instance_number}"


def resolve_parent(entity_type, entity_id):
    if entity_type == "transect":
        return get_object_or_404(CompletedTransect, pk=entity_id)
    if entity_type == "occurrence":
        return get_object_or_404(CompletedOccurrence, pk=entity_id)
    if entity_type == "instance":
        try:
            occurrence_id, instance_number = entity_id.split(":", 1)
        except ValueError as exc:
            raise Http404 from exc
        workflows = CompletedWorkflow.objects.filter(occurrence_id=occurrence_id, instance_number=instance_number)
        if not workflows.exists():
            raise Http404
        return workflows
    raise Http404


def can_view(user, entity_type):
    return user.is_authenticated and user.has_perm(ENTITY_PERMISSIONS[entity_type])


def image_context(entity_type, entity_id, user):
    return {
        "entity_images": EntityImage.objects.filter(
            Q(targets__entity_type=entity_type, targets__entity_id=str(entity_id))
            | Q(entity_type=entity_type, entity_id=str(entity_id))
        ).distinct(),
        "image_upload_form": EntityImageUploadForm(),
        "image_entity_type": entity_type,
        "image_entity_id": str(entity_id),
        "can_upload_images": user.has_perm("bones.add_entityimage"),
    }


def _json_value(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return str(value)


def _hierarchy_metadata(entity_type, entity_id):
    if entity_type == "transect":
        transect = CompletedTransect.objects.select_related("transect_template").get(pk=entity_id)
        return canonical_metadata(transect)
    if entity_type == "occurrence":
        occurrence = CompletedOccurrence.objects.select_related(
            "transect__transect_template"
        ).get(pk=entity_id)
        return {
            **canonical_metadata(occurrence.transect),
            "occurrence_id": occurrence.pk,
            "occurrence_number": occurrence.occurrence_number,
        }
    occurrence_id, instance_number = str(entity_id).split(":", 1)
    occurrence = CompletedOccurrence.objects.select_related(
        "transect__transect_template"
    ).get(pk=occurrence_id)
    return {
        **canonical_metadata(occurrence.transect),
        "occurrence_id": occurrence.pk,
        "occurrence_number": occurrence.occurrence_number,
        "instance_number": int(instance_number),
    }

@transaction.atomic
def save_image(upload, entity_type, entity_id, user, alt_text="", *, parsed_metadata=None, source_schema="", photo_role="", import_batch=None, targets=None):
    import hashlib
    digest = hashlib.sha256()
    for chunk in upload.chunks() if hasattr(upload, "chunks") else iter(lambda: upload.read(1024 * 1024), b""):
        digest.update(chunk)
    upload.seek(0)
    checksum = digest.hexdigest()
    target_specs = targets or [{"entity_type": entity_type, "entity_id": str(entity_id)}]
    existing = EntityImage.objects.filter(entity_type=entity_type, entity_id=str(entity_id), checksum=checksum).first()
    if existing:
        links_created = 0
        for target in target_specs:
            lookup = {
                "image": existing,
                "entity_type": target["entity_type"],
                "entity_id": str(target["entity_id"]),
            }
            if EntityImageTarget.objects.filter(**lookup).exists():
                continue
            link = EntityImageTarget(**lookup, linked_by=user)
            link._history_user = user
            link._change_reason = "Image linked during bulk import"
            link.save()
            links_created += 1
        existing._asset_created = False
        existing._links_created = links_created
        write_image_index()
        return existing
    source = Image.open(upload)
    width, height = source.size
    raw_exif = source.getexif()
    exif = {ExifTags.TAGS.get(key, str(key)): _json_value(value) for key, value in raw_exif.items()}
    try: gps = raw_exif.get_ifd(ExifTags.IFD.GPSInfo)
    except (AttributeError, KeyError, TypeError): gps = {}
    if gps:
        exif["GPSInfo"] = {ExifTags.GPSTAGS.get(key, str(key)): _json_value(value) for key, value in gps.items()}
    upload.seek(0)
    metadata = _hierarchy_metadata(entity_type, entity_id)
    metadata.update(parsed_metadata or {})
    record = EntityImage(entity_type=entity_type, entity_id=str(entity_id), original_name=upload.name, content_type=getattr(upload, "content_type", "application/octet-stream") or "application/octet-stream", size=upload.size, width=width, height=height, checksum=checksum, exif_metadata=exif, parsed_metadata=metadata, source_schema=source_schema, photo_role=photo_role, alt_text=alt_text, import_batch=import_batch, uploaded_by=user)
    record.image.save(upload.name, upload, save=False)
    thumb = ImageOps.exif_transpose(source.copy()); thumb.thumbnail((480, 360))
    output = BytesIO(); thumb.save(output, format="WEBP", quality=82)
    record.thumbnail.save("thumbnail.webp", ContentFile(output.getvalue()), save=False)
    record._history_user = user
    record._change_reason = "Imported in bulk" if import_batch else "Uploaded through detail page"
    record.save()
    for target in target_specs:
        link = EntityImageTarget(
            image=record,
            entity_type=target["entity_type"],
            entity_id=str(target["entity_id"]),
            linked_by=user,
        )
        link._history_user = user
        link._change_reason = "Image linked during bulk import" if import_batch else "Image linked during upload"
        link.save()
    record._asset_created = True
    record._links_created = len(target_specs)
    write_image_index()
    return record

class ImageUploadView(LoginRequiredMixin, View):
    def post(self, request, entity_type, entity_id):
        resolve_parent(entity_type, entity_id)
        if not can_view(request.user, entity_type) or not request.user.has_perm("bones.add_entityimage"):
            return HttpResponseForbidden()
        form = EntityImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            for upload in form.cleaned_data["images"]:
                save_image(upload, entity_type, entity_id, request.user, form.cleaned_data["alt_text"])
        return redirect(request.POST.get("next") or "/")


class ProtectedImageView(LoginRequiredMixin, View):
    def get(self, request, pk, variant):
        if variant not in {"original", "thumbnail"}:
            raise Http404
        record = get_object_or_404(EntityImage, pk=pk, archived_by_deletion__isnull=True)
        resolve_parent(record.entity_type, record.entity_id)
        if not can_view(request.user, record.entity_type):
            return HttpResponseForbidden()
        field = record.thumbnail if variant == "thumbnail" else record.image
        if not field:
            raise Http404
        response = FileResponse(field.open("rb"), content_type="image/webp" if variant == "thumbnail" else record.content_type)
        response["Content-Disposition"] = f'inline; filename="{record.original_name}"'
        return response


class ImageDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        record = get_object_or_404(EntityImage, pk=pk, archived_by_deletion__isnull=True)
        target_type = request.POST.get("entity_type")
        target_id = request.POST.get("entity_id")
        resolve_parent(target_type or record.entity_type, target_id or record.entity_id)
        allowed = request.user == record.uploaded_by or request.user.has_perm("bones.delete_entityimage")
        if not can_view(request.user, target_type or record.entity_type) or not allowed:
            return HttpResponseForbidden()
        if target_type and target_id:
            link = record.targets.filter(entity_type=target_type, entity_id=target_id).first()
            if link is None:
                raise Http404
            if record.targets.count() > 1:
                link._history_user = request.user
                link._change_reason = "Image unlinked from entity"
                link.delete()
                write_image_index()
                return redirect(request.POST.get("next") or "/")
        record._history_user = request.user
        record._change_reason = (
            "Deleted by uploader" if request.user == record.uploaded_by
            else "Deleted by administrator"
        )
        record.delete()
        write_image_index()
        return redirect(request.POST.get("next") or "/")
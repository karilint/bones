from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from simple_history.models import HistoricalRecords


WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def safe_template_folder(name):
    import hashlib
    import re
    import unicodedata

    canonical = unicodedata.normalize("NFC", str(name or "Unknown template")).strip()
    readable = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", canonical)
    readable = re.sub(r"\s+", " ", readable).rstrip(" .") or "Unknown template"
    if readable.upper() in WINDOWS_RESERVED:
        readable = f"_{readable}"
    readable = readable[:100].rstrip(" .")
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]
    return f"{readable}--{digest}"


def _entity_parts(instance):
    meta = instance.parsed_metadata or {}
    template_folder = meta.get("template_folder") or safe_template_folder(meta.get("template_name"))
    transect_uid = meta.get("transect_uid") or (
        instance.entity_id if instance.entity_type == "transect" else "unknown"
    )
    transect_date = str(meta.get("transect_date") or "unknown-date")[:10]
    base = (
        f"bones/images/templates/{template_folder}/transects/"
        f"{transect_date}--{transect_uid}"
    )
    if instance.entity_type == "transect":
        role = (instance.photo_role or "general").lower()
        return f"{base}/direct/{role}"
    occurrence = meta.get("occurrence_number", "unknown")
    occurrence_id = meta.get("occurrence_id") or (
        instance.entity_id if instance.entity_type == "occurrence" else "unknown"
    )
    base = f"{base}/occurrences/{occurrence}-{occurrence_id}"
    if instance.entity_type == "occurrence":
        return f"{base}/shared" if meta.get("instance_numbers") else f"{base}/direct"
    return f"{base}/instances/{meta.get('instance_number', 'unknown')}"

def entity_image_path(instance, filename):
    extension = Path(filename).suffix.lower() or ".jpg"
    return f"{_entity_parts(instance)}/originals/{instance.pk}{extension}"


def entity_thumbnail_path(instance, filename):
    return f"{_entity_parts(instance)}/thumbnails/{instance.pk}.webp"


def remove_empty_image_directories(storage, deleted_name):
    """Remove empty ancestors without ever crossing the template image root."""
    if not deleted_name or not isinstance(storage, FileSystemStorage):
        return

    boundary = (Path(storage.location) / "bones" / "images" / "templates").resolve()
    current = Path(storage.path(deleted_name)).resolve().parent
    try:
        current.relative_to(boundary)
    except ValueError:
        return

    while current != boundary:
        try:
            current.rmdir()
        except FileNotFoundError:
            current = current.parent
            continue
        except OSError:
            break
        current = current.parent

class ImageImportBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, default="preview")
    source_kind = models.CharField(max_length=20, default="upload")
    summary = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bones_image_imports")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    history = HistoricalRecords()

    class Meta:
        permissions = (("run_image_import", "Can run bulk image imports"),)
        ordering = ("-created_at",)


class EntityImage(models.Model):
    TRANSECT, OCCURRENCE, INSTANCE = "transect", "occurrence", "instance"
    ENTITY_TYPES = ((TRANSECT, "Transect"), (OCCURRENCE, "Occurrence"), (INSTANCE, "Instance"))
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPES)
    entity_id = models.CharField(max_length=80)
    image = models.ImageField(upload_to=entity_image_path, max_length=500)
    thumbnail = models.ImageField(upload_to=entity_thumbnail_path, blank=True, max_length=500)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size = models.PositiveBigIntegerField()
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    checksum = models.CharField(max_length=64, blank=True, db_index=True)
    exif_metadata = models.JSONField(default=dict, blank=True)
    parsed_metadata = models.JSONField(default=dict, blank=True)
    source_schema = models.CharField(max_length=40, blank=True)
    photo_role = models.CharField(max_length=40, blank=True)
    alt_text = models.CharField(max_length=300, blank=True)
    import_batch = models.ForeignKey(ImageImportBatch, blank=True, null=True, on_delete=models.SET_NULL, related_name="images")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bones_images")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    archived_by_deletion = models.ForeignKey(
        "bones.InstanceDeletion",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="archived_images",
    )

    history = HistoricalRecords()

    class Meta:
        ordering = ("-uploaded_at",)
        indexes = [models.Index(fields=("entity_type", "entity_id"), name="bones_image_entity_idx")]

    def __str__(self):
        return self.original_name or str(self.pk)

    def generated_alt_text(self):
        if self.entity_type == self.INSTANCE:
            occurrence, instance = self.entity_id.split(":", 1)
            return f"Image for occurrence {occurrence}, instance {instance}"
        return f"Image for {self.entity_type} {self.entity_id}"

    def delete(self, *args, **kwargs):
        storage = self.image.storage
        names = (self.image.name, self.thumbnail.name)
        result = super().delete(*args, **kwargs)
        for name in names:
            if name:
                storage.delete(name)
                remove_empty_image_directories(storage, name)
        return result

class EntityImageTarget(models.Model):
    """A lightweight association between one stored image and an entity."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    image = models.ForeignKey(EntityImage, on_delete=models.CASCADE, related_name="targets")
    entity_type = models.CharField(max_length=20, choices=EntityImage.ENTITY_TYPES)
    entity_id = models.CharField(max_length=80)
    linked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bones_image_targets",
    )
    linked_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ("linked_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("image", "entity_type", "entity_id"),
                name="bones_image_target_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=("entity_type", "entity_id"),
                name="bones_image_target_entity_idx",
            )
        ]

    def __str__(self):
        return f"{self.image_id}: {self.entity_type} {self.entity_id}"

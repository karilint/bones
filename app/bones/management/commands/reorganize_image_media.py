from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db import transaction

from bones.image_catalog import write_image_index
from bones.image_imports import canonical_metadata
from bones.models import CompletedOccurrence, CompletedTransect, EntityImage
from bones.models.images import entity_image_path, entity_thumbnail_path


class Command(BaseCommand):
    help = "Preview or apply the template-first image media reorganization."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Copy, verify, update, and remove old files.")
        parser.add_argument("--report", help="CSV report path; defaults under media/bones/images.")

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        report = Path(options["report"] or Path(settings.MEDIA_ROOT) / "bones" / "images" / "reorganization-report.csv")
        report.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        for image in EntityImage.objects.all():
            old_image, old_thumbnail = image.image.name, image.thumbnail.name
            try:
                metadata = self._metadata(image)
                image.parsed_metadata = {**(image.parsed_metadata or {}), **metadata}
                new_image = entity_image_path(image, image.original_name)
                new_thumbnail = entity_thumbnail_path(image, "thumbnail.webp") if old_thumbnail else ""
                status = "unchanged" if old_image == new_image and old_thumbnail == new_thumbnail else "planned"
                if apply_changes and status == "planned":
                    self._apply(image, old_image, old_thumbnail, new_image, new_thumbnail)
                    status = "moved"
                elif apply_changes:
                    image._change_reason = "Media hierarchy metadata standardized"
                    image.save(update_fields=["parsed_metadata"])
                rows.append([image.pk, image.original_name, old_image, new_image, status, ""])
            except Exception as exc:
                rows.append([image.pk, image.original_name, old_image, "", "failed", str(exc)])
                self.stderr.write(f"Failed {image.pk}: {exc}")
        with report.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["image_id", "original_filename", "old_path", "new_path", "status", "error"])
            writer.writerows(rows)
        if apply_changes:
            write_image_index()
        counts = {status: sum(1 for row in rows if row[4] == status) for status in {row[4] for row in rows}}
        self.stdout.write(f"Report: {report}")
        self.stdout.write(f"Results: {counts}")

    def _metadata(self, image):
        if image.entity_type == EntityImage.TRANSECT:
            transect = CompletedTransect.objects.select_related("transect_template").get(pk=image.entity_id)
            return canonical_metadata(transect)
        occurrence_id = str(image.entity_id).split(":", 1)[0]
        occurrence = CompletedOccurrence.objects.select_related("transect__transect_template").get(pk=occurrence_id)
        metadata = {
            **canonical_metadata(occurrence.transect),
            "occurrence_id": occurrence.pk,
            "occurrence_number": occurrence.occurrence_number,
        }
        if image.entity_type == EntityImage.INSTANCE:
            metadata["instance_number"] = int(str(image.entity_id).split(":", 1)[1])
        return metadata

    @staticmethod
    def _read(name):
        if not name or not default_storage.exists(name):
            raise FileNotFoundError(name)
        with default_storage.open(name, "rb") as source:
            return source.read()

    def _apply(self, image, old_image, old_thumbnail, new_image, new_thumbnail):
        original = self._read(old_image)
        thumbnail = self._read(old_thumbnail) if old_thumbnail else None
        checksum = hashlib.sha256(original).hexdigest()
        created = []
        try:
            if not default_storage.exists(new_image):
                default_storage.save(new_image, ContentFile(original)); created.append(new_image)
            if hashlib.sha256(self._read(new_image)).hexdigest() != checksum:
                raise ValueError("Original checksum verification failed")
            if thumbnail is not None and not default_storage.exists(new_thumbnail):
                default_storage.save(new_thumbnail, ContentFile(thumbnail)); created.append(new_thumbnail)
            if thumbnail is not None and self._read(new_thumbnail) != thumbnail:
                raise ValueError("Thumbnail verification failed")
            with transaction.atomic():
                image.image.name = new_image
                image.thumbnail.name = new_thumbnail
                image.checksum = checksum
                image._change_reason = "Media files reorganized into template hierarchy"
                image.save(update_fields=["image", "thumbnail", "checksum", "parsed_metadata"])
            if old_image != new_image: default_storage.delete(old_image)
            if old_thumbnail and old_thumbnail != new_thumbnail: default_storage.delete(old_thumbnail)
        except Exception:
            for name in created:
                default_storage.delete(name)
            raise
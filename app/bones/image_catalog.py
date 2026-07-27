from __future__ import annotations

import csv
import os
from pathlib import Path

from django.conf import settings


def write_image_index():
    from .models import EntityImage

    target = Path(settings.MEDIA_ROOT) / "bones" / "images" / "image-index.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "template_name", "transect_uid", "transect_date", "occurrence_number",
            "occurrence_id", "instance_number", "entity_type", "entity_id",
            "photo_role", "original_filename", "storage_path", "checksum",
            "import_batch", "uploaded_at",
        ])
        for image in EntityImage.objects.filter(archived_by_deletion__isnull=True).select_related("import_batch").prefetch_related("targets"):
            metadata = image.parsed_metadata or {}
            targets = list(image.targets.all()) or [image]
            for target_link in targets:
                target_type = target_link.entity_type
                target_id = target_link.entity_id
                instance_number = metadata.get("instance_number", "")
                if target_type == "instance" and ":" in target_id:
                    instance_number = target_id.rsplit(":", 1)[1]
                writer.writerow([
                    metadata.get("template_name", ""), metadata.get("transect_uid", ""),
                    metadata.get("transect_date", ""), metadata.get("occurrence_number", ""),
                    metadata.get("occurrence_id", ""), instance_number,
                    target_type, target_id, image.photo_role, image.original_name,
                    image.image.name, image.checksum, image.import_batch_id or "", image.uploaded_at.isoformat(),
                ])
    os.replace(temporary, target)
    return target
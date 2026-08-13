"""Normalize previously imported canonical image files."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.management.base import BaseCommand, CommandError

from bones.image_catalog import write_image_index
from bones.image_processing import normalization_policy, normalize_image
from bones.models import EntityImage


class Command(BaseCommand):
    help = "Preview or normalize existing image media, retaining recoverable backups."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Replace canonical files and update image records.")
        parser.add_argument("--backup-dir", default=str(Path(settings.MEDIA_ROOT) / "bones" / "image-originals"))

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        backup_root = Path(options["backup_dir"]).resolve()
        changed = skipped = failed = 0
        before_total = after_total = 0
        policy = normalization_policy()

        for record in EntityImage.objects.order_by("uploaded_at").iterator():
            storage = record.image.storage
            if not isinstance(storage, FileSystemStorage):
                raise CommandError("Existing-media normalization currently requires FileSystemStorage.")
            old_name = record.image.name
            if not old_name or not storage.exists(old_name):
                self.stderr.write(f"Missing file for {record.pk}: {old_name}")
                failed += 1
                continue
            old_path = Path(storage.path(old_name)).resolve()
            old_size = old_path.stat().st_size
            before_total += old_size
            after_total += old_size
            already_normalized = (record.parsed_metadata or {}).get("image_normalization") == policy
            compliant = (
                record.content_type == "image/jpeg"
                and max(record.width, record.height) <= policy["max_edge"]
                and record.size == old_size
            )
            if already_normalized or compliant:
                if apply_changes and not already_normalized:
                    record.parsed_metadata = {**(record.parsed_metadata or {}), "image_normalization": policy}
                    record.save(update_fields=["parsed_metadata"])
                skipped += 1
                continue
            try:
                with old_path.open("rb") as source:
                    normalized = normalize_image(source)
            except Exception as exc:
                self.stderr.write(f"Failed {record.pk}: {exc}")
                failed += 1
                continue
            new_size = len(normalized.data)
            after_total += min(old_size, new_size) - old_size
            if new_size >= old_size:
                skipped += 1
                continue
            changed += 1
            self.stdout.write(f"{record.pk}: {old_size:,} -> {new_size:,} bytes")
            if apply_changes:
                self._apply(record, old_name, old_path, normalized, backup_root)

        mode = "Applied" if apply_changes else "Preview"
        saving = before_total - after_total
        self.stdout.write(self.style.SUCCESS(
            f"{mode}: {changed} reducible, {skipped} unchanged, {failed} failed; "
            f"estimated saving {saving / (1024 ** 2):.1f} MiB."
        ))
        if apply_changes and changed:
            write_image_index()

    def _apply(self, record, old_name, old_path, normalized, backup_root):
        media_root = Path(record.image.storage.location).resolve()
        try:
            relative = old_path.relative_to(media_root)
        except ValueError as exc:
            raise CommandError(f"Image path is outside media storage: {old_path}") from exc
        backup_path = backup_root / relative
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        if not backup_path.exists():
            shutil.copy2(old_path, backup_path)

        new_name = str(PurePosixPath(old_name).with_suffix(normalized.extension))
        new_path = Path(record.image.storage.path(new_name)).resolve()
        new_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(dir=new_path.parent, suffix=".tmp")
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(normalized.data)
            os.replace(temp_name, new_path)
            record.image.name = new_name
            record.content_type = normalized.content_type
            record.size = len(normalized.data)
            record.width = normalized.width
            record.height = normalized.height
            record.checksum = normalized.checksum
            record.parsed_metadata = {**(record.parsed_metadata or {}), "image_normalization": normalization_policy()}
            record._change_reason = "Canonical image normalized for storage"
            record.save(update_fields=["image", "content_type", "size", "width", "height", "checksum", "parsed_metadata"])
            if old_path != new_path:
                old_path.unlink(missing_ok=True)
        except Exception:
            Path(temp_name).unlink(missing_ok=True)
            if old_path == new_path:
                shutil.copy2(backup_path, old_path)
            raise

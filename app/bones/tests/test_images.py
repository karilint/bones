import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.urls import resolve
from uuid import uuid4
from io import BytesIO
from PIL import Image

from ..admin import BulkForm
from ..image_forms import EntityImageUploadForm
from ..image_imports import norm, parse_filename, resolve_filename
from ..image_processing import normalize_image
from ..image_views import ImageDeleteView
from ..models import (
    CompletedOccurrenceInfo, CompletedResponse, CompletedTransectInfo,
    CompletedTransectTrack, DataLogFile, DataType, DataTypeOption, EntityImage,
    EntityImageTarget, ImageImportBatch, ProjectConfig, TemplateTransect, TemplateWorkflow, TransectDataLog,
)
from ..models.images import entity_image_path, remove_empty_image_directories, safe_template_folder


class EntityImageTests(SimpleTestCase):
    def test_image_normalization_bounds_dimensions_and_returns_jpeg(self):
        content = BytesIO()
        Image.new("RGB", (5000, 2500), "blue").save(content, "JPEG", quality=95)
        content.seek(0)

        normalized = normalize_image(content)

        self.assertEqual((normalized.width, normalized.height), (3840, 1920))
        self.assertEqual(normalized.content_type, "image/jpeg")
        self.assertEqual(normalized.extension, ".jpg")
        self.assertEqual(len(normalized.checksum), 64)
        with Image.open(BytesIO(normalized.data)) as image:
            self.assertEqual(image.format, "JPEG")

    def test_image_normalization_flattens_transparency(self):
        content = BytesIO()
        Image.new("RGBA", (20, 10), (255, 0, 0, 0)).save(content, "PNG")
        content.seek(0)

        normalized = normalize_image(content)

        with Image.open(BytesIO(normalized.data)) as image:
            self.assertEqual(image.mode, "RGB")

    def test_admin_bulk_form_accepts_five_images(self):
        uploads = []
        for index in range(5):
            content = BytesIO()
            Image.new("RGB", (20, 10), "blue").save(content, "JPEG")
            uploads.append(
                SimpleUploadedFile(
                    f"10_4365881_1_{index}.jpg",
                    content.getvalue(),
                    content_type="image/jpeg",
                )
            )
        form = BulkForm(files={"files": uploads})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(len(form.cleaned_data["files"]), 5)
    def test_all_remaining_domain_models_have_history_managers(self):
        audited_models = (
            CompletedOccurrenceInfo,
            CompletedResponse,
            CompletedTransectInfo,
            CompletedTransectTrack,
            DataLogFile,
            DataType,
            DataTypeOption,
            EntityImage,
            EntityImageTarget,
            ImageImportBatch,
            ProjectConfig,
            TemplateTransect,
            TemplateWorkflow,
            TransectDataLog,
        )
        for model in audited_models:
            with self.subTest(model=model.__name__):
                self.assertTrue(hasattr(model, "history"))

    def test_image_history_urls_use_uuid_identifiers(self):
        image_id = uuid4()
        list_match = resolve("/history/images/")
        record_match = resolve(f"/history/images/{image_id}/")
        entry_match = resolve(f"/history/images/{image_id}/1/")
        self.assertEqual(list_match.url_name, "images")
        self.assertEqual(record_match.url_name, "image_record")
        self.assertEqual(entry_match.url_name, "image_entry")
    def test_delete_url_resolves_to_delete_view(self):
        match = resolve(f"/images/{uuid4()}/delete/")
        self.assertIs(match.func.view_class, ImageDeleteView)

    def test_bulk_filename_schemas(self):
        self.assertEqual(parse_filename("10_4365881_1_2.jpg"), ("full_hierarchy", {"transect_name": "10", "transect_uid": 4365881, "occurrence_number": 1, "instance_number": 2}))
        self.assertEqual(parse_filename("12.100.18.jpg"), ("historical_occurrence", {"occurrence_number": 12, "transect_name": "100", "year": 2018}))
        schema, metadata = parse_filename("106_4479276_Turn_left.png")
        self.assertEqual(schema, "transect_location")
        self.assertEqual(metadata["photo_role"], "turn")

    def test_instance_range_filename_expands_inclusively(self):
        schema, metadata = parse_filename("105_4478950_18_1-4.JPG")
        self.assertEqual(schema, "instance_range")
        self.assertEqual(metadata["transect_name"], "105")
        self.assertEqual(metadata["transect_uid"], 4478950)
        self.assertEqual(metadata["occurrence_number"], 18)
        self.assertEqual(metadata["instance_numbers"], [1, 2, 3, 4])

    def test_instance_photo_variants_resolve_to_the_same_instance(self):
        for filename, variant in (
            ("97_3967792_1_2_a.JPG", "a"),
            ("97_3967792_1_2_b.JPG", "b"),
            ("97_3967792_2_1_c.JPG", "c"),
        ):
            with self.subTest(filename=filename):
                schema, metadata = parse_filename(filename)
                self.assertEqual(schema, "full_hierarchy")
                self.assertEqual(metadata["transect_uid"], 3967792)
                self.assertEqual(
                    metadata["instance_number"], int(filename.split("_")[3])
                )
                self.assertEqual(metadata["photo_variant"], variant)

    def test_begin_labels_are_transect_start_photos(self):
        for filename in ("97_3967792_Begin.JPG", "97_3967792_0Begin.JPG"):
            with self.subTest(filename=filename):
                schema, metadata = parse_filename(filename)
                self.assertEqual(schema, "transect_location")
                self.assertEqual(metadata["photo_role"], "start")

    def test_numeric_turn_label_is_a_transect_turn_photo(self):
        schema, metadata = parse_filename("97_3967792_3Turn.JPG")
        self.assertEqual(schema, "transect_location")
        self.assertEqual(metadata["photo_role"], "turn")

    def test_large_instance_range_does_not_imply_file_copies(self):
        schema, metadata = parse_filename("105_4478950_18_1-90.JPG")
        self.assertEqual(schema, "instance_range")
        self.assertEqual(len(metadata["instance_numbers"]), 90)

    def test_range_asset_uses_shared_occurrence_folder(self):
        image = EntityImage(
            id=uuid4(),
            entity_type="occurrence",
            entity_id="694",
            parsed_metadata={
                "template_name": "105",
                "template_folder": "105--1253e937",
                "transect_uid": 4478950,
                "transect_date": "2019-08-08",
                "occurrence_number": 18,
                "occurrence_id": 694,
                "instance_numbers": [1, 2, 3, 4],
            },
        )
        path = entity_image_path(image, "range.JPG")
        self.assertIn("/occurrences/18-694/shared/originals/", path)
    def test_instance_range_rejects_reversed_zero_and_excessive_ranges(self):
        for filename in (
            "105_4478950_18_4-1.JPG",
            "105_4478950_18_0-4.JPG",
            "105_4478950_18_1-251.JPG",
        ):
            with self.subTest(filename=filename):
                schema, _ = parse_filename(filename)
                self.assertEqual(schema, "invalid_instance_range")

    def test_text_transect_name_can_precede_instance_range(self):
        schema, metadata = parse_filename("North_Woodland_4478950_18_1-4.JPG")
        self.assertEqual(schema, "instance_range")
        self.assertEqual(metadata["transect_name"], "North_Woodland")
    def test_text_transect_names_can_contain_separators(self):
        schema, metadata = parse_filename("North_Woodland_4365881_1_2.jpg")
        self.assertEqual(schema, "full_hierarchy")
        self.assertEqual(metadata["transect_name"], "North_Woodland")
        schema, metadata = parse_filename("12.North.Woodland.18.jpg")
        self.assertEqual(schema, "historical_occurrence")
        self.assertEqual(metadata["transect_name"], "North.Woodland")

    def test_safe_template_folder_is_readable_stable_and_windows_safe(self):
        folder = safe_template_folder('Transect: North/West')
        self.assertTrue(folder.startswith("Transect- North-West--"))
        self.assertEqual(folder, safe_template_folder('Transect: North/West'))
        self.assertNotIn("/", folder)
    def test_transect_names_ignore_leading_zeroes(self):
        self.assertEqual(norm("010"), norm("10"))

    @patch("bones.image_imports.CompletedTransect.objects.select_related")
    def test_uid_filename_checks_completed_name_and_retains_template_metadata(self,select_related):
        transect=SimpleNamespace(
            pk=7130086,name="134",start_time=datetime(2024,8,22,tzinfo=timezone.utc),
            transect_template=SimpleNamespace(name="133"),
        )
        queryset=MagicMock(); queryset.get.return_value=transect; select_related.return_value=queryset
        result=resolve_filename("134_7130086_Start.jpg")
        self.assertEqual(result["status"],"ready")
        self.assertEqual(result["metadata"]["transect_name"],"134")
        self.assertEqual(result["metadata"]["template_name"],"133")

        mismatch=resolve_filename("133_7130086_Start.jpg")
        self.assertEqual(mismatch["status"],"transect_name_mismatch")
        self.assertEqual(mismatch["actual_transect_name"],"134")
        self.assertEqual(mismatch["actual_template_name"],"133")
    def test_generated_alt_text_uses_parent_identifiers(self):
        image = EntityImage(entity_type="instance", entity_id="42:3")
        self.assertEqual(image.generated_alt_text(), "Image for occurrence 42, instance 3")

    def test_upload_form_accepts_multiple_valid_images(self):
        uploads = []
        for name in ("one.jpg", "two.jpg"):
            content = BytesIO()
            Image.new("RGB", (20, 10), "red").save(content, "JPEG")
            uploads.append(SimpleUploadedFile(name, content.getvalue(), content_type="image/jpeg"))
        form = EntityImageUploadForm(files={"images": uploads})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(len(form.cleaned_data["images"]), 2)
    def test_empty_image_hierarchy_is_removed_to_templates_boundary(self):
        with tempfile.TemporaryDirectory() as media_root:
            storage = FileSystemStorage(location=media_root)
            name = (
                "bones/images/templates/North--12345678/transects/2020-01-01--1/"
                "occurrences/2-3/instances/4/originals/image.jpg"
            )
            path = Path(storage.path(name))
            path.parent.mkdir(parents=True)
            path.write_bytes(b"image")
            storage.delete(name)

            remove_empty_image_directories(storage, name)

            boundary = Path(media_root, "bones", "images", "templates")
            self.assertTrue(boundary.is_dir())
            self.assertFalse((boundary / "North--12345678").exists())

    def test_cleanup_keeps_shared_and_nonempty_folders(self):
        with tempfile.TemporaryDirectory() as media_root:
            storage = FileSystemStorage(location=media_root)
            base = (
                "bones/images/templates/North--12345678/transects/2020-01-01--1/"
                "occurrences/2-3/instances/4/originals"
            )
            deleted_name = f"{base}/deleted.jpg"
            remaining_name = f"{base}/remaining.jpg"
            deleted_path = Path(storage.path(deleted_name))
            deleted_path.parent.mkdir(parents=True)
            deleted_path.write_bytes(b"deleted")
            Path(storage.path(remaining_name)).write_bytes(b"remaining")
            storage.delete(deleted_name)

            remove_empty_image_directories(storage, deleted_name)

            self.assertTrue(Path(storage.path(remaining_name)).is_file())
            self.assertTrue(deleted_path.parent.is_dir())

    def test_cleanup_ignores_paths_outside_templates_boundary(self):
        with tempfile.TemporaryDirectory() as media_root:
            storage = FileSystemStorage(location=media_root)
            outside = Path(media_root, "unrelated", "empty")
            outside.mkdir(parents=True)

            remove_empty_image_directories(storage, "unrelated/empty/missing.jpg")

            self.assertTrue(outside.is_dir())

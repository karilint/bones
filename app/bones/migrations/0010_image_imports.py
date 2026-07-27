from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid
import bones.models.images

class Migration(migrations.Migration):
    dependencies = [("bones", "0009_entityimage"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="ImageImportBatch", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("status", models.CharField(default="preview", max_length=20)), ("source_kind", models.CharField(default="upload", max_length=20)),
            ("summary", models.JSONField(blank=True, default=dict)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("completed_at", models.DateTimeField(blank=True, null=True)),
            ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bones_image_imports", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ("-created_at",), "permissions": (("run_image_import", "Can run bulk image imports"),)}),
        migrations.AddField(model_name="entityimage", name="checksum", field=models.CharField(blank=True, db_index=True, max_length=64)),
        migrations.AddField(model_name="entityimage", name="parsed_metadata", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="entityimage", name="source_schema", field=models.CharField(blank=True, max_length=40)),
        migrations.AddField(model_name="entityimage", name="photo_role", field=models.CharField(blank=True, max_length=40)),
        migrations.AddField(model_name="entityimage", name="import_batch", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="images", to="bones.imageimportbatch")),
        migrations.AlterField(model_name="entityimage", name="image", field=models.ImageField(max_length=500, upload_to=bones.models.images.entity_image_path)),
        migrations.AlterField(model_name="entityimage", name="thumbnail", field=models.ImageField(blank=True, max_length=500, upload_to=bones.models.images.entity_thumbnail_path)),
    ]
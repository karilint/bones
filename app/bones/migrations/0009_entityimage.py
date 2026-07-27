from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import bones.models.images
import uuid


class Migration(migrations.Migration):
    dependencies = [("bones", "0008_datalogfile_upload_date_index"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="EntityImage",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("entity_type", models.CharField(choices=[("transect", "Transect"), ("occurrence", "Occurrence"), ("instance", "Instance")], max_length=20)),
                ("entity_id", models.CharField(max_length=80)),
                ("image", models.ImageField(upload_to=bones.models.images.entity_image_path)),
                ("thumbnail", models.ImageField(blank=True, upload_to=bones.models.images.entity_thumbnail_path)),
                ("original_name", models.CharField(max_length=255)), ("content_type", models.CharField(max_length=100)),
                ("size", models.PositiveBigIntegerField()), ("width", models.PositiveIntegerField()), ("height", models.PositiveIntegerField()),
                ("exif_metadata", models.JSONField(blank=True, default=dict)), ("alt_text", models.CharField(blank=True, max_length=300)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bones_images", to=settings.AUTH_USER_MODEL)),
            ], options={"ordering": ("-uploaded_at",)},
        ),
        migrations.AddIndex(model_name="entityimage", index=models.Index(fields=["entity_type", "entity_id"], name="bones_image_entity_idx")),
    ]
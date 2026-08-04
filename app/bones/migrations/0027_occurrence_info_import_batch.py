import uuid

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("bones", "0026_mni_weathering_corrected_ages"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="OccurrenceInfoImportBatch",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("original_filename", models.CharField(max_length=255)),
                ("file_checksum", models.CharField(db_index=True, max_length=64)),
                ("status", models.CharField(choices=[("preview", "Preview"), ("completed", "Completed"), ("failed", "Failed")], default="preview", max_length=20)),
                ("summary", models.JSONField(blank=True, default=dict, encoder=DjangoJSONEncoder)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bones_occurrence_info_imports", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("-created_at",),
                "permissions": (("run_occurrence_info_import", "Can import occurrence-info answers"),),
            },
        ),
    ]

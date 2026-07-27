import uuid

from django.db import migrations
from django.utils import timezone


def populate_targets(apps, schema_editor):
    EntityImage = apps.get_model("bones", "EntityImage")
    EntityImageTarget = apps.get_model("bones", "EntityImageTarget")
    HistoricalEntityImageTarget = apps.get_model("bones", "HistoricalEntityImageTarget")
    database = schema_editor.connection.alias
    now = timezone.now()
    targets = []
    history = []
    for image in EntityImage.objects.using(database).all().iterator(chunk_size=500):
        target_id = uuid.uuid4()
        values = {
            "id": target_id,
            "image_id": image.pk,
            "entity_type": image.entity_type,
            "entity_id": image.entity_id,
            "linked_by_id": image.uploaded_by_id,
            "linked_at": now,
        }
        targets.append(EntityImageTarget(**values))
        history.append(
            HistoricalEntityImageTarget(
                **values,
                history_date=now,
                history_type="+",
                history_change_reason="Baseline image target",
            )
        )
    EntityImageTarget.objects.using(database).bulk_create(targets, batch_size=500)
    HistoricalEntityImageTarget.objects.using(database).bulk_create(history, batch_size=500)


class Migration(migrations.Migration):
    dependencies = [("bones", "0015_image_targets")]
    operations = [migrations.RunPython(populate_targets, migrations.RunPython.noop)]
import hashlib
from pathlib import Path
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import migrations, models
import bones.models.images


def retry_move(apps, schema_editor):
    EntityImage=apps.get_model("bones","EntityImage")
    Occurrence=apps.get_model("bones","CompletedOccurrence")
    for image in EntityImage.objects.filter(parsed_metadata={}):
        if image.entity_type=="transect":
            metadata={"transect_uid":int(image.entity_id)}; base=f"bones/images/transects/{image.entity_id}/direct/{(image.photo_role or 'direct').lower()}"
        else:
            occurrence_id=str(image.entity_id).split(":",1)[0]
            with schema_editor.connection.cursor() as cursor:
                cursor.execute("SELECT [TransectUID], [OccurrenceNumber] FROM [CompletedOccurrences] WHERE [ID] = %s", [occurrence_id])
                transect_uid, occurrence_number = cursor.fetchone()
            metadata={"transect_uid":transect_uid,"occurrence_id":int(occurrence_id),"occurrence_number":occurrence_number}
            base=f"bones/images/transects/{transect_uid}/occurrences/{occurrence_number}-{occurrence_id}"
            if image.entity_type=="instance":
                number=int(str(image.entity_id).split(":",1)[1]); metadata["instance_number"]=number; base+=f"/instances/{number}"
            else: base+="/direct"
        old_image=image.image.name; old_thumb=image.thumbnail.name; ext=Path(old_image).suffix.lower() or ".jpg"
        new_image=f"{base}/originals/{image.pk}{ext}"; new_thumb=f"{base}/thumbnails/{image.pk}.webp"
        if old_image and default_storage.exists(old_image):
            with default_storage.open(old_image,"rb") as source: data=source.read()
            if not default_storage.exists(new_image): default_storage.save(new_image,ContentFile(data))
            image.checksum=hashlib.sha256(data).hexdigest(); image.image.name=new_image
        if old_thumb and default_storage.exists(old_thumb):
            with default_storage.open(old_thumb,"rb") as source: data=source.read()
            if not default_storage.exists(new_thumb): default_storage.save(new_thumb,ContentFile(data))
            image.thumbnail.name=new_thumb
        image.parsed_metadata=metadata; image.save(update_fields=["image","thumbnail","checksum","parsed_metadata"])
        if old_image!=new_image: default_storage.delete(old_image)
        if old_thumb!=new_thumb: default_storage.delete(old_thumb)

class Migration(migrations.Migration):
    dependencies=[("bones","0011_move_existing_images")]
    operations=[
        migrations.RunSQL(
            sql="ALTER TABLE [bones_entityimage] ALTER COLUMN [image] nvarchar(500) NOT NULL; ALTER TABLE [bones_entityimage] ALTER COLUMN [thumbnail] nvarchar(500) NULL;",
            reverse_sql=migrations.RunSQL.noop,
            state_operations=[
                migrations.AlterField(model_name="entityimage", name="image", field=models.ImageField(max_length=500, upload_to=bones.models.images.entity_image_path)),
                migrations.AlterField(model_name="entityimage", name="thumbnail", field=models.ImageField(blank=True, max_length=500, upload_to=bones.models.images.entity_thumbnail_path)),
            ],
        ),
        migrations.RunPython(retry_move,migrations.RunPython.noop),
    ]
import hashlib
from pathlib import Path
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db import migrations


def move_existing(apps, schema_editor):
    EntityImage=apps.get_model("bones","EntityImage"); Occurrence=apps.get_model("bones","CompletedOccurrence")
    for image in EntityImage.objects.all():
        metadata={}; base="bones/images/transects/unknown"
        try:
            if image.entity_type=="transect": metadata={"transect_uid":int(image.entity_id)}; base=f"bones/images/transects/{image.entity_id}/direct/{(image.photo_role or 'direct').lower()}"
            else:
                occurrence_id=image.entity_id.split(":",1)[0]; occurrence=Occurrence.objects.get(pk=occurrence_id)
                metadata={"transect_uid":occurrence.transect_id,"occurrence_id":occurrence.pk,"occurrence_number":occurrence.occurrence_number}
                base=f"bones/images/transects/{occurrence.transect_id}/occurrences/{occurrence.occurrence_number}-{occurrence.pk}"
                if image.entity_type=="instance":
                    number=int(image.entity_id.split(":",1)[1]); metadata["instance_number"]=number; base+=f"/instances/{number}"
                else: base+="/direct"
        except Exception: continue
        old_image=image.image.name; old_thumb=image.thumbnail.name
        ext=Path(old_image).suffix.lower() or ".jpg"; new_image=f"{base}/originals/{image.pk}{ext}"; new_thumb=f"{base}/thumbnails/{image.pk}.webp"
        if old_image and default_storage.exists(old_image):
            with default_storage.open(old_image,"rb") as source: data=source.read()
            if not default_storage.exists(new_image): default_storage.save(new_image, ContentFile(data))
            image.checksum=hashlib.sha256(data).hexdigest()
            if old_image!=new_image: default_storage.delete(old_image)
            image.image.name=new_image
        if old_thumb and default_storage.exists(old_thumb):
            with default_storage.open(old_thumb,"rb") as source: data=source.read()
            if not default_storage.exists(new_thumb): default_storage.save(new_thumb, ContentFile(data))
            if old_thumb!=new_thumb: default_storage.delete(old_thumb)
            image.thumbnail.name=new_thumb
        image.parsed_metadata=metadata; image.save(update_fields=["image","thumbnail","checksum","parsed_metadata"])

class Migration(migrations.Migration):
    dependencies=[("bones","0010_image_imports")]
    operations=[migrations.RunPython(move_existing,migrations.RunPython.noop)]
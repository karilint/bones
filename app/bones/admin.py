from __future__ import annotations
import mimetypes, zipfile
from io import BytesIO
from pathlib import Path
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone
from .image_forms import MultipleFileField, MultipleFileInput
from .image_imports import resolve_filename
from .image_views import save_image
from .models import CompletedOccurrence, EntityImage, ImageImportBatch

ALLOWED={".jpg",".jpeg",".png",".webp"}; MAX=20*1024*1024
class MultiInput(forms.ClearableFileInput): allow_multiple_selected=True
class BulkForm(forms.Form):
    files=MultipleFileField(required=False, widget=MultipleFileInput(attrs={"accept":".jpg,.jpeg,.png,.webp,.zip"}))
    scan_inbox=forms.BooleanField(required=False, help_text="Scan media/bones/import-inbox")

@admin.register(EntityImage)
class EntityImageAdmin(admin.ModelAdmin):
    list_display=("original_name","entity_type","entity_id","source_schema","uploaded_by","uploaded_at","archived_by_deletion","archived_by_occurrence_deletion","archived_by_transect_deletion")
    readonly_fields=("checksum","exif_metadata","parsed_metadata","uploaded_at")
    def has_delete_permission(self,request,obj=None):
        if obj is not None and (obj.archived_by_deletion_id or obj.archived_by_occurrence_deletion_id or obj.archived_by_transect_deletion_id):
            return False
        return super().has_delete_permission(request,obj)
    def get_actions(self,request):
        actions=super().get_actions(request); actions.pop("delete_selected",None); return actions
    def get_urls(self):
        return [path("bulk-import/",self.admin_site.admin_view(self.bulk_import),name="bones_entityimage_bulk"),path("bulk-import/<uuid:batch_id>/",self.admin_site.admin_view(self.bulk_preview),name="bones_entityimage_bulk_preview")]+super().get_urls()
    def _allowed(self,request): return request.user.has_perm("bones.run_image_import") and request.user.has_perm("bones.add_entityimage")
    def changelist_view(self,request,extra_context=None):
        extra_context={**(extra_context or {}),"bulk_import_url":reverse("admin:bones_entityimage_bulk")}; return super().changelist_view(request,extra_context)
    def bulk_import(self,request):
        if not self._allowed(request): return HttpResponseForbidden()
        form=BulkForm(request.POST or None,request.FILES or None)
        if request.method=="POST" and form.is_valid():
            batch=ImageImportBatch(created_by=request.user,source_kind="inbox" if form.cleaned_data["scan_inbox"] else "upload")
            batch._history_user=request.user; batch._change_reason="Bulk image import started"; batch.save()
            staged=[]
            def stage(name,data):
                if Path(name).suffix.lower() not in ALLOWED or len(data)>MAX: return
                safe=Path(name).name; storage_name=default_storage.save(f"bones/import-inbox/{batch.pk}/{safe}",ContentFile(data)); staged.append((safe,storage_name))
            for upload in request.FILES.getlist("files"):
                raw=upload.read()
                if Path(upload.name).suffix.lower()==".zip":
                    try:
                        with zipfile.ZipFile(BytesIO(raw)) as archive:
                            for info in archive.infolist():
                                if info.is_dir() or info.file_size>MAX or ".." in Path(info.filename).parts: continue
                                if Path(info.filename).suffix.lower() in ALLOWED: stage(info.filename,archive.read(info))
                    except zipfile.BadZipFile: messages.error(request,f"Invalid ZIP: {upload.name}")
                else: stage(upload.name,raw)
            if form.cleaned_data["scan_inbox"]:
                inbox=Path(settings.MEDIA_ROOT)/"bones"/"import-inbox"
                if inbox.exists():
                    for file in inbox.iterdir():
                        if file.is_file() and file.suffix.lower() in ALLOWED and file.stat().st_size<=MAX: stage(file.name,file.read_bytes())
            items=[]
            for name,storage_name in staged:
                resolved=resolve_filename(name); resolved["storage_name"]=storage_name; items.append(resolved)
            batch.summary={"items":items}; batch._history_user=request.user; batch._change_reason="Bulk image import preview prepared"; batch.save(update_fields=["summary"])
            return redirect("admin:bones_entityimage_bulk_preview",batch_id=batch.pk)
        return render(request,"admin/bones/entityimage/bulk_import.html",{**self.admin_site.each_context(request),"form":form,"title":"Bulk image import"})
    def bulk_preview(self,request,batch_id):
        if not self._allowed(request): return HttpResponseForbidden()
        batch=get_object_or_404(ImageImportBatch,pk=batch_id); items=batch.summary.get("items",[])
        if request.method=="POST":
            imported=skipped=links_created=0
            for index,item in enumerate(items):
                if item["status"]=="ambiguous":
                    selected=request.POST.get(f"candidate_{index}")
                    candidate=next((x for x in item["candidates"] if str(x["id"])==selected),None)
                    if not candidate: continue
                    occurrence=CompletedOccurrence.objects.get(pk=candidate["id"]); item["entity_type"]="occurrence"; item["entity_id"]=str(occurrence.pk); item["metadata"].update({key: value for key, value in candidate.items() if key not in {"id", "label"}}); item["metadata"].update(occurrence_id=occurrence.pk); item["status"]="ready"
                if item["status"]!="ready": continue
                with default_storage.open(item["storage_name"],"rb") as source:
                    data=source.read()
                upload=SimpleUploadedFile(item["filename"],data,content_type=mimetypes.guess_type(item["filename"])[0] or "application/octet-stream")
                image = save_image(upload,item["entity_type"],item["entity_id"],request.user,parsed_metadata=item["metadata"],source_schema=item["schema"],photo_role=item["metadata"].get("photo_role","") ,import_batch=batch,targets=item.get("targets"))
                imported += int(image._asset_created); links_created += image._links_created; skipped += int(not image._asset_created and not image._links_created)
            batch.status="completed"; batch.completed_at=timezone.now(); batch.summary={"items":items,"imported":imported,"links_created":links_created,"duplicates":skipped}; batch._history_user=request.user; batch._change_reason="Bulk image import completed"; batch.save()
            messages.success(request,f"Stored {imported} new images and created {links_created} links; skipped {skipped} complete duplicates."); return redirect("admin:bones_entityimage_changelist")
        return render(request,"admin/bones/entityimage/bulk_preview.html",{**self.admin_site.each_context(request),"batch":batch,"items":items,"title":"Review image import"})

@admin.register(ImageImportBatch)
class ImageImportBatchAdmin(admin.ModelAdmin):
    list_display=("id","status","source_kind","created_by","created_at","completed_at")
    readonly_fields=("id","status","source_kind","summary","created_by","created_at","completed_at")
    def has_add_permission(self,request): return False

# Register the grouped instance deletion workflow.
from . import instance_admin  # noqa: E402,F401
from . import occurrence_admin  # noqa: E402,F401
from . import transect_admin  # noqa: E402,F401
from . import admin_general  # noqa: E402,F401

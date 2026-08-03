from __future__ import annotations

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse

from .image_catalog import write_image_index
from .models import (CompletedOccurrence, CompletedOccurrenceInfo,
                     CompletedResponse, CompletedWorkflow, EntityImageTarget,
                     OccurrenceDeletion)


class OccurrenceSearchForm(forms.Form):
    occurrence_id=forms.IntegerField(required=False,min_value=1,label="Occurrence ID")
    occurrence_number=forms.IntegerField(required=False,min_value=1)
    transect_uid=forms.IntegerField(required=False,min_value=1,label="Transect UID")
    template_name=forms.CharField(required=False,max_length=200,label="Template transect")
    def clean(self):
        cleaned=super().clean()
        if not any(value not in (None,"") for value in cleaned.values()):
            raise forms.ValidationError("Enter at least one search value.")
        return cleaned


class OccurrenceDeletionForm(forms.Form):
    reason=forms.CharField(max_length=100,widget=forms.Textarea(attrs={"rows":3}))
    confirm=forms.BooleanField(label="I confirm that this occurrence and all dependent workflows and responses should be deleted")


def _values(objects):
    return [{field.attname:getattr(obj,field.attname) for field in obj._meta.concrete_fields} for obj in objects]


def _summary(occurrence_id,*,lock=False):
    queryset=CompletedOccurrence.objects.select_related("transect__transect_template")
    occurrence=get_object_or_404(queryset.select_for_update() if lock else queryset,pk=occurrence_id)
    workflows=list(CompletedWorkflow.objects.filter(occurrence_id=occurrence_id))
    workflow_ids=[item.pk for item in workflows]
    data={
        "occurrence":occurrence,
        "workflows":workflows,
        "responses":list(CompletedResponse.objects.filter(workflow_id__in=workflow_ids)),
        "occurrence_info":list(CompletedOccurrenceInfo.objects.filter(occurrence_id=occurrence_id)),
    }
    targets=Q(entity_type="occurrence",entity_id=str(occurrence_id))
    for instance_number in {workflow.instance_number for workflow in workflows}:
        targets|=Q(entity_type="instance",entity_id=f"{occurrence_id}:{instance_number}")
    data["image_links"]=list(EntityImageTarget.objects.filter(targets).select_related("image").distinct())
    scope_link_ids=[link.pk for link in data["image_links"]]
    seen_images=set(); exclusive=[]
    for link in data["image_links"]:
        if link.image_id not in seen_images and not link.image.targets.exclude(pk__in=scope_link_ids).exists():
            exclusive.append(link); seen_images.add(link.image_id)
    data["exclusive_images"]=exclusive
    return data


@admin.register(OccurrenceDeletion)
class OccurrenceDeletionAdmin(admin.ModelAdmin):
    change_list_template="admin/bones/occurrencedeletion/change_list.html"
    list_display=("deleted_at","template_name","transect_uid","occurrence_number","occurrence_id","deleted_by","reason")
    search_fields=("template_name","=transect_uid","=occurrence_number","=occurrence_id","deleted_by__username","reason")
    readonly_fields=tuple(field.name for field in OccurrenceDeletion._meta.fields)
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False
    def get_urls(self):
        return [
            path("find/",self.admin_site.admin_view(self.find_occurrence),name="bones_occurrencedeletion_find"),
            path("delete/<int:occurrence_id>/",self.admin_site.admin_view(self.delete_occurrence),name="bones_occurrencedeletion_delete_occurrence"),
        ]+super().get_urls()
    def changelist_view(self,request,extra_context=None):
        return super().changelist_view(request,{**(extra_context or {}),"find_occurrence_url":reverse("admin:bones_occurrencedeletion_find")})
    @staticmethod
    def _require_permission(request):
        if not request.user.has_perm("bones.delete_completed_occurrence"): raise PermissionDenied
    def find_occurrence(self,request):
        self._require_permission(request); form=OccurrenceSearchForm(request.GET or None); results=[]
        if request.GET and form.is_valid():
            queryset=CompletedOccurrence.objects.select_related("transect__transect_template"); values=form.cleaned_data
            if values["occurrence_id"]: queryset=queryset.filter(pk=values["occurrence_id"])
            if values["occurrence_number"]: queryset=queryset.filter(occurrence_number=values["occurrence_number"])
            if values["transect_uid"]: queryset=queryset.filter(transect_id=values["transect_uid"])
            if values["template_name"]: queryset=queryset.filter(transect__transect_template__name__icontains=values["template_name"])
            for occurrence in queryset.order_by("-recording_start_time")[:100]:
                occurrence.deletion_url=reverse("admin:bones_occurrencedeletion_delete_occurrence",kwargs={"occurrence_id":occurrence.pk}); results.append(occurrence)
        return render(request,"admin/bones/occurrencedeletion/find_occurrence.html",{**self.admin_site.each_context(request),"title":"Find a completed occurrence to delete","form":form,"results":results,"opts":self.model._meta})
    def delete_occurrence(self,request,occurrence_id):
        self._require_permission(request); summary=_summary(occurrence_id); form=OccurrenceDeletionForm(request.POST or None)
        if request.method=="POST" and form.is_valid():
            reason=form.cleaned_data["reason"]
            with transaction.atomic():
                summary=_summary(occurrence_id,lock=True); occurrence=summary["occurrence"]; transect=occurrence.transect
                audit=OccurrenceDeletion(
                    occurrence_id=occurrence.pk,occurrence_number=occurrence.occurrence_number,transect_uid=occurrence.transect_id,
                    template_name=transect.transect_template.name if transect.transect_template else "Unknown template",
                    reason=reason,deleted_by=request.user,workflow_count=len(summary["workflows"]),response_count=len(summary["responses"]),
                    snapshot={"occurrence":_values([occurrence])[0],**{key:_values(summary[key]) for key in ("workflows","responses","occurrence_info")}},
                )
                audit._history_user=request.user; audit._change_reason="Completed occurrence deletion audit created"; audit.save()
                exclusive_ids={link.image_id for link in summary["exclusive_images"]}
                for link in summary["image_links"]:
                    image=link.image; link._history_user=request.user; link._change_reason=reason; link.delete()
                    if image.pk in exclusive_ids:
                        image.archived_by_occurrence_deletion=audit; image._history_user=request.user; image._change_reason=reason; image.save(update_fields=["archived_by_occurrence_deletion"])
                for key in ("responses","workflows","occurrence_info"):
                    for obj in summary[key]: obj._history_user=request.user; obj._change_reason=reason; obj.delete()
                occurrence._history_user=request.user; occurrence._change_reason=reason; occurrence.delete(); transaction.on_commit(write_image_index)
            messages.success(request,f"Occurrence {occurrence_id} was deleted and retained in the audit log.")
            return redirect("admin:bones_occurrencedeletion_change",object_id=audit.pk)
        return render(request,"admin/bones/occurrencedeletion/delete_occurrence.html",{**self.admin_site.each_context(request),"title":"Delete completed occurrence","form":form,"summary":summary,"opts":self.model._meta})

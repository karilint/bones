from __future__ import annotations

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse

from .image_catalog import write_image_index
from .models import (
    CompletedOccurrence, CompletedOccurrenceInfo, CompletedResponse,
    CompletedTransect, CompletedTransectInfo, CompletedTransectTrack,
    CompletedWorkflow, EntityImageTarget, TransectDataLog, TransectDeletion,
)


class TransectSearchForm(forms.Form):
    transect_uid = forms.IntegerField(required=False, min_value=1, label="Transect UID")
    transect_name = forms.CharField(required=False, max_length=200)
    template_name = forms.CharField(required=False, max_length=200, label="Template transect")

    def clean(self):
        cleaned = super().clean()
        if not any(value not in (None, "") for value in cleaned.values()):
            raise forms.ValidationError("Enter at least one search value.")
        return cleaned


class TransectDeletionForm(forms.Form):
    reason = forms.CharField(max_length=100, widget=forms.Textarea(attrs={"rows": 3}))
    confirm = forms.BooleanField(
        label="I confirm that this completed transect and all dependent data should be deleted"
    )


def _values(objects):
    return [
        {field.attname: getattr(obj, field.attname) for field in obj._meta.concrete_fields}
        for obj in objects
    ]


def _summary(transect_uid, *, lock=False):
    queryset = CompletedTransect.objects.select_related("transect_template")
    transect = get_object_or_404(queryset.select_for_update() if lock else queryset, pk=transect_uid)
    occurrences = list(CompletedOccurrence.objects.filter(transect_id=transect_uid))
    occurrence_ids = [item.pk for item in occurrences]
    workflows = list(CompletedWorkflow.objects.filter(occurrence_id__in=occurrence_ids))
    workflow_ids = [item.pk for item in workflows]
    data = {
        "transect": transect,
        "occurrences": occurrences,
        "workflows": workflows,
        "responses": list(CompletedResponse.objects.filter(workflow_id__in=workflow_ids)),
        "occurrence_info": list(CompletedOccurrenceInfo.objects.filter(occurrence_id__in=occurrence_ids)),
        "transect_info": list(CompletedTransectInfo.objects.filter(transect_id=transect_uid)),
        "track_points": list(CompletedTransectTrack.objects.filter(transect_id=transect_uid)),
        "data_logs": list(TransectDataLog.objects.filter(transect_id=transect_uid)),
    }
    targets = Q(entity_type="transect", entity_id=str(transect_uid))
    for occurrence_id in occurrence_ids:
        targets |= Q(entity_type="occurrence", entity_id=str(occurrence_id))
    for workflow in workflows:
        targets |= Q(entity_type="instance", entity_id=f"{workflow.occurrence_id}:{workflow.instance_number}")
    data["image_links"] = list(EntityImageTarget.objects.filter(targets).select_related("image").distinct())
    data["exclusive_images"] = [link for link in data["image_links"] if link.image.targets.count() == 1]
    return data


@admin.register(TransectDeletion)
class TransectDeletionAdmin(admin.ModelAdmin):
    change_list_template = "admin/bones/transectdeletion/change_list.html"
    list_display = ("deleted_at", "template_name", "transect_uid", "transect_name", "deleted_by", "reason")
    search_fields = ("template_name", "=transect_uid", "transect_name", "deleted_by__username", "reason")
    readonly_fields = tuple(field.name for field in TransectDeletion._meta.fields)

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

    def get_urls(self):
        return [
            path("find/", self.admin_site.admin_view(self.find_transect), name="bones_transectdeletion_find"),
            path("delete/<int:transect_uid>/", self.admin_site.admin_view(self.delete_transect), name="bones_transectdeletion_delete_transect"),
        ] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, {**(extra_context or {}), "find_transect_url": reverse("admin:bones_transectdeletion_find")})

    @staticmethod
    def _require_permission(request):
        if not request.user.has_perm("bones.delete_completed_transect"):
            raise PermissionDenied

    def find_transect(self, request):
        self._require_permission(request)
        form = TransectSearchForm(request.GET or None)
        results = []
        if request.GET and form.is_valid():
            queryset = CompletedTransect.objects.select_related("transect_template")
            values = form.cleaned_data
            if values["transect_uid"]: queryset = queryset.filter(pk=values["transect_uid"])
            if values["transect_name"]: queryset = queryset.filter(name__icontains=values["transect_name"])
            if values["template_name"]: queryset = queryset.filter(transect_template__name__icontains=values["template_name"])
            for transect in queryset.order_by("-start_time")[:100]:
                transect.deletion_url = reverse("admin:bones_transectdeletion_delete_transect", kwargs={"transect_uid": transect.pk})
                results.append(transect)
        return render(request, "admin/bones/transectdeletion/find_transect.html", {**self.admin_site.each_context(request), "title": "Find a completed transect to delete", "form": form, "results": results, "opts": self.model._meta})

    def delete_transect(self, request, transect_uid):
        self._require_permission(request)
        summary = _summary(transect_uid)
        form = TransectDeletionForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            reason = form.cleaned_data["reason"]
            with transaction.atomic():
                summary = _summary(transect_uid, lock=True)
                transect = summary["transect"]
                audit = TransectDeletion(
                    transect_uid=transect.pk, transect_name=transect.name,
                    template_name=transect.transect_template.name if transect.transect_template else "Unknown template",
                    transect_date=transect.start_time.date() if transect.start_time else None,
                    reason=reason, deleted_by=request.user,
                    occurrence_count=len(summary["occurrences"]), workflow_count=len(summary["workflows"]),
                    response_count=len(summary["responses"]),
                    snapshot={"transect": _values([transect])[0], **{key: _values(summary[key]) for key in ("occurrences", "workflows", "responses", "occurrence_info", "transect_info", "track_points", "data_logs")}},
                )
                audit._history_user = request.user; audit._change_reason = "Completed transect deletion audit created"; audit.save()
                exclusive_ids = {link.image_id for link in summary["exclusive_images"]}
                for link in summary["image_links"]:
                    image = link.image; link._history_user = request.user; link._change_reason = reason; link.delete()
                    if image.pk in exclusive_ids:
                        image.archived_by_transect_deletion = audit; image._history_user = request.user; image._change_reason = reason; image.save(update_fields=["archived_by_transect_deletion"])
                for key in ("responses", "workflows", "occurrence_info", "occurrences", "transect_info", "track_points", "data_logs"):
                    for obj in summary[key]: obj._history_user = request.user; obj._change_reason = reason; obj.delete()
                transect._history_user = request.user; transect._change_reason = reason; transect.delete()
                transaction.on_commit(write_image_index)
            messages.success(request, f"Transect {transect_uid} was deleted and retained in the audit log.")
            return redirect("admin:bones_transectdeletion_change", object_id=audit.pk)
        return render(request, "admin/bones/transectdeletion/delete_transect.html", {**self.admin_site.each_context(request), "title": "Delete completed transect", "form": form, "summary": summary, "opts": self.model._meta})

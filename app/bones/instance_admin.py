from __future__ import annotations

from collections import OrderedDict

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone

from .image_catalog import write_image_index
from .models import (
    CompletedOccurrence,
    CompletedResponse,
    CompletedWorkflow,
    EntityImage,
    EntityImageTarget,
    InstanceDeletion,
    Question,
    TemplateWorkflow,
)
from .models.images import remove_empty_image_directories


class InstanceSearchForm(forms.Form):
    template_name = forms.CharField(required=False, max_length=200, label="Template transect")
    transect_uid = forms.IntegerField(required=False, min_value=1, label="Transect UID")
    occurrence_number = forms.IntegerField(required=False, min_value=1)
    occurrence_id = forms.IntegerField(required=False, min_value=1, label="Occurrence ID")
    instance_number = forms.IntegerField(required=False, min_value=1)
    completed_by = forms.CharField(required=False, max_length=100)

    def clean(self):
        cleaned = super().clean()
        if not any(value not in (None, "") for value in cleaned.values()):
            raise forms.ValidationError("Enter at least one search value.")
        return cleaned


class InstanceDeletionForm(forms.Form):
    reason = forms.CharField(
        max_length=100,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Required. This is stored in every deletion history record.",
    )
    confirm = forms.BooleanField(label="I confirm that this complete instance should be deleted")


class InstanceRestorationForm(forms.Form):
    reason = forms.CharField(
        max_length=100,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Required. This is stored in every restoration history record.",
    )
    confirm = forms.BooleanField(label="I confirm that this instance should be restored")

def _instance_queryset(occurrence_id, instance_number, *, lock=False):
    queryset = CompletedWorkflow.objects.filter(
        occurrence_id=occurrence_id,
        instance_number=instance_number,
    ).select_related(
        "occurrence__transect__transect_template",
        "template_workflow",
    )
    return queryset.select_for_update() if lock else queryset


def _instance_summary(occurrence_id, instance_number, *, lock=False):
    workflows = list(_instance_queryset(occurrence_id, instance_number, lock=lock))
    if not workflows:
        raise Http404("Instance no longer exists.")
    occurrence = workflows[0].occurrence
    workflow_ids = [workflow.pk for workflow in workflows]
    responses = CompletedResponse.objects.filter(workflow_id__in=workflow_ids)
    links = EntityImageTarget.objects.filter(
        entity_type="instance",
        entity_id=f"{occurrence_id}:{instance_number}",
    ).select_related("image")
    exclusive_images = sum(1 for link in links if link.image.targets.count() == 1)
    return {
        "workflows": workflows,
        "occurrence": occurrence,
        "response_count": responses.count(),
        "image_links": list(links),
        "exclusive_image_count": exclusive_images,
    }




def _restoration_conflicts(audit):
    conflicts = []
    if audit.restoration_status != "deleted":
        conflicts.append("This deletion has already been restored or is not restorable.")
    try:
        occurrence = CompletedOccurrence.objects.select_related("transect").get(pk=audit.occurrence_id)
    except CompletedOccurrence.DoesNotExist:
        conflicts.append("The parent occurrence no longer exists.")
        occurrence = None
    if occurrence and (
        occurrence.transect_id != audit.transect_uid
        or occurrence.occurrence_number != audit.occurrence_number
    ):
        conflicts.append("The parent occurrence no longer matches the deletion snapshot.")
    if CompletedWorkflow.objects.filter(
        occurrence_id=audit.occurrence_id,
        instance_number=audit.instance_number,
    ).exists():
        conflicts.append("An active instance already uses this occurrence and instance number.")
    workflow_ids = [item["uid"] for item in audit.workflow_snapshot]
    existing_workflows = set(
        CompletedWorkflow.objects.filter(pk__in=workflow_ids).values_list("pk", flat=True)
    )
    if existing_workflows:
        conflicts.append(f"Workflow UIDs already exist: {', '.join(sorted(existing_workflows))}.")
    response_ids = [item["id"] for item in audit.response_snapshot]
    existing_responses = list(
        CompletedResponse.objects.filter(pk__in=response_ids).values_list("pk", flat=True)
    )
    if existing_responses:
        conflicts.append(f"Response IDs already exist: {', '.join(str(value) for value in existing_responses)}.")
    template_ids = {item["template_workflow_id"] for item in audit.workflow_snapshot}
    found_templates = set(
        TemplateWorkflow.objects.filter(pk__in=template_ids).values_list("pk", flat=True)
    )
    missing_templates = template_ids - found_templates
    if missing_templates:
        conflicts.append(f"Template workflows are missing: {', '.join(sorted(missing_templates))}.")
    question_ids = {item["question_id"] for item in audit.response_snapshot}
    found_questions = set(Question.objects.filter(pk__in=question_ids).values_list("pk", flat=True))
    missing_questions = question_ids - found_questions
    if missing_questions:
        conflicts.append(f"Questions are missing: {', '.join(sorted(missing_questions))}.")
    for item in audit.image_snapshot:
        image = EntityImage.objects.filter(pk=item["image_id"]).first()
        if image is None:
            conflicts.append(f"Image {item['image_id']} no longer exists.")
            continue
        if item.get("archived"):
            if image.archived_by_deletion_id != audit.pk:
                conflicts.append(f"Image {image.pk} is not archived by this deletion.")
            if not image.image or not image.image.storage.exists(image.image.name):
                conflicts.append(f"Original file for image {image.pk} is missing.")
            if image.thumbnail and not image.thumbnail.storage.exists(image.thumbnail.name):
                conflicts.append(f"Thumbnail for image {image.pk} is missing.")
    return conflicts

@admin.register(InstanceDeletion)
class InstanceDeletionAdmin(admin.ModelAdmin):
    change_list_template = "admin/bones/instancedeletion/change_list.html"
    change_form_template = "admin/bones/instancedeletion/change_form.html"
    list_display = (
        "deleted_at",
        "template_name",
        "transect_uid",
        "occurrence_number",
        "occurrence_id",
        "instance_number",
        "deleted_by",
        "reason",
        "restoration_status",
        "restored_by",
        "restored_at",
    )
    search_fields = (
        "template_name",
        "=transect_uid",
        "=occurrence_number",
        "=occurrence_id",
        "=instance_number",
        "deleted_by__username",
        "reason",
        "restoration_status",
        "restored_by",
        "restored_at",
    )
    list_filter = ("deleted_at", "template_name", "deleted_by")
    readonly_fields = tuple(field.name for field in InstanceDeletion._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("bones.view_instancedeletion")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        custom = [
            path(
                "find/",
                self.admin_site.admin_view(self.find_instance),
                name="bones_instancedeletion_find",
            ),
            path(
                "restore/<uuid:audit_id>/",
                self.admin_site.admin_view(self.restore_instance),
                name="bones_instancedeletion_restore_instance",
            ),
            path(
                "delete/<int:occurrence_id>/<int:instance_number>/",
                self.admin_site.admin_view(self.delete_instance),
                name="bones_instancedeletion_delete_instance",
            ),
        ]
        return custom + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        context = {
            **(extra_context or {}),
            "find_instance_url": reverse("admin:bones_instancedeletion_find"),
        }
        return super().changelist_view(request, context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        obj = self.get_object(request, object_id)
        restore_url = None
        if (
            obj
            and obj.restoration_status == "deleted"
            and request.user.has_perm("bones.restore_completed_instance")
        ):
            restore_url = reverse(
                "admin:bones_instancedeletion_restore_instance",
                kwargs={"audit_id": obj.pk},
            )
        return super().change_view(
            request,
            object_id,
            form_url,
            {**(extra_context or {}), "restore_instance_url": restore_url},
        )

    def _require_restore_permission(self, request):
        if not request.user.has_perm("bones.restore_completed_instance"):
            raise PermissionDenied

    def restore_instance(self, request, audit_id):
        self._require_restore_permission(request)
        audit = get_object_or_404(InstanceDeletion, pk=audit_id)
        conflicts = _restoration_conflicts(audit)
        form = InstanceRestorationForm(request.POST or None)
        if request.method == "POST" and form.is_valid() and not conflicts:
            reason = form.cleaned_data["reason"]
            with transaction.atomic():
                audit = InstanceDeletion.objects.select_for_update().get(pk=audit_id)
                conflicts = _restoration_conflicts(audit)
                if conflicts:
                    form.add_error(None, "The restoration preflight changed; review the conflicts below.")
                else:
                    for item in audit.workflow_snapshot:
                        workflow = CompletedWorkflow(
                            uid=item["uid"],
                            occurrence_id=item["occurrence_id"],
                            template_workflow_id=item["template_workflow_id"],
                            instance_number=item["instance_number"],
                            completed_by=item["completed_by"],
                        )
                        workflow._history_user = request.user
                        workflow._change_reason = reason
                        workflow.save(force_insert=True)
                    for item in audit.response_snapshot:
                        response = CompletedResponse(
                            id=item["id"],
                            occurrence_id=item["occurrence_id"],
                            workflow_id=item["workflow_id"],
                            question_number=item["question_number"],
                            question_text=item["question_text"],
                            response_code=item["response_code"],
                            response=item["response"],
                            skipped=item["skipped"],
                            question_id=item["question_id"],
                        )
                        response._history_user = request.user
                        response._change_reason = reason
                        response.save(force_insert=True)
                    for item in audit.image_snapshot:
                        image = EntityImage.objects.get(pk=item["image_id"])
                        if not image.targets.filter(
                            entity_type=item["entity_type"], entity_id=item["entity_id"]
                        ).exists():
                            link = EntityImageTarget(
                                image=image,
                                entity_type=item["entity_type"],
                                entity_id=item["entity_id"],
                                linked_by=request.user,
                            )
                            link._history_user = request.user
                            link._change_reason = reason
                            link.save()
                        if item.get("archived"):
                            image.archived_by_deletion = None
                            image._history_user = request.user
                            image._change_reason = reason
                            image.save(update_fields=["archived_by_deletion"])
                    audit.restoration_status = "restored"
                    audit.restored_at = timezone.now()
                    audit.restored_by = request.user
                    audit.restoration_reason = reason
                    audit.restoration_error = ""
                    audit._history_user = request.user
                    audit._change_reason = reason
                    audit.save(
                        update_fields=[
                            "restoration_status", "restored_at", "restored_by",
                            "restoration_reason", "restoration_error",
                        ]
                    )
                    transaction.on_commit(write_image_index)
                    messages.success(request, f"Instance {audit.instance_number} was restored.")
                    return redirect("admin:bones_instancedeletion_change", object_id=audit.pk)
        return render(
            request,
            "admin/bones/instancedeletion/restore_instance.html",
            {
                **self.admin_site.each_context(request),
                "title": "Restore completed instance",
                "audit": audit,
                "form": form,
                "conflicts": conflicts,
                "opts": self.model._meta,
            },
        )
    def _require_delete_permission(self, request):
        if not request.user.has_perm("bones.delete_completed_instance"):
            raise PermissionDenied

    def find_instance(self, request):
        self._require_delete_permission(request)
        form = InstanceSearchForm(request.GET or None)
        results = []
        if request.GET and form.is_valid():
            values = form.cleaned_data
            queryset = CompletedWorkflow.objects.select_related(
                "occurrence__transect__transect_template",
                "template_workflow",
            )
            if values["template_name"]:
                queryset = queryset.filter(
                    occurrence__transect__transect_template__name__icontains=values["template_name"]
                )
            if values["transect_uid"]:
                queryset = queryset.filter(occurrence__transect_id=values["transect_uid"])
            if values["occurrence_number"]:
                queryset = queryset.filter(occurrence__occurrence_number=values["occurrence_number"])
            if values["occurrence_id"]:
                queryset = queryset.filter(occurrence_id=values["occurrence_id"])
            if values["instance_number"]:
                queryset = queryset.filter(instance_number=values["instance_number"])
            if values["completed_by"]:
                queryset = queryset.filter(completed_by__icontains=values["completed_by"])
            grouped = OrderedDict()
            for workflow in queryset.order_by("occurrence_id", "instance_number")[:1000]:
                key = (workflow.occurrence_id, workflow.instance_number)
                item = grouped.setdefault(
                    key,
                    {
                        "occurrence": workflow.occurrence,
                        "instance_number": workflow.instance_number,
                        "workflow_count": 0,
                        "completed_by": set(),
                    },
                )
                item["workflow_count"] += 1
                if workflow.completed_by:
                    item["completed_by"].add(workflow.completed_by)
            for item in grouped.values():
                item["completed_by"] = ", ".join(sorted(item["completed_by"]))
                item["delete_url"] = reverse(
                    "admin:bones_instancedeletion_delete_instance",
                    kwargs={
                        "occurrence_id": item["occurrence"].pk,
                        "instance_number": item["instance_number"],
                    },
                )
                results.append(item)
        return render(
            request,
            "admin/bones/instancedeletion/find_instance.html",
            {
                **self.admin_site.each_context(request),
                "title": "Find an instance to delete",
                "form": form,
                "results": results,
                "opts": self.model._meta,
            },
        )

    def delete_instance(self, request, occurrence_id, instance_number):
        self._require_delete_permission(request)
        summary = _instance_summary(occurrence_id, instance_number)
        form = InstanceDeletionForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            reason = form.cleaned_data["reason"]
            with transaction.atomic():
                summary = _instance_summary(occurrence_id, instance_number, lock=True)
                workflows = summary["workflows"]
                occurrence = summary["occurrence"]
                transect = occurrence.transect
                workflow_ids = [workflow.pk for workflow in workflows]
                responses = list(
                    CompletedResponse.objects.select_for_update().filter(workflow_id__in=workflow_ids)
                )
                links = list(
                    EntityImageTarget.objects.select_for_update()
                    .filter(entity_type="instance", entity_id=f"{occurrence_id}:{instance_number}")
                    .select_related("image")
                )
                exclusive = [link for link in links if link.image.targets.count() == 1]
                audit = InstanceDeletion(
                    template_name=(transect.transect_template.name if transect.transect_template else "Unknown template"),
                    transect_uid=transect.pk,
                    transect_date=transect.start_time.date() if transect.start_time else None,
                    occurrence_id=occurrence.pk,
                    occurrence_number=occurrence.occurrence_number,
                    instance_number=instance_number,
                    reason=reason,
                    deleted_by=request.user,
                    workflow_count=len(workflows),
                    response_count=len(responses),
                    image_link_count=len(links),
                    image_file_count=len(exclusive),
                    workflow_snapshot=[
                        {
                            "uid": workflow.pk,
                            "occurrence_id": workflow.occurrence_id,
                            "template_workflow_id": workflow.template_workflow_id,
                            "template_workflow": str(workflow.template_workflow),
                            "instance_number": workflow.instance_number,
                            "completed_by": workflow.completed_by,
                        }
                        for workflow in workflows
                    ],
                    response_snapshot=[
                        {
                            "id": response.pk,
                            "occurrence_id": response.occurrence_id,
                            "workflow_id": response.workflow_id,
                            "question_number": response.question_number,
                            "question_text": response.question_text,
                            "response_code": response.response_code,
                            "response": response.response,
                            "skipped": response.skipped,
                            "question_id": response.question_id,
                        }
                        for response in responses
                    ],
                    image_snapshot=[
                        {
                            "image_id": str(link.image_id),
                            "entity_type": link.entity_type,
                            "entity_id": link.entity_id,
                            "archived": link in exclusive,
                        }
                        for link in links
                    ],
                )
                audit._history_user = request.user
                audit._change_reason = "Instance deletion audit created"
                audit.save()
                for response in responses:
                    response._history_user = request.user
                    response._change_reason = reason
                    response.delete()
                for link in links:
                    image = link.image
                    is_exclusive = link in exclusive
                    link._history_user = request.user
                    link._change_reason = reason
                    link.delete()
                    if is_exclusive:
                        image.archived_by_deletion = audit
                        image._history_user = request.user
                        image._change_reason = reason
                        image.save(update_fields=["archived_by_deletion"])
                for workflow in workflows:
                    workflow._history_user = request.user
                    workflow._change_reason = reason
                    workflow.delete()
                LogEntry.objects.log_action(
                    user_id=request.user.pk,
                    content_type_id=ContentType.objects.get_for_model(InstanceDeletion).pk,
                    object_id=str(audit.pk),
                    object_repr=str(audit),
                    action_flag=CHANGE,
                    change_message=f"Deleted completed instance. Reason: {reason}",
                )
                transaction.on_commit(write_image_index)
            messages.success(request, f"Instance {instance_number} was deleted and retained in the audit log.")
            return redirect("admin:bones_instancedeletion_change", object_id=audit.pk)
        return render(
            request,
            "admin/bones/instancedeletion/delete_instance.html",
            {
                **self.admin_site.each_context(request),
                "title": "Delete completed instance",
                "form": form,
                "summary": summary,
                "opts": self.model._meta,
            },
        )
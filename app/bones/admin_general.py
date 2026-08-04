from __future__ import annotations
import hashlib, json
from pathlib import Path
from urllib.parse import urlencode
from django import forms
from django.contrib import admin, messages
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin
from .models import (CompletedOccurrence,CompletedOccurrenceInfo,CompletedResponse,CompletedTransect,CompletedTransectInfo,CompletedTransectTrack,CompletedWorkflow,DataLogFile,DataType,DataTypeOption,MNIElementRule,MNITaxonRule,MNIWeatheringRule,OccurrenceInfoImportBatch,ProjectConfig,Question,TemplateTransect,TemplateWorkflow,TransectDataLog)
from .occurrence_info_imports import template_workbook, validate_workbook

def signature(obj):
    if not obj or obj.pk is None: return ""
    data={f.attname:getattr(obj,f.attname) for f in obj._meta.concrete_fields}
    return hashlib.sha256(json.dumps(data,sort_keys=True,default=str).encode()).hexdigest()

class AuditFieldsForm(forms.ModelForm):
    edit_reason=forms.CharField(max_length=100,required=False,widget=forms.Textarea(attrs={"rows":2}),help_text="Required for edits and stored in audit history.")
    record_version=forms.CharField(required=False,widget=forms.HiddenInput)
    class Meta:
        fields="__all__"
class ResponseAuditForm(AuditFieldsForm):
    answer_option=forms.ChoiceField(
        label="Answer",
        required=False,
        help_text="Selecting one option stores its code and text together.",
    )
class OccurrenceInfoAuditForm(AuditFieldsForm):
    answer_option=forms.ChoiceField(
        label="Answer",
        required=False,
        help_text="Selecting one option stores its code and text together.",
    )
class OccurrenceInfoImportForm(forms.Form):
    workbook=forms.FileField(
        help_text="Upload the completed .xlsx template (maximum 5 MB).",
        widget=forms.ClearableFileInput(attrs={"accept":".xlsx"}),
    )
    def clean_workbook(self):
        workbook=self.cleaned_data["workbook"]
        if Path(workbook.name).suffix.lower() != ".xlsx":
            raise ValidationError("Upload an .xlsx workbook.")
        if workbook.size > 5 * 1024 * 1024:
            raise ValidationError("The workbook may not exceed 5 MB.")
        return workbook
class WorkflowDeletionForm(forms.Form):
    reason=forms.CharField(max_length=100,widget=forms.Textarea(attrs={"rows":3}),help_text="Required. Stored in workflow and response deletion history.")
    confirm=forms.BooleanField(label="I confirm that this workflow and its responses should be deleted")
class BonesHistoryAdmin(SimpleHistoryAdmin):
    form=AuditFieldsForm
    list_per_page=50; save_on_top=True
    def has_add_permission(self,request): return False
    def has_delete_permission(self,request,obj=None): return False
    def get_actions(self,request):
        actions=super().get_actions(request); actions.pop("delete_selected",None); return actions
    def validate_admin_form(self,cleaned,instance): return cleaned
    def get_form(self,request,obj=None,change=False,**kwargs):
        base=super().get_form(request,obj,change,**kwargs); owner=self
        def init(form,*args,**kw):
            base.__init__(form,*args,**kw); editing=form.instance is not None and form.instance.pk is not None
            form.fields["edit_reason"].required=editing
            if editing and not form.is_bound: form.initial["record_version"]=signature(form.instance)
        def clean(form):
            cleaned=base.clean(form)
            if form.instance is not None and form.instance.pk is not None:
                posted=cleaned.get("record_version")
                if posted and posted != signature(form.instance): raise ValidationError("This record changed after the form was opened. Reload and review it.")
            return owner.validate_admin_form(cleaned,form.instance)
        return type("Audited"+base.__name__,(base,),{"edit_reason":forms.CharField(max_length=100,required=False,widget=forms.Textarea(attrs={"rows":2}),help_text="Required for edits and stored in audit history."),"record_version":forms.CharField(required=False,widget=forms.HiddenInput),"__init__":init,"clean":clean})
    def save_model(self,request,obj,form,change):
        obj._history_user=request.user; obj._change_reason=form.cleaned_data.get("edit_reason") or "Created in Django admin"; super().save_model(request,obj,form,change)
    @admin.display(description="History")
    def history_link(self,obj): return format_html('<a href="{}">History</a>',reverse(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_history",args=(obj.pk,)))

class ReadOnlyAdmin(SimpleHistoryAdmin):
    list_per_page=50
    def has_add_permission(self,r): return False
    def has_change_permission(self,r,obj=None): return False
    def has_delete_permission(self,r,obj=None): return False
    def has_view_permission(self,r,obj=None): return r.user.has_perm(f"{self.model._meta.app_label}.view_{self.model._meta.model_name}")
    def get_actions(self,r): return {}

@admin.register(CompletedResponse)
class ResponseAdmin(BonesHistoryAdmin):
    form=ResponseAuditForm
    list_display=("id","transect_uid","occurrence_label","instance","workflow_label","question_number","question_label","response_code","response","skipped","history_link")
    list_select_related=("occurrence__transect__transect_template","workflow__template_workflow","question__data_type")
    search_fields=("=id","=occurrence__transect__uid","occurrence__transect__transect_template__name__icontains","=occurrence__id","=occurrence__occurrence_number","=workflow__instance_number","workflow__uid__icontains","workflow__template_workflow__name__icontains","question__id__icontains","=question_number","question_text__icontains","response_code__icontains","response__icontains","workflow__completed_by__icontains")
    list_filter=("skipped","workflow__instance_number","workflow__template_workflow")
    readonly_fields=("id","occurrence","workflow","question","question_number","question_text","hierarchy","options")
    fields=("hierarchy","id","occurrence","workflow","question","question_number","question_text","options","answer_option","response_code","response","skipped","edit_reason","record_version")
    @admin.display(description="Transect",ordering="occurrence__transect__uid")
    def transect_uid(self,o): return o.occurrence.transect_id
    @admin.display(description="Occurrence",ordering="occurrence__occurrence_number")
    def occurrence_label(self,o): return f"{o.occurrence.occurrence_number} (ID {o.occurrence_id})"
    @admin.display(description="Instance",ordering="workflow__instance_number")
    def instance(self,o): return o.workflow.instance_number
    @admin.display(description="Workflow",ordering="workflow__template_workflow__name")
    def workflow_label(self,o): return o.workflow.template_workflow.name
    @admin.display(description="Question")
    def question_label(self,o): return o.question_text if len(o.question_text or "")<81 else o.question_text[:77]+"..."
    @admin.display(description="Hierarchy")
    def hierarchy(self,o):
        if not o:return ""
        t=o.occurrence.transect; return f"Template {t.transect_template}; transect {t.pk}; occurrence {o.occurrence.occurrence_number} (ID {o.occurrence_id}); instance {o.workflow.instance_number}; workflow {o.workflow.template_workflow}"
    @admin.display(description="Configured answer options")
    def options(self,o):
        if not o:return ""
        rows=DataTypeOption.objects.filter(data_type_id=o.question.data_type_id)[:100]
        return "; ".join(f"{x.code}: {x.text}" for x in rows) or "Free-form answer"
    def get_form(self,request,obj=None,change=False,**kwargs):
        base=super().get_form(request,obj,change,**kwargs)
        class OptionAnswerForm(base):
            def __init__(self,*args,**form_kwargs):
                super().__init__(*args,**form_kwargs)
                instance=self.instance; options=[]
                if instance and instance.question_id:
                    options=list(DataTypeOption.objects.filter(data_type_id=instance.question.data_type_id).order_by("code"))
                self._answer_options={str(option.code):option for option in options}
                if options:
                    choices=[("","---------")]+[(str(x.code),f"{x.code} — {x.text}") for x in options]
                    self.fields["answer_option"].choices=choices; self.fields["answer_option"].widget=forms.Select(choices=choices)
                    self.initial["answer_option"]=str(instance.response_code or "")
                    self.fields["response_code"].widget=forms.HiddenInput(); self.fields["response"].widget=forms.HiddenInput()
                else:
                    self.fields["answer_option"].widget=forms.HiddenInput()
                    self.fields["answer_option"].help_text="No configured options; edit the response fields below."
            def clean(self):
                cleaned=super().clean()
                if self._answer_options:
                    selected=cleaned.get("answer_option"); skipped=cleaned.get("skipped",False)
                    if not selected and not skipped: self.add_error("answer_option","Select an answer or mark the response as skipped.")
                    elif selected:
                        option=self._answer_options.get(str(selected))
                        if option is None: self.add_error("answer_option","Select a configured answer.")
                        else: cleaned["response_code"]=option.code; cleaned["response"]=option.text or ""
                    else: cleaned["response_code"]=""; cleaned["response"]=""
                return cleaned
        return OptionAnswerForm
@admin.register(CompletedWorkflow)
class WorkflowAdmin(BonesHistoryAdmin):
    change_form_template="admin/bones/completedworkflow/change_form.html"
    list_display=("uid","transect_uid","occurrence_label","instance_number","template_workflow","completed_by","answers","instance_page","history_link")
    list_select_related=("occurrence__transect__transect_template","template_workflow")
    search_fields=("uid__icontains","=occurrence__transect__uid","occurrence__transect__transect_template__name__icontains","=occurrence__id","=occurrence__occurrence_number","=instance_number","template_workflow__name__icontains","completed_by__icontains")
    list_filter=("template_workflow","instance_number")
    readonly_fields=("uid","occurrence","template_workflow","instance_number","answers","instance_page")
    fields=("uid","occurrence","instance_number","template_workflow","completed_by","answers","instance_page","edit_reason","record_version")
    @admin.display(description="Transect",ordering="occurrence__transect__uid")
    def transect_uid(self,o): return o.occurrence.transect_id
    @admin.display(description="Occurrence",ordering="occurrence__occurrence_number")
    def occurrence_label(self,o): return f"{o.occurrence.occurrence_number} (ID {o.occurrence_id})"
    @admin.display(description="Answers")
    def answers(self,o): return format_html('<a href="{}?{}">View answers</a>',reverse("admin:bones_completedresponse_changelist"),urlencode({"workflow__uid__exact":o.pk}))
    @admin.display(description="Instance page")
    def instance_page(self,o): return format_html('<a href="{}">Open instance</a>',reverse("bones:occurrences:instance_detail",kwargs={"occurrence_pk":o.occurrence_id,"instance_number":o.instance_number}))
    def get_urls(self):
        custom=[path("<path:object_id>/remove/",self.admin_site.admin_view(self.remove_workflow),name="bones_completedworkflow_remove")]
        return custom+super().get_urls()
    def change_view(self,request,object_id,form_url="",extra_context=None):
        remove_url=None
        if request.user.has_perm("bones.delete_completedworkflow"):
            remove_url=reverse("admin:bones_completedworkflow_remove",args=(object_id,))
        return super().change_view(request,object_id,form_url,{**(extra_context or {}),"remove_workflow_url":remove_url})
    def remove_workflow(self,request,object_id):
        if not request.user.has_perm("bones.delete_completedworkflow"):
            raise PermissionDenied
        workflow=get_object_or_404(
            CompletedWorkflow.objects.select_related("occurrence__transect__transect_template","template_workflow"),
            pk=object_id,
        )
        siblings=CompletedWorkflow.objects.filter(
            occurrence_id=workflow.occurrence_id,
            instance_number=workflow.instance_number,
        ).exclude(pk=workflow.pk)
        conflict=not siblings.exists()
        responses=CompletedResponse.objects.filter(workflow_id=workflow.pk)
        form=WorkflowDeletionForm(request.POST or None)
        if request.method=="POST" and form.is_valid() and not conflict:
            reason=form.cleaned_data["reason"]
            with transaction.atomic():
                workflow=CompletedWorkflow.objects.select_for_update().get(pk=object_id)
                if not CompletedWorkflow.objects.select_for_update().filter(
                    occurrence_id=workflow.occurrence_id,
                    instance_number=workflow.instance_number,
                ).exclude(pk=workflow.pk).exists():
                    form.add_error(None,"This is now the last workflow. Use the complete-instance deletion procedure.")
                else:
                    occurrence_id=workflow.occurrence_id; instance_number=workflow.instance_number
                    response_rows=list(CompletedResponse.objects.select_for_update().filter(workflow_id=workflow.pk))
                    workflow_label=str(workflow)
                    for response in response_rows:
                        response._history_user=request.user; response._change_reason=reason; response.delete()
                    workflow._history_user=request.user; workflow._change_reason=reason; workflow.delete()
                    LogEntry.objects.log_action(
                        user_id=request.user.pk,
                        content_type_id=ContentType.objects.get_for_model(CompletedWorkflow).pk,
                        object_id=str(object_id),object_repr=workflow_label,action_flag=CHANGE,
                        change_message=f"Removed workflow from instance. Reason: {reason}",
                    )
                    messages.success(request,"The workflow and its responses were removed; sibling workflows and instance images were retained.")
                    return redirect(f'{reverse("admin:bones_completedworkflow_changelist")}?occurrence__id__exact={occurrence_id}&instance_number={instance_number}')
        return render(request,"admin/bones/completedworkflow/remove_workflow.html",{
            **self.admin_site.each_context(request),"title":"Remove workflow from instance","opts":self.model._meta,
            "workflow":workflow,"response_count":responses.count(),"conflict":conflict,"form":form,
        })

@admin.register(CompletedOccurrence)
class OccurrenceAdmin(BonesHistoryAdmin):
    change_form_template="admin/bones/completedoccurrence/change_form.html"
    list_display=("id","transect","occurrence_number","recording_start_time","state","instances","answers","history_link")
    list_select_related=("transect__transect_template",)
    search_fields=("=id","=occurrence_number","=transect__uid","transect__name__icontains","transect__transect_template__name__icontains","note__icontains","state__icontains")
    list_filter=("state","transect__transect_template")
    readonly_fields=("id","transect","occurrence_number","instances","answers")
    fields=("id","transect","occurrence_number","recording_start_time","recording_end_time","lat","long","note","state","instances","answers","edit_reason","record_version")
    @admin.display(description="Instances")
    def instances(self,o): return format_html('<a href="{}?{}">View instances</a>',reverse("admin:bones_completedworkflow_changelist"),urlencode({"occurrence__id__exact":o.pk}))
    @admin.display(description="Answers")
    def answers(self,o): return format_html('<a href="{}?{}">View answers</a>',reverse("admin:bones_completedresponse_changelist"),urlencode({"occurrence__id__exact":o.pk}))
    def change_view(self,request,object_id,form_url="",extra_context=None):
        deletion_url=None
        if request.user.has_perm("bones.delete_completed_occurrence"):
            deletion_url=reverse("admin:bones_occurrencedeletion_delete_occurrence",kwargs={"occurrence_id":object_id})
        return super().change_view(request,object_id,form_url,{**(extra_context or {}),"delete_occurrence_url":deletion_url})

@admin.register(CompletedTransect)
class TransectAdmin(BonesHistoryAdmin):
    list_display=("uid","name","transect_template","start_time","end_time","state","occurrences","answers","history_link")
    list_select_related=("transect_template",)
    search_fields=("=uid","name__icontains","transect_template__name__icontains","state__icontains")
    list_filter=("state","transect_template","start_time")
    readonly_fields=("uid","transect_template","occurrences","answers")
    fields=("uid","transect_template","name","start_time","turn_time","end_time","lat_from","long_from","lat_turn","long_turn","lat_to","long_to","distance_km","angle_degrees","state","paused_for_minutes","occurrences","answers","edit_reason","record_version")
    @admin.display(description="Occurrences")
    def occurrences(self,o): return format_html('<a href="{}?{}">View occurrences</a>',reverse("admin:bones_completedoccurrence_changelist"),urlencode({"transect__uid__exact":o.pk}))
    @admin.display(description="Answers")
    def answers(self,o): return format_html('<a href="{}?{}">View answers</a>',reverse("admin:bones_completedresponse_changelist"),urlencode({"occurrence__transect__uid__exact":o.pk}))

@admin.register(TemplateTransect)
class TemplateTransectAdmin(BonesHistoryAdmin):
    list_display=("name","scheduled_time","open_ended","created_dynamically","history_link"); search_fields=("id__icontains","name__icontains","note__icontains"); list_filter=("open_ended","created_dynamically"); readonly_fields=("id",)
@admin.register(TemplateWorkflow)
class TemplateWorkflowAdmin(BonesHistoryAdmin):
    list_display=("name","date_added","added_by","history_link"); search_fields=("id__icontains","name__icontains","added_by__icontains"); readonly_fields=("id",)
@admin.register(Question)
class QuestionAdmin(BonesHistoryAdmin):
    list_display=("id","prompt","data_type","workflow","history_link"); list_select_related=("data_type","workflow"); search_fields=("id__icontains","prompt__icontains","data_type__name__icontains","workflow__name__icontains"); list_filter=("data_type","workflow"); readonly_fields=("id","data_type","data_type_name","workflow")
@admin.register(DataType)
class DataTypeAdmin(BonesHistoryAdmin):
    list_display=("id","name","is_user_data_type","csharp_type","history_link"); search_fields=("id__icontains","name__icontains","csharp_type__icontains"); list_filter=("is_user_data_type",); readonly_fields=("id",)
@admin.register(ProjectConfig)
class ProjectConfigAdmin(BonesHistoryAdmin):
    list_display=("id","project","publish_date","config_folder","history_link"); search_fields=("=id","project__icontains","config_folder__icontains"); readonly_fields=("id",)

@admin.register(DataLogFile)
class DataLogAdmin(ReadOnlyAdmin): list_display=("id","upload_date","uploaded_by"); search_fields=("=id","uploaded_by__icontains","contents__icontains")
@admin.register(DataTypeOption)
class OptionAdmin(ReadOnlyAdmin): list_display=("data_type","code","text"); list_select_related=("data_type",); search_fields=("data_type__name__icontains","code__icontains","text__icontains")
@admin.register(CompletedTransectInfo)
class TransectInfoAdmin(ReadOnlyAdmin): list_display=("transect","pre_or_post","question_text","response_code","response"); search_fields=("=transect__uid","question_text__icontains","response_code__icontains","response__icontains")
@admin.register(CompletedTransectTrack)
class TrackAdmin(ReadOnlyAdmin): list_display=("id","transect","time","user","is_start","is_turn_point","is_end"); search_fields=("=id","=transect__uid","user__icontains"); list_filter=("is_start","is_checkpoint","is_occurrence","is_turn_point","is_end")
@admin.register(CompletedOccurrenceInfo)
class OccurrenceInfoAdmin(BonesHistoryAdmin):
    form=OccurrenceInfoAuditForm
    change_list_template="admin/bones/completedoccurrenceinfo/change_list.html"
    list_display=("occurrence","pre_or_post","question_text","response_code","response","history_link")
    list_select_related=("occurrence__transect",)
    search_fields=("=occurrence__id","=occurrence__transect__uid","question_text__icontains","response_code__icontains","response__icontains")
    list_filter=("pre_or_post",)
    readonly_fields=("id","occurrence","pre_or_post","question_text","response_data_type","options")
    fields=("id","occurrence","pre_or_post","question_text","response_data_type","options","answer_option","response_code","response","edit_reason","record_version")
    def get_urls(self):
        custom=[
            path("bulk-update/template/",self.admin_site.admin_view(self.import_template),name="bones_completedoccurrenceinfo_import_template"),
            path("bulk-update/",self.admin_site.admin_view(self.bulk_update),name="bones_completedoccurrenceinfo_bulk_update"),
            path("bulk-update/<uuid:batch_id>/",self.admin_site.admin_view(self.bulk_preview),name="bones_completedoccurrenceinfo_bulk_preview"),
        ]
        return custom+super().get_urls()
    def _import_allowed(self,request):
        return request.user.has_perm("bones.run_occurrence_info_import") and request.user.has_perm("bones.change_completedoccurrenceinfo")
    def changelist_view(self,request,extra_context=None):
        extra_context={**(extra_context or {}),"occurrence_info_import_allowed":self._import_allowed(request)}
        return super().changelist_view(request,extra_context)
    def import_template(self,request):
        if not self._import_allowed(request): return HttpResponseForbidden()
        response=HttpResponse(
            template_workbook(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"]='attachment; filename="occurrence_info_updates.xlsx"'
        return response
    def bulk_update(self,request):
        if not self._import_allowed(request): return HttpResponseForbidden()
        form=OccurrenceInfoImportForm(request.POST or None,request.FILES or None)
        if request.method=="POST" and form.is_valid():
            upload=form.cleaned_data["workbook"]
            content=upload.read()
            try:
                items=validate_workbook(content)
            except ValueError as exc:
                form.add_error("workbook",str(exc))
            else:
                batch=OccurrenceInfoImportBatch.objects.create(
                    original_filename=Path(upload.name).name,
                    file_checksum=hashlib.sha256(content).hexdigest(),
                    created_by=request.user,
                    summary={"items":items},
                )
                return redirect("admin:bones_completedoccurrenceinfo_bulk_preview",batch_id=batch.pk)
        return render(request,"admin/bones/completedoccurrenceinfo/bulk_update.html",{
            **self.admin_site.each_context(request),"form":form,"title":"Bulk update occurrence answers",
            "template_url":reverse("admin:bones_completedoccurrenceinfo_import_template"),
        })
    def bulk_preview(self,request,batch_id):
        if not self._import_allowed(request): return HttpResponseForbidden()
        batch=get_object_or_404(OccurrenceInfoImportBatch,pk=batch_id)
        items=batch.summary.get("items",[])
        counts={status:sum(item.get("status")==status for item in items) for status in ("ready","unchanged","duplicate","error")}
        can_apply=batch.status=="preview" and counts["ready"]>0 and counts["error"]==0
        if request.method=="POST":
            if not can_apply:
                messages.error(request,"This import cannot be applied because it has errors, no changes, or was already completed.")
            else:
                updated=unchanged=0
                with transaction.atomic():
                    for item in items:
                        if item["status"] != "ready": continue
                        target=CompletedOccurrenceInfo.objects.select_for_update().get(pk=item["target_id"])
                        new_code=item["new_response_code"]
                        new_response=item["canonical_new_response"]
                        if (target.response_code or "")==new_code and (target.response or "").strip().casefold()==new_response.strip().casefold():
                            unchanged+=1; continue
                        target.response_code=new_code
                        target.response=new_response
                        target._history_user=request.user
                        target._change_reason=item["update_comment"]
                        target.save(update_fields=["response_code","response"])
                        updated+=1
                    batch.status="completed"
                    batch.completed_at=timezone.now()
                    batch.summary={**batch.summary,"updated":updated,"unchanged_at_apply":unchanged}
                    batch.save(update_fields=["status","completed_at","summary"])
                messages.success(request,f"Updated {updated} occurrence answers; skipped {counts['unchanged']+counts['duplicate']+unchanged} unchanged or duplicate rows.")
                return redirect("admin:bones_completedoccurrenceinfo_changelist")
        return render(request,"admin/bones/completedoccurrenceinfo/bulk_preview.html",{
            **self.admin_site.each_context(request),"batch":batch,"items":items,"counts":counts,
            "can_apply":can_apply,"title":"Review occurrence answer updates",
        })
    @admin.display(description="Configured answer options")
    def options(self,o):
        if not o or not o.response_data_type:return ""
        rows=DataTypeOption.objects.filter(data_type_id=o.response_data_type)[:100]
        return "; ".join(f"{x.code}: {x.text}" for x in rows) or "Free-form answer"
    def get_form(self,request,obj=None,change=False,**kwargs):
        base=super().get_form(request,obj,change,**kwargs)
        class OptionAnswerForm(base):
            def __init__(self,*args,**form_kwargs):
                super().__init__(*args,**form_kwargs)
                instance=self.instance; options=[]
                if instance and instance.response_data_type:
                    options=list(DataTypeOption.objects.filter(data_type_id=instance.response_data_type).order_by("code"))
                self._answer_options={str(option.code):option for option in options}
                if options:
                    choices=[("","---------")]+[(str(x.code),f"{x.code} — {x.text}") for x in options]
                    self.fields["answer_option"].choices=choices; self.fields["answer_option"].widget=forms.Select(choices=choices)
                    self.initial["answer_option"]=str(instance.response_code or "")
                    self.fields["response_code"].widget=forms.HiddenInput(); self.fields["response"].widget=forms.HiddenInput()
                else:
                    self.fields["answer_option"].widget=forms.HiddenInput()
                    self.fields["answer_option"].help_text="No configured options; edit the response fields below."
            def clean(self):
                cleaned=super().clean()
                if self._answer_options:
                    selected=cleaned.get("answer_option")
                    if not selected: self.add_error("answer_option","Select an answer.")
                    else:
                        option=self._answer_options.get(str(selected))
                        if option is None: self.add_error("answer_option","Select a configured answer.")
                        else: cleaned["response_code"]=option.code; cleaned["response"]=option.text or ""
                return cleaned
        return OptionAnswerForm
@admin.register(OccurrenceInfoImportBatch)
class OccurrenceInfoImportBatchAdmin(admin.ModelAdmin):
    list_display=("id","original_filename","status","created_by","created_at","completed_at")
    readonly_fields=("id","original_filename","file_checksum","status","summary","created_by","created_at","completed_at")
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False
@admin.register(TransectDataLog)
class TransectLogAdmin(ReadOnlyAdmin): list_display=("id","transect","data_log_file","is_primary","username"); search_fields=("=id","=transect__uid","=data_log_file__id","username__icontains")

@admin.register(MNIElementRule)
class MNIElementRuleAdmin(admin.ModelAdmin):
    list_display=("canonical_name","divisor","paired","excluded","active","reviewed")
    list_filter=("paired","excluded","active","reviewed")
    search_fields=("canonical_name","display_name","notes")

@admin.register(MNITaxonRule)
class MNITaxonRuleAdmin(admin.ModelAdmin):
    list_display=("source_alias","canonical_label","default_excluded","active")
    list_filter=("default_excluded","active")
    search_fields=("source_alias","canonical_label","notes")

@admin.register(MNIWeatheringRule)
class MNIWeatheringRuleAdmin(admin.ModelAdmin):
    list_display=("source_class","canonical_class","age_min","age_max","age_min_corrected","age_max_corrected","active","reviewed")
    list_filter=("active","reviewed")
    search_fields=("source_class","canonical_class","notes")

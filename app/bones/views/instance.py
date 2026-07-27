from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from .detail import safe_reverse
from .mixins import BonesAuthMixin
from ..image_views import image_context, instance_key
from ..models import CompletedOccurrence, CompletedWorkflow


class CompletedInstanceDetailView(BonesAuthMixin, TemplateView):
    template_name = "bones/completed_instance_detail.html"
    permission_required = "bones.view_completedworkflow"

    def dispatch(self, request, *args, **kwargs):
        self.occurrence = get_object_or_404(CompletedOccurrence, pk=kwargs["occurrence_pk"])
        self.workflows = list(CompletedWorkflow.objects.filter(occurrence=self.occurrence, instance_number=kwargs["instance_number"]).select_related("template_workflow"))
        if not self.workflows:
            from django.http import Http404
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        number = self.kwargs["instance_number"]
        context.update({
            "page_title": _("Instance {number}").format(number=number),
            "page_icon": "fa-solid fa-layer-group",
            "intro_text": _("Review the workflows and images associated with this occurrence instance."),
            "breadcrumbs": [
                {"label": _("Completed occurrences"), "url": safe_reverse("bones:occurrences:list")},
                {"label": str(self.occurrence), "url": safe_reverse("bones:occurrences:detail", kwargs={"pk": self.occurrence.pk})},
                {"label": _("Instance {number}").format(number=number), "url": None},
            ],
            "tabs": [
                {"id": "overview", "label": _("Overview"), "icon": "fa-solid fa-circle-info", "active": True, "template": "bones/completed_instances/_overview.html"},
                {"id": "images", "label": _("Images"), "icon": "fa-solid fa-images", "active": False, "template": "bones/images/_tab.html"},
            ],
            "tablist_label": _("Instance detail navigation"),
            "instance_workflows": self.workflows,
            "list_url": safe_reverse("bones:occurrences:detail", kwargs={"pk": self.occurrence.pk}),
            "history_url": None, "extra_actions": [],
        })
        context.update(image_context("instance", instance_key(self.occurrence.pk, number), self.request.user))
        return context
"""Master-detail view archetypes for completed records."""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from django.db import DatabaseError
from django.db.models import Count, Prefetch, Q
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView

from .detail import (
    format_boolean,
    format_datetime,
    format_pre,
    format_value,
    safe_reverse,
)
from ..image_views import image_context, instance_key
from ..maps import map_context
from ..models import CompletedOccurrence, CompletedTransect, EntityImage
from ..reports.mni_detail import build_mni_detail, empty_mni_detail
from .mixins import BonesAuthMixin


class BonesMasterDetailView(BonesAuthMixin, DetailView):
    """Base class for master-detail style pages with tab navigation."""

    page_icon: str = ""
    page_title_template: str = "{object}"
    intro_text: str = ""
    list_route_name: str | None = None
    history_route_name: str | None = None
    breadcrumb_list_label: str = ""
    tablist_label: str = ""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.history_error: bool = False

    def get_page_title(self) -> str:
        return self.page_title_template.format(object=self.object)

    def get_intro_text(self) -> str:
        return self.intro_text

    def get_list_url(self) -> str | None:
        return safe_reverse(self.list_route_name)

    def get_history_kwargs(self) -> Mapping[str, Any] | None:
        if not self.object:
            return None
        return {"pk": getattr(self.object, "pk", None)}

    def get_history_url(self) -> str | None:
        return safe_reverse(self.history_route_name, kwargs=self.get_history_kwargs())

    def get_extra_actions(self) -> Iterable[Mapping[str, Any]]:
        return []

    def get_tabs(self) -> Iterable[Mapping[str, Any]]:
        """Return metadata describing the tabs to render."""

        return []

    def get_tablist_label(self) -> str:
        return self.tablist_label or _("Record sections")

    def get_breadcrumbs(self) -> list[dict[str, str | None]]:
        breadcrumbs: list[dict[str, str | None]] = [
            {"label": _("Dashboard"), "url": safe_reverse("dashboard")},
        ]
        list_url = self.get_list_url()
        if self.breadcrumb_list_label:
            breadcrumbs.append({"label": self.breadcrumb_list_label, "url": list_url})
        elif list_url:
            breadcrumbs.append({"label": list_url, "url": list_url})
        breadcrumbs.append({"label": self.get_page_title(), "url": None})
        return breadcrumbs

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": self.get_page_title(),
                "page_icon": self.page_icon,
                "intro_text": self.get_intro_text(),
                "list_url": self.get_list_url(),
                "history_url": self.get_history_url(),
                "extra_actions": list(self.get_extra_actions()),
                "tabs": list(self.get_tabs()),
                "tablist_label": self.get_tablist_label(),
                "breadcrumbs": self.get_breadcrumbs(),
            }
        )
        return context

    @staticmethod
    def _as_list(manager: Any) -> list[Any]:
        if hasattr(manager, "all"):
            return list(manager.all())
        if manager is None:
            return []
        return list(manager)

    def get_permission_required(self):  # type: ignore[override]
        perms = super().get_permission_required()
        if perms:
            return perms
        if getattr(self, "model", None):
            meta = self.model._meta  # type: ignore[attr-defined]
            return (f"{meta.app_label}.view_{meta.model_name}",)
        return ()


class CompletedTransectDetailView(BonesMasterDetailView):
    """Present a completed transect alongside its related data."""

    model = CompletedTransect
    template_name = "bones/completed_transect_detail.html"
    page_icon = "fa-solid fa-route"
    page_title_template = _("Transect {object}")
    intro_text = _(
        "Inspect a completed transect, review its captured occurrences, track points, and audit history."
    )
    list_route_name = "bones:transects:list"
    history_route_name = "bones:history:transect_record"
    breadcrumb_list_label = _("Completed transects")
    tablist_label = _("Transect detail navigation")

    def get_queryset(self):
        # Load occurrence summaries rather than every nested response/workflow.
        occurrence_summaries = (
            CompletedOccurrence.objects.with_details()
            .annotate(
                response_count=Count("responses", distinct=True),
                workflow_count=Count("workflows", distinct=True),
            )
            .order_by("occurrence_number", "pk")
        )
        return (
            CompletedTransect.objects.select_related("transect_template")
            .annotate(track_point_count=Count("track_points", distinct=True))
            .prefetch_related(
                Prefetch("occurrences", queryset=occurrence_summaries),
                "details",
            )
        )

    def get_extra_actions(self) -> Iterable[Mapping[str, Any]]:
        obj = self.object
        if not obj:
            return []
        return [
            {
                "label": _("Export responses"),
                "icon": "fa-solid fa-file-export",
                "url": safe_reverse("bones:transects:export_responses", kwargs={"pk": obj.pk}),
            },
            {
                "label": _("Download GPS track"),
                "icon": "fa-solid fa-download",
                "url": safe_reverse("bones:transects:download_track", kwargs={"pk": obj.pk}),
            },
        ]

    def get_overview_sections(self) -> list[dict[str, Any]]:
        transect = self.object
        return [
            {
                "title": _("Summary"),
                "icon": "fa-solid fa-circle-info",
                "items": [
                    {"label": _("Identifier"), "value": format_value(transect.pk)},
                    {
                        "label": _("Template"),
                        "value": format_value(getattr(transect.transect_template, "name", transect.transect_template)),
                    },
                    {"label": _("State"), "value": format_value(transect.state)},
                    {"label": _("Started"), "value": format_datetime(transect.start_time)},
                    {"label": _("Ended"), "value": format_datetime(transect.end_time)},
                    {"label": _("Turn time"), "value": format_datetime(transect.turn_time)},
                    {
                        "label": _("Distance (km)"),
                        "value": format_value(transect.distance_km),
                    },
                ],
            },
            {
                "title": _("Coordinates"),
                "icon": "fa-solid fa-location-dot",
                "items": [
                    {
                        "label": _("Start"),
                        "value": self._format_coordinates(transect.lat_from, transect.long_from),
                    },
                    {
                        "label": _("Turn"),
                        "value": self._format_coordinates(transect.lat_turn, transect.long_turn),
                    },
                    {
                        "label": _("End"),
                        "value": self._format_coordinates(transect.lat_to, transect.long_to),
                    },
                ],
            },
        ]

    @staticmethod
    def _format_coordinates(lat: Any, long: Any) -> str:
        if lat in (None, "") or long in (None, ""):
            return format_value(None)
        return format_value(_("Lat {lat}, Long {long}").format(lat=lat, long=long))

    def get_info_table(self) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]]]:
        headers = [
            {"label": _("Phase")},
            {"label": _("Question")},
            {"label": _("Response")},
        ]
        rows: list[list[dict[str, Any]]] = []
        details = getattr(self.object, "details", None)
        info_entries = details.all() if hasattr(details, "all") else []
        for info in info_entries:
            rows.append(
                [
                    {"value": format_value(info.pre_or_post)},
                    {"value": format_value(info.question_text)},
                    {"value": format_value(info.response)},
                ]
            )
        return headers, rows

    def get_occurrence_table(self) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]]]:
        headers = [
            {"label": _("Occurrence")},
            {"label": _("Taxon")},
            {"label": _("Taxon Guess")},
            {"label": _("State")},
            {"label": _("Started")},
            {"label": _("Ended")},
            {"label": _("Responses"), "classes": "w3-center"},
            {"label": _("Workflows"), "classes": "w3-center"},
        ]
        rows: list[list[dict[str, Any]]] = []
        occurrences = getattr(self.object, "occurrences", None)
        occurrence_entries = occurrences.all() if hasattr(occurrences, "all") else []
        for occurrence in occurrence_entries:
            detail_entries = self._as_list(getattr(occurrence, "details", None))
            rows.append(
                [
                    {
                        "value": _( "Occurrence {number}").format(number=occurrence.occurrence_number),
                        "url": safe_reverse("occurrences:detail", kwargs={"pk": occurrence.pk}),
                    },
                    {
                        "value": format_value(
                            self._occurrence_detail_response(
                                detail_entries, "Pre", "Taxon"
                            )
                        )
                    },
                    {
                        "value": format_value(
                            self._occurrence_detail_response(
                                detail_entries, "Post", "Taxon Guess?"
                            )
                        )
                    },
                    {"value": format_value(occurrence.state)},
                    {"value": format_datetime(occurrence.recording_start_time)},
                    {"value": format_datetime(occurrence.recording_end_time)},
                    {
                        "value": self._related_count(occurrence, "response_count", "responses"),
                        "classes": "w3-center",
                    },
                    {
                        "value": self._related_count(occurrence, "workflow_count", "workflows"),
                        "classes": "w3-center",
                    },
                ]
            )
        return headers, rows

    @classmethod
    def _related_count(cls, occurrence: Any, annotation: str, relation: str) -> int:
        value = getattr(occurrence, annotation, None)
        if value is not None:
            return int(value)
        return len(cls._as_list(getattr(occurrence, relation, None)))

    @staticmethod
    def _occurrence_detail_response(
        details: Iterable[Any], phase: str, question: str
    ) -> Any:
        for detail in details:
            if (
                getattr(detail, "pre_or_post", "").casefold() == phase.casefold()
                and getattr(detail, "question_text", "").casefold()
                == question.casefold()
            ):
                return getattr(detail, "response", None)
        return None

    def get_track_point_table(self) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]]]:
        headers = [
            {"label": _("Timestamp")},
            {"label": _("Latitude")},
            {"label": _("Longitude")},
            {"label": _("Start")},
            {"label": _("Checkpoint")},
            {"label": _("Occurrence")},
            {"label": _("Turn point")},
            {"label": _("End")},
        ]
        rows: list[list[dict[str, Any]]] = []
        points = getattr(self.object, "track_points", None)
        track_entries = points.all() if hasattr(points, "all") else []
        for point in track_entries:
            rows.append(
                [
                    {"value": format_datetime(point.time)},
                    {"value": format_value(point.lat)},
                    {"value": format_value(point.long)},
                    {"value": format_boolean(point.is_start)},
                    {"value": format_boolean(point.is_checkpoint)},
                    {"value": format_boolean(point.is_occurrence)},
                    {"value": format_boolean(point.is_turn_point)},
                    {"value": format_boolean(point.is_end)},
                ]
            )
        return headers, rows

    def get_history_entries(self) -> list[Any]:
        try:
            return list(self.object.history.all().order_by("-history_date")[:25])
        except DatabaseError:
            self.history_error = True
            return []

    def get_tabs(self) -> Iterable[Mapping[str, Any]]:
        return [
            {
                "id": "overview",
                "label": _("Overview"),
                "icon": "fa-solid fa-circle-info",
                "active": True,
                "template": "bones/completed_transects/_overview.html",
            },
            {
                "id": "map",
                "label": _("Map"),
                "icon": "fa-solid fa-map-location-dot",
                "active": False,
                "template": "bones/maps/_tab.html",
            },
            {
                "id": "related",
                "label": _("Occurrences"),
                "icon": "fa-solid fa-layer-group",
                "active": False,
                "template": "bones/completed_transects/_related.html",
            },
            {
                "id": "mni", "label": _("MNI"),
                "icon": "fa-solid fa-calculator", "active": False,
                "template": "bones/completed_transects/_mni.html",
            },
            {
                "id": "history",
                "label": _("History"),
                "icon": "fa-solid fa-clock-rotate-left",
                "active": False,
                "template": "bones/completed_transects/_history.html",
            },
            {
                "id": "images", "label": _("Images"), "icon": "fa-solid fa-images",
                "active": False, "template": "bones/images/_tab.html",
            },
        ]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        info_headers, info_rows = self.get_info_table()
        occurrence_headers, occurrence_rows = self.get_occurrence_table()
        history_entries = self.get_history_entries()
        context.update(
            {
                "overview_sections": self.get_overview_sections(),
                "transect_info_headers": info_headers,
                "transect_info_rows": info_rows,
                "transect_occurrence_headers": occurrence_headers,
                "transect_occurrence_rows": occurrence_rows,
                "transect_track_point_count": getattr(self.object, "track_point_count", None),
                "transect_history_entries": history_entries,
                "transect_history_error": self.history_error,
            }
        )
        try:
            context["mni_detail"] = build_mni_detail(self.object.pk)
        except DatabaseError:
            context["mni_detail"] = empty_mni_detail(
                _("MNI is temporarily unavailable.")
            )
        context.update(image_context("transect", self.object.pk, self.request.user))
        context.update(
            map_context(
                safe_reverse(
                    "bones:transects:map_data", kwargs={"pk": self.object.pk}
                ),
                title=_("Transect map"),
            )
        )
        return context


class CompletedOccurrenceDetailView(BonesMasterDetailView):
    """Present a completed occurrence with nested responses and workflows."""

    model = CompletedOccurrence
    template_name = "bones/completed_occurrence_detail.html"
    page_icon = "fa-solid fa-frog"
    page_title_template = _("Occurrence {object}")
    intro_text = _(
        "Review a recorded occurrence, browse captured responses, linked workflows, and audit events."
    )
    list_route_name = "bones:occurrences:list"
    history_route_name = "bones:history:occurrence_record"
    breadcrumb_list_label = _("Completed occurrences")
    tablist_label = _("Occurrence detail navigation")
    default_response_questions = (
        "What element is this?",
        "Complete?",
        "Side",
        "Weathering class",
    )

    def get_queryset(self):
        return (
            CompletedOccurrence.objects.select_related(
                "transect",
                "transect__transect_template",
            )
            .with_related_data()
        )

    def get_extra_actions(self) -> Iterable[Mapping[str, Any]]:
        obj = self.object
        if not obj:
            return []
        return [
            {
                "label": _("Export responses"),
                "icon": "fa-solid fa-file-export",
                "url": safe_reverse("occurrences:export_responses", kwargs={"pk": obj.pk}),
            },
            {
                "label": _("View parent transect"),
                "icon": "fa-solid fa-route",
                "url": safe_reverse(
                    "transects:detail",
                    kwargs={"pk": getattr(obj.transect, "pk", None)}
                    if getattr(obj.transect, "pk", None) is not None
                    else None,
                ),
            },
        ]

    def get_overview_sections(self) -> list[dict[str, Any]]:
        occurrence = self.object
        transect = getattr(occurrence, "transect", None)
        return [
            {
                "title": _("Summary"),
                "icon": "fa-solid fa-circle-info",
                "items": [
                    {"label": _("Identifier"), "value": format_value(occurrence.pk)},
                    {
                        "label": _("Transect"),
                        "value": format_value(transect.name if transect else None),
                    },
                    {"label": _("State"), "value": format_value(occurrence.state)},
                    {"label": _("Recording started"), "value": format_datetime(occurrence.recording_start_time)},
                    {"label": _("Recording ended"), "value": format_datetime(occurrence.recording_end_time)},
                    {
                        "label": _("Latitude"),
                        "value": format_value(occurrence.lat),
                    },
                    {
                        "label": _("Longitude"),
                        "value": format_value(occurrence.long),
                    },
                ],
            },
            {
                "title": _("Notes"),
                "icon": "fa-solid fa-pen-to-square",
                "items": [
                    {"label": _("Note"), "value": format_pre(occurrence.note)},
                ],
            },
        ]

    def get_detail_table(self) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]]]:
        headers = [
            {"label": _("Phase")},
            {"label": _("Question")},
            {"label": _("Response")},
        ]
        rows: list[list[dict[str, Any]]] = []
        details = getattr(self.object, "details", None)
        info_entries = details.all() if hasattr(details, "all") else []
        for info in info_entries:
            rows.append(
                [
                    {"value": format_value(info.pre_or_post)},
                    {"value": format_value(info.question_text)},
                    {"value": format_value(info.response)},
                ]
            )
        return headers, rows

    @staticmethod
    def _resolve_instance_number(entry: Any) -> Any:
        value = getattr(entry, "instance_number", None)
        if value is not None:
            return value
        workflow = getattr(entry, "workflow", None)
        if workflow is not None:
            return getattr(workflow, "instance_number", None)
        return None

    @staticmethod
    def _sort_responses(entries: Sequence[Any]) -> list[Any]:
        def _sort_key(response: Any) -> tuple[Any, Any, Any]:
            workflow = getattr(response, "workflow", None)
            template_workflow = getattr(workflow, "template_workflow", None)
            workflow_name = getattr(template_workflow, "name", None)
            if workflow_name is None:
                workflow_name = getattr(workflow, "name", None)
            if workflow_name is None:
                workflow_name = getattr(workflow, "pk", "")
            question_number = getattr(response, "question_number", None)
            question_text = getattr(response, "question_text", "")
            return (str(workflow_name).lower(), question_number if question_number is not None else float("inf"), question_text)

        return sorted(entries, key=_sort_key)

    def get_response_table(
        self,
        responses: Iterable[Any] | None = None,
        *,
        instance_number: Any | None = None,
        question_texts: set[str] | None = None,
    ) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]]]:
        headers = [
            {"label": _("Question")},
            {"label": _("Response")},
            {"label": _("Response code")},
            {"label": _("Skipped")},
            {"label": _("Workflow")},
        ]
        rows: list[list[dict[str, Any]]] = []
        response_source = responses
        if response_source is None:
            response_source = getattr(self.object, "responses", None)
        response_entries = [
            entry for entry in self._as_list(response_source) if not getattr(entry, "skipped", False)
        ]
        if instance_number is not None:
            response_entries = [
                entry
                for entry in response_entries
                if self._resolve_instance_number(entry) == instance_number
            ]
        if question_texts is not None:
            response_entries = [
                entry
                for entry in response_entries
                if getattr(entry, "question_text", "") in question_texts
            ]
        response_entries = self._sort_responses(response_entries)
        for response in response_entries:
            workflow = getattr(response, "workflow", None)
            template_workflow = getattr(workflow, "template_workflow", None)
            workflow_label_source = getattr(template_workflow, "name", workflow)
            workflow_pk = getattr(workflow, "pk", None)
            rows.append(
                [
                    {"value": format_value(response.question_text)},
                    {"value": format_value(response.response)},
                    {"value": format_value(response.response_code)},
                    {"value": format_boolean(response.skipped)},
                    {
                        "value": format_value(workflow_label_source),
                        "url": safe_reverse(
                            "workflows:detail",
                            kwargs={"pk": workflow_pk} if workflow_pk is not None else None,
                        ),
                    },
                ]
            )
        return headers, rows

    def get_workflow_table(
        self,
        workflows: Iterable[Any] | None = None,
        *,
        instance_number: Any | None = None,
    ) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]]]:
        headers = [
            {"label": _("Template workflow")},
            {"label": _("Instance")},
            {"label": _("Completed by")},
        ]
        rows: list[list[dict[str, Any]]] = []
        workflow_source = workflows
        if workflow_source is None:
            workflow_source = getattr(self.object, "workflows", None)
        workflow_entries = self._as_list(workflow_source)
        if instance_number is not None:
            workflow_entries = [
                entry
                for entry in workflow_entries
                if getattr(entry, "instance_number", None) == instance_number
            ]
        for workflow in workflow_entries:
            workflow_pk = getattr(workflow, "pk", None)
            rows.append(
                [
                    {
                        "value": format_value(getattr(workflow.template_workflow, "name", workflow.template_workflow)),
                        "url": safe_reverse(
                            "workflows:detail",
                            kwargs={"pk": workflow_pk} if workflow_pk is not None else None,
                        ),
                    },
                    {"value": format_value(workflow.instance_number)},
                    {"value": format_value(workflow.completed_by)},
                ]
            )
        return headers, rows

    def get_instance_summaries(
        self,
        *,
        workflows: Iterable[Any] | None = None,
        responses: Iterable[Any] | None = None,
        images_by_instance: Mapping[Any, Sequence[EntityImage]] | None = None,
        question_texts: set[str] | None = None,
        match_question: str = "",
        match_response: str = "",
    ) -> list[dict[str, Any]]:
        workflow_entries = self._as_list(workflows if workflows is not None else getattr(self.object, "workflows", None))
        response_entries = self._as_list(responses if responses is not None else getattr(self.object, "responses", None))

        instance_order: list[Any] = []

        def _record_instance(value: Any) -> None:
            if value is None:
                return
            if value not in instance_order:
                instance_order.append(value)

        for workflow in workflow_entries:
            _record_instance(getattr(workflow, "instance_number", None))
        for response in response_entries:
            _record_instance(self._resolve_instance_number(response))

        instance_order.sort()

        if match_question and match_response:
            matching_instances = {
                self._resolve_instance_number(response)
                for response in response_entries
                if not getattr(response, "skipped", False)
                and str(getattr(response, "question_text", "")).casefold()
                == match_question.casefold()
                and str(getattr(response, "response", "")).casefold()
                == match_response.casefold()
            }
            instance_order = [
                number for number in instance_order if number in matching_instances
            ]

        summaries: list[dict[str, Any]] = []
        base_url = safe_reverse("workflows:list")
        occurrence_pk = getattr(self.object, "pk", None)

        for instance_number in instance_order:
            _, workflow_rows = self.get_workflow_table(
                workflow_entries,
                instance_number=instance_number,
            )
            _, response_rows = self.get_response_table(
                response_entries,
                instance_number=instance_number,
                question_texts=question_texts,
            )
            url = safe_reverse(
                "bones:occurrences:instance_detail",
                kwargs={
                    "occurrence_pk": occurrence_pk,
                    "instance_number": instance_number,
                },
            )
            summaries.append(
                {
                    "number": instance_number,
                    "display_number": format_value(instance_number),
                    "workflow_rows": workflow_rows,
                    "response_rows": response_rows,
                    "images": list((images_by_instance or {}).get(instance_number, [])),
                    "url": url,
                }
            )

        return summaries

    @staticmethod
    def get_response_question_choices(responses: Iterable[Any]) -> list[str]:
        return sorted(
            {
                str(response.question_text)
                for response in responses
                if getattr(response, "question_text", None)
                and not getattr(response, "skipped", False)
            },
            key=str.casefold,
        )

    @staticmethod
    def get_response_value_choices(responses: Iterable[Any]) -> list[str]:
        return sorted(
            {
                str(response.response)
                for response in responses
                if getattr(response, "response", None) not in (None, "")
                and not getattr(response, "skipped", False)
            },
            key=str.casefold,
        )

    def get_instance_images(
        self, instance_numbers: Iterable[Any]
    ) -> dict[Any, list[EntityImage]]:
        occurrence_pk = getattr(self.object, "pk", None)
        numbers_by_key = {
            instance_key(occurrence_pk, number): number
            for number in instance_numbers
        }
        if not numbers_by_key:
            return {}

        images = EntityImage.objects.filter(
            Q(targets__entity_type=EntityImage.INSTANCE, targets__entity_id__in=numbers_by_key)
            | Q(entity_type=EntityImage.INSTANCE, entity_id__in=numbers_by_key)
        ).prefetch_related("targets").distinct()
        grouped: dict[Any, list[EntityImage]] = {
            number: [] for number in numbers_by_key.values()
        }
        for image in images:
            direct_key = image.entity_id if image.entity_type == EntityImage.INSTANCE else None
            target_keys = {
                target.entity_id
                for target in image.targets.all()
                if target.entity_type == EntityImage.INSTANCE
            }
            for key in target_keys | ({direct_key} if direct_key else set()):
                number = numbers_by_key.get(key)
                if number is not None and image not in grouped[number]:
                    grouped[number].append(image)
        return grouped

    def get_history_entries(self) -> list[Any]:
        try:
            return list(self.object.history.all().order_by("-history_date")[:25])
        except DatabaseError:
            self.history_error = True
            return []

    def get_tabs(self) -> Iterable[Mapping[str, Any]]:
        return [
            {
                "id": "overview",
                "label": _("Overview"),
                "icon": "fa-solid fa-circle-info",
                "active": True,
                "template": "bones/completed_occurrences/_overview.html",
            },
            {
                "id": "map",
                "label": _("Map"),
                "icon": "fa-solid fa-map-location-dot",
                "active": False,
                "template": "bones/maps/_tab.html",
            },
            {
                "id": "related",
                "label": _("Instances"),
                "icon": "fa-solid fa-layer-group",
                "active": False,
                "template": "bones/completed_occurrences/_related.html",
            },
            {
                "id": "mni", "label": _("MNI"),
                "icon": "fa-solid fa-calculator", "active": False,
                "template": "bones/completed_occurrences/_mni.html",
            },
            {
                "id": "history",
                "label": _("History"),
                "icon": "fa-solid fa-clock-rotate-left",
                "active": False,
                "template": "bones/completed_occurrences/_history.html",
            },
            {
                "id": "images", "label": _("Images"), "icon": "fa-solid fa-images",
                "active": False, "template": "bones/images/_tab.html",
            },
        ]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        detail_headers, detail_rows = self.get_detail_table()
        workflows = self._as_list(getattr(self.object, "workflows", None))
        responses = self._as_list(getattr(self.object, "responses", None))
        response_question_choices = self.get_response_question_choices(responses)
        response_filter_applied = "response_filter_applied" in self.request.GET
        if response_filter_applied:
            selected_response_questions = self.request.GET.getlist("response_question")
        else:
            available_questions = set(response_question_choices)
            selected_response_questions = [
                question
                for question in self.default_response_questions
                if question in available_questions
            ]
        selected_response_question_set = (
            set(selected_response_questions) if selected_response_questions else None
        )
        match_question = self.request.GET.get("match_question", "").strip()
        match_response = self.request.GET.get("match_response", "").strip()
        response_headers, response_rows = self.get_response_table(responses=responses)
        workflow_headers, workflow_rows = self.get_workflow_table(workflows=workflows)
        history_entries = self.get_history_entries()
        occurrence_instances = self.get_instance_summaries(
            workflows=workflows,
            responses=responses,
            question_texts=selected_response_question_set,
            match_question=match_question,
            match_response=match_response,
        )
        images_by_instance = self.get_instance_images(
            instance["number"] for instance in occurrence_instances
        )
        for instance in occurrence_instances:
            instance["images"] = images_by_instance.get(instance["number"], [])
        context.update(
            {
                "overview_sections": self.get_overview_sections(),
                "occurrence_detail_headers": detail_headers,
                "occurrence_detail_rows": detail_rows,
                "occurrence_response_headers": response_headers,
                "occurrence_response_rows": response_rows,
                "occurrence_workflow_headers": workflow_headers,
                "occurrence_workflow_rows": workflow_rows,
                "occurrence_instances": occurrence_instances,
                "response_question_choices": response_question_choices,
                "response_value_choices": self.get_response_value_choices(responses),
                "selected_response_questions": selected_response_questions,
                "match_question": match_question,
                "match_response": match_response,
                "occurrence_history_entries": history_entries,
                "occurrence_history_error": self.history_error,
            }
        )
        try:
            context["mni_detail"] = build_mni_detail(
                self.object.transect_id, occurrence_id=self.object.pk
            )
        except DatabaseError:
            context["mni_detail"] = empty_mni_detail(
                _("MNI is temporarily unavailable.")
            )
        context.update(image_context("occurrence", self.object.pk, self.request.user))
        context.update(
            map_context(
                safe_reverse(
                    "bones:occurrences:map_data", kwargs={"pk": self.object.pk}
                ),
                title=_("Occurrence map"),
            )
        )
        return context

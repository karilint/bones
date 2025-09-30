"""Master-detail view archetypes for completed records."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from django.db import DatabaseError
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView

from .detail import (
    format_boolean,
    format_datetime,
    format_pre,
    format_value,
    safe_reverse,
)
from ..models import CompletedOccurrence, CompletedTransect
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
    list_route_name = "transects:list"
    history_route_name = "history:transect_record"
    breadcrumb_list_label = _("Completed transects")
    tablist_label = _("Transect detail navigation")

    def get_queryset(self):
        return (
            CompletedTransect.objects.select_related("transect_template")
            .with_occurrences()
            .with_details()
            .prefetch_related("track_points")
        )

    def get_extra_actions(self) -> Iterable[Mapping[str, Any]]:
        obj = self.object
        if not obj:
            return []
        return [
            {
                "label": _("Export responses"),
                "icon": "fa-solid fa-file-export",
                "url": safe_reverse("transects:export_responses", kwargs={"pk": obj.pk}),
            },
            {
                "label": _("Download GPS track"),
                "icon": "fa-solid fa-download",
                "url": safe_reverse("transects:download_track", kwargs={"pk": obj.pk}),
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
            rows.append(
                [
                    {
                        "value": _( "Occurrence {number}").format(number=occurrence.occurrence_number),
                        "url": safe_reverse("occurrences:detail", kwargs={"pk": occurrence.pk}),
                    },
                    {"value": format_value(occurrence.state)},
                    {"value": format_datetime(occurrence.recording_start_time)},
                    {"value": format_datetime(occurrence.recording_end_time)},
                    {
                        "value": len(self._as_list(getattr(occurrence, "responses", None))),
                        "classes": "w3-center",
                    },
                    {
                        "value": len(self._as_list(getattr(occurrence, "workflows", None))),
                        "classes": "w3-center",
                    },
                ]
            )
        return headers, rows

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
                "id": "related",
                "label": _("Related items"),
                "icon": "fa-solid fa-layer-group",
                "active": False,
                "template": "bones/completed_transects/_related.html",
            },
            {
                "id": "history",
                "label": _("History"),
                "icon": "fa-solid fa-clock-rotate-left",
                "active": False,
                "template": "bones/completed_transects/_history.html",
            },
        ]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        info_headers, info_rows = self.get_info_table()
        occurrence_headers, occurrence_rows = self.get_occurrence_table()
        track_headers, track_rows = self.get_track_point_table()
        history_entries = self.get_history_entries()
        context.update(
            {
                "overview_sections": self.get_overview_sections(),
                "transect_info_headers": info_headers,
                "transect_info_rows": info_rows,
                "transect_occurrence_headers": occurrence_headers,
                "transect_occurrence_rows": occurrence_rows,
                "transect_track_headers": track_headers,
                "transect_track_rows": track_rows,
                "transect_history_entries": history_entries,
                "transect_history_error": self.history_error,
            }
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
    list_route_name = "occurrences:list"
    history_route_name = "history:occurrence_record"
    breadcrumb_list_label = _("Completed occurrences")
    tablist_label = _("Occurrence detail navigation")

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

    def get_response_table(self) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]]]:
        headers = [
            {"label": _("Question")},
            {"label": _("Response")},
            {"label": _("Response code")},
            {"label": _("Skipped")},
            {"label": _("Workflow")},
        ]
        rows: list[list[dict[str, Any]]] = []
        responses = getattr(self.object, "responses", None)
        response_entries = responses.all() if hasattr(responses, "all") else []
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

    def get_workflow_table(self) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]]]:
        headers = [
            {"label": _("Template workflow")},
            {"label": _("Instance")},
            {"label": _("Completed by")},
        ]
        rows: list[list[dict[str, Any]]] = []
        workflows = getattr(self.object, "workflows", None)
        workflow_entries = workflows.all() if hasattr(workflows, "all") else []
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
                "id": "related",
                "label": _("Related items"),
                "icon": "fa-solid fa-layer-group",
                "active": False,
                "template": "bones/completed_occurrences/_related.html",
            },
            {
                "id": "history",
                "label": _("History"),
                "icon": "fa-solid fa-clock-rotate-left",
                "active": False,
                "template": "bones/completed_occurrences/_history.html",
            },
        ]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        detail_headers, detail_rows = self.get_detail_table()
        response_headers, response_rows = self.get_response_table()
        workflow_headers, workflow_rows = self.get_workflow_table()
        history_entries = self.get_history_entries()
        context.update(
            {
                "overview_sections": self.get_overview_sections(),
                "occurrence_detail_headers": detail_headers,
                "occurrence_detail_rows": detail_rows,
                "occurrence_response_headers": response_headers,
                "occurrence_response_rows": response_rows,
                "occurrence_workflow_headers": workflow_headers,
                "occurrence_workflow_rows": workflow_rows,
                "occurrence_history_entries": history_entries,
                "occurrence_history_error": self.history_error,
            }
        )
        return context

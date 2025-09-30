"""Navigation context helpers for the Bones application.

This module centralises the primary navigation structure so templates and
views can rely on a single source of truth. The context processor resolves
URL names lazily and falls back to sensible routes (such as child links or the
dashboard) when targets have not been wired yet, which keeps the interface
functional during incremental development without exposing broken ``#`` links.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional

from django.urls import NoReverseMatch, reverse


NavigationLink = Mapping[str, Any]


def _safe_reverse(url_name: Optional[str], *, kwargs: Optional[Mapping[str, Any]] = None) -> Optional[str]:
    """Resolve a URL name if it exists, otherwise return ``None``.

    The navigation plan references routes that will come online over the course
    of the coding plan. Swallow ``NoReverseMatch`` errors so placeholder links
    can gracefully fall back to other working URLs until their corresponding
    views exist.
    """
    if not url_name:
        return None

    try:
        return reverse(url_name, kwargs=kwargs)
    except NoReverseMatch:
        return None


def _materialise_link(link: NavigationLink) -> Dict[str, Any]:
    """Return a link dictionary augmented with a resolved URL."""

    children = [_materialise_link(child) for child in link.get("children", [])]
    resolved_url = link.get("url") or _safe_reverse(link.get("url_name"), kwargs=link.get("kwargs"))

    fallback_sources: Iterable[Optional[str]] = (
        link.get("fallback_url"),
        _safe_reverse(link.get("fallback_url_name"), kwargs=link.get("fallback_kwargs")),
        *[child.get("url") for child in children if child.get("url")],
        "/",
    )

    url = resolved_url
    if not url:
        for candidate in fallback_sources:
            if candidate:
                url = candidate
                break

    return {
        "label": link.get("label", ""),
        "icon": link.get("icon"),
        "url": url,
        "children": children,
    }


NAVIGATION_SECTIONS: List[NavigationLink] = [
    {
        "label": "Dashboard",
        "icon": "fa-solid fa-gauge-high",
        "url_name": "dashboard",
        "children": [
            {"label": "Overview", "url_name": "dashboard"},
            {
                "label": "Recent Activity",
                "url_name": "history:dashboard",
                "fallback_url_name": "history:index",
            },
        ],
    },
    {
        "label": "Transects",
        "icon": "fa-solid fa-route",
        "url_name": "transects:list",
        "children": [
            {"label": "Completed Transects", "url_name": "transects:list"},
            {
                "label": "Transect Detail",
                "url_name": "transects:detail",
                "fallback_url_name": "transects:list",
            },
            {"label": "Transect History", "url_name": "history:transects"},
        ],
    },
    {
        "label": "Occurrences",
        "icon": "fa-solid fa-frog",
        "url_name": "occurrences:list",
        "children": [
            {"label": "Completed Occurrences", "url_name": "occurrences:list"},
            {
                "label": "Occurrence Detail",
                "url_name": "occurrences:detail",
                "fallback_url_name": "occurrences:list",
            },
            {"label": "Occurrence History", "url_name": "history:occurrences"},
        ],
    },
    {
        "label": "Workflows",
        "icon": "fa-solid fa-diagram-project",
        "url_name": "workflows:list",
        "children": [
            {"label": "Workflow Runs", "url_name": "workflows:list"},
            {
                "label": "Workflow Detail",
                "url_name": "workflows:detail",
                "fallback_url_name": "workflows:list",
            },
            {"label": "Workflow History", "url_name": "history:workflows"},
        ],
    },
    {
        "label": "Templates",
        "icon": "fa-solid fa-layer-group",
        "url_name": "templates:list",
        "children": [
            {"label": "Template Transects", "url_name": "templates:list"},
            {
                "label": "Template Detail",
                "url_name": "templates:detail",
                "fallback_url_name": "templates:list",
            },
            {"label": "Template Questions", "url_name": "templates:questions"},
        ],
    },
    {
        "label": "Reference Data",
        "icon": "fa-solid fa-database",
        "url_name": "reference:list",
        "children": [
            {"label": "Data Types", "url_name": "reference:data_types"},
            {"label": "Data Type Options", "url_name": "reference:data_type_options"},
            {"label": "Project Config", "url_name": "reference:project_config"},
        ],
    },
    {
        "label": "Data Logs",
        "icon": "fa-solid fa-file-arrow-down",
        "url_name": "logs:list",
        "children": [
            {"label": "Uploaded Logs", "url_name": "logs:list"},
            {
                "label": "Log Detail",
                "url_name": "logs:detail",
                "fallback_url_name": "logs:list",
            },
        ],
    },
    {
        "label": "History",
        "icon": "fa-solid fa-clock-rotate-left",
        "url_name": "history:index",
        "children": [
            {"label": "Transect History", "url_name": "history:transects"},
            {"label": "Occurrence History", "url_name": "history:occurrences"},
            {"label": "Workflow History", "url_name": "history:workflows"},
            {"label": "Question History", "url_name": "history:questions"},
        ],
    },
]


def navigation_context(request: Any) -> Dict[str, Any]:
    """Provide navigation metadata for base templates and partials.

    Returns a list of navigation sections resolved from :data:`NAVIGATION_SECTIONS`
    with URLs reversed when available. The structure aligns with the Django app
    guidelines so downstream archetypes (dashboard, list, detail, history) can
    depend on consistent labelling and iconography.
    """
    return {
        "navigation_sections": [_materialise_link(section) for section in NAVIGATION_SECTIONS],
    }

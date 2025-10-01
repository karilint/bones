"""Custom template tags to assist with pagination rendering."""

from __future__ import annotations

from typing import Iterable

from django import template

register = template.Library()


@register.simple_tag
def compact_page_range(page_obj, max_length: int = 3) -> Iterable[int]:
    """Return a compact range of page numbers centered on the current page.

    The range includes at most ``max_length`` numbers, favors centering the
    current page when possible, and gracefully handles small collections.
    """

    total_pages = getattr(page_obj, "paginator").num_pages
    current = getattr(page_obj, "number")
    window = max(1, int(max_length))

    if total_pages <= window:
        start = 1
        end = total_pages
    else:
        half_window = window // 2
        start = current - half_window
        end = current + half_window

        if window % 2 == 0:
            end -= 1

        if start < 1:
            start = 1
            end = window
        elif end > total_pages:
            end = total_pages
            start = total_pages - window + 1

    return range(start, end + 1)

from django.shortcuts import render
from django.db import DatabaseError

from .models import CompletedTransect


def hello_world(request):
    """Render a simple page with the CompletedTransects count."""
    try:
        completed_transects_count = CompletedTransect.objects.count()
    except DatabaseError:
        completed_transects_count = None

    context = {
        "completed_transects_count": completed_transects_count,
    }
    return render(request, "bones/hello_world.html", context)

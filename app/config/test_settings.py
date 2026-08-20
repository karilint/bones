"""Offline-safe settings for the automated Bones test suite."""
from .settings import *  # noqa: F403


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}


# Bones has SQL Server-only schema operations for unmanaged production tables.
# Tests create the few unmanaged SQLite fixtures they need explicitly, while
# Django synchronizes application-managed models directly from model state.
MIGRATION_MODULES = {"bones": None}

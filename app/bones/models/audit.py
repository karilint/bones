from __future__ import annotations

import uuid

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from simple_history.models import HistoricalRecords


class InstanceDeletion(models.Model):
    """Permanent audit summary for deleting one logical occurrence instance."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template_name = models.CharField(max_length=200)
    transect_uid = models.IntegerField(db_index=True)
    transect_date = models.DateField(blank=True, null=True)
    occurrence_id = models.IntegerField(db_index=True)
    occurrence_number = models.IntegerField()
    instance_number = models.IntegerField(db_index=True)
    reason = models.CharField(max_length=100)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bones_instance_deletions",
    )
    deleted_at = models.DateTimeField(auto_now_add=True, db_index=True)
    workflow_count = models.PositiveIntegerField(default=0)
    response_count = models.PositiveIntegerField(default=0)
    image_link_count = models.PositiveIntegerField(default=0)
    image_file_count = models.PositiveIntegerField(default=0)
    workflow_snapshot = models.JSONField(default=list, blank=True)
    response_snapshot = models.JSONField(default=list, blank=True)
    image_snapshot = models.JSONField(default=list, blank=True)
    restoration_status = models.CharField(max_length=20, default="deleted", db_index=True)
    restored_at = models.DateTimeField(blank=True, null=True)
    restored_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="bones_instance_restorations",
    )
    restoration_reason = models.CharField(max_length=100, blank=True)
    restoration_error = models.TextField(blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ("-deleted_at",)
        permissions = (
            ("delete_completed_instance", "Can delete completed instances"),
            ("restore_completed_instance", "Can restore completed instances"),
        )
        indexes = [
            models.Index(
                fields=("occurrence_id", "instance_number"),
                name="bones_deleted_instance_idx",
            )
        ]

    def __str__(self):
        return (
            f"Transect {self.transect_uid}, occurrence {self.occurrence_number}, "
            f"instance {self.instance_number}"
        )


class TransectDeletion(models.Model):
    """Permanent audit summary for deleting one completed transect."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transect_uid = models.IntegerField(db_index=True)
    transect_name = models.CharField(max_length=200)
    template_name = models.CharField(max_length=200)
    transect_date = models.DateField(blank=True, null=True)
    reason = models.CharField(max_length=100)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bones_transect_deletions")
    deleted_at = models.DateTimeField(auto_now_add=True, db_index=True)
    occurrence_count = models.PositiveIntegerField(default=0)
    workflow_count = models.PositiveIntegerField(default=0)
    response_count = models.PositiveIntegerField(default=0)
    snapshot = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder)
    history = HistoricalRecords()

    class Meta:
        ordering = ("-deleted_at",)
        permissions = (("delete_completed_transect", "Can delete completed transects"),)

    def __str__(self):
        return f"{self.transect_name} ({self.transect_uid})"


class OccurrenceDeletion(models.Model):
    """Permanent snapshot of a deleted completed occurrence and its children."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurrence_id = models.IntegerField(db_index=True)
    occurrence_number = models.IntegerField()
    transect_uid = models.IntegerField(db_index=True)
    template_name = models.CharField(max_length=200)
    reason = models.CharField(max_length=100)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="bones_occurrence_deletions",
    )
    deleted_at = models.DateTimeField(auto_now_add=True, db_index=True)
    workflow_count = models.PositiveIntegerField(default=0)
    response_count = models.PositiveIntegerField(default=0)
    snapshot = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder)

    history = HistoricalRecords()

    class Meta:
        ordering = ("-deleted_at",)
        permissions = (("delete_completed_occurrence", "Can delete completed occurrences"),)

    def __str__(self):
        return f"Occurrence {self.occurrence_number} ({self.occurrence_id})"

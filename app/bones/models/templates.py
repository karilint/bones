"""Template entities used to seed completed work."""
from django.db import models


class TemplateWorkflowQuerySet(models.QuerySet):
    """Helpers for eager loading template workflow relations."""

    def with_questions(self):
        """Select related questions for configuration dashboards."""
        return self.prefetch_related("questions")


class TemplateWorkflowManager(models.Manager.from_queryset(TemplateWorkflowQuerySet)):
    """Manager exposing helpers for template workflows."""

    pass


class TemplateTransectQuerySet(models.QuerySet):
    """Helpers for fetching template transects."""

    def with_completed_transects(self):
        """Prefetch completed transects spawned from the template."""
        return self.prefetch_related("completed_transects")


class TemplateTransectManager(models.Manager.from_queryset(TemplateTransectQuerySet)):
    """Manager exposing helpers for template transects."""

    pass


class TemplateWorkflow(models.Model):
    id = models.CharField(db_column="ID", primary_key=True, max_length=36)
    name = models.CharField(
        db_column="Name",
        max_length=50,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
    )
    date_added = models.DateTimeField(db_column="DateAdded", blank=True, null=True)
    added_by = models.CharField(
        db_column="AddedBy",
        max_length=50,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
        blank=True,
        null=True,
    )

    objects = TemplateWorkflowManager()

    class Meta:
        managed = False
        db_table = "TemplateWorkflows"
        verbose_name = "Template workflow"
        verbose_name_plural = "Template workflows"

    def __str__(self) -> str:
        return self.name


class TemplateTransect(models.Model):
    id = models.CharField(db_column="ID", primary_key=True, max_length=36)
    name = models.CharField(
        db_column="Name",
        max_length=200,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
    )
    scheduled_time = models.DateTimeField(db_column="Scheduled_time")
    lat_from = models.DecimalField(db_column="Lat_from", max_digits=12, decimal_places=8)
    long_from = models.DecimalField(db_column="Long_from", max_digits=12, decimal_places=8)
    lat_to = models.DecimalField(
        db_column="Lat_to", max_digits=12, decimal_places=8, blank=True, null=True
    )
    long_to = models.DecimalField(
        db_column="Long_to", max_digits=12, decimal_places=8, blank=True, null=True
    )
    open_ended = models.BooleanField(db_column="Open_ended", blank=True, null=True)
    distance_km = models.FloatField(db_column="Distance_km", blank=True, null=True)
    angle_degrees = models.IntegerField(db_column="Angle_degrees", blank=True, null=True)
    note = models.CharField(
        db_column="Note",
        max_length=4000,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
        blank=True,
        null=True,
    )
    created_dynamically = models.BooleanField(
        db_column="CreatedDynamically", blank=True, null=True
    )

    objects = TemplateTransectManager()

    class Meta:
        managed = False
        db_table = "TemplateTransects"
        verbose_name = "Template transect"
        verbose_name_plural = "Template transects"

    def __str__(self) -> str:
        return self.name

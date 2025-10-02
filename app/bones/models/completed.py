"""Completed entity models and query utilities."""
from django.db import models
from django.db.models import Count, Prefetch
from simple_history.models import HistoricalRecords


class CompletedResponseQuerySet(models.QuerySet):
    """Additional helpers for chaining response lookups."""

    def with_questions(self):
        """Select related question metadata to avoid per-row lookups."""
        return self.select_related("question", "workflow", "workflow__template_workflow")


class CompletedResponseManager(models.Manager.from_queryset(CompletedResponseQuerySet)):
    """Manager exposing helpers for completed responses."""

    pass


class CompletedWorkflowQuerySet(models.QuerySet):
    """Reusable queryset helpers for completed workflows."""

    def with_templates(self):
        """Select the originating template workflow for summary views."""
        return self.select_related("template_workflow")


class CompletedWorkflowManager(models.Manager.from_queryset(CompletedWorkflowQuerySet)):
    """Manager exposing helpers for completed workflows."""

    pass


class CompletedOccurrenceQuerySet(models.QuerySet):
    """Helpers for fetching occurrences with their dependent records."""

    def with_responses(self):
        """Prefetch responses with question metadata."""
        return self.prefetch_related(
            Prefetch(
                "responses",
                queryset=CompletedResponse.objects.with_questions(),
            )
        )

    def with_workflows(self):
        """Prefetch related workflows and their template data."""
        return self.prefetch_related(
            Prefetch(
                "workflows",
                queryset=CompletedWorkflow.objects.with_templates(),
            )
        )

    def with_details(self):
        """Prefetch related information rows for display tabs."""
        return self.prefetch_related("details")

    def with_response_counts(self):
        """Annotate the number of responses captured for each occurrence."""
        return self.annotate(response_count=Count("responses"))

    def with_related_data(self):
        """Bundle common prefetch chains for list/detail screens."""
        return self.with_responses().with_workflows().with_details()


class CompletedOccurrenceManager(models.Manager.from_queryset(CompletedOccurrenceQuerySet)):
    """Manager exposing helpers for completed occurrences."""

    pass


class CompletedTransectQuerySet(models.QuerySet):
    """Query helpers for completed transects."""

    def with_occurrence_counts(self):
        """Annotate the number of occurrences related to each transect."""
        return self.annotate(occurrence_count=Count("occurrences"))

    def with_occurrences(self):
        """Prefetch occurrences and their nested dependencies."""
        return self.prefetch_related(
            Prefetch(
                "occurrences",
                queryset=CompletedOccurrence.objects.with_related_data(),
            )
        )

    def with_details(self):
        """Prefetch related info rows and track points."""
        return self.prefetch_related("details", "track_points")

    def for_dashboard(self):
        """Combine the prefetch helpers typically used on dashboards."""
        return (
            self.select_related("transect_template")
            .with_occurrences()
            .with_details()
        )


class CompletedTransectManager(models.Manager.from_queryset(CompletedTransectQuerySet)):
    """Manager exposing helpers for completed transects."""

    pass


class CompletedTransect(models.Model):
    uid = models.IntegerField(db_column="UID", primary_key=True)
    name = models.CharField(
        db_column="Name",
        max_length=200,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
    )
    start_time = models.DateTimeField()
    turn_time = models.DateTimeField(blank=True, null=True)
    end_time = models.DateTimeField()
    lat_from = models.DecimalField(max_digits=12, decimal_places=8)
    long_from = models.DecimalField(max_digits=12, decimal_places=8)
    lat_turn = models.DecimalField(max_digits=12, decimal_places=8, blank=True, null=True)
    long_turn = models.DecimalField(max_digits=12, decimal_places=8, blank=True, null=True)
    lat_to = models.DecimalField(max_digits=12, decimal_places=8)
    long_to = models.DecimalField(max_digits=12, decimal_places=8)
    distance_km = models.FloatField()
    angle_degrees = models.IntegerField()
    state = models.CharField(
        max_length=50,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
    )
    transect_template = models.ForeignKey(
        "bones.TemplateTransect",
        models.DO_NOTHING,
        db_column="TransectTemplateID",
        blank=True,
        null=True,
        related_name="completed_transects",
        db_constraint=False,
    )
    paused_for_minutes = models.IntegerField(
        db_column="PausedFor_Minutes", blank=True, null=True
    )

    history = HistoricalRecords()

    objects = CompletedTransectManager()

    class Meta:
        managed = False
        db_table = "CompletedTransects"
        verbose_name = "Completed transect"
        verbose_name_plural = "Completed transects"

    def __str__(self) -> str:
        return f"{self.name} ({self.uid})"


class CompletedTransectInfo(models.Model):
    transect = models.ForeignKey(
        CompletedTransect,
        models.DO_NOTHING,
        db_column="TransectUID",
        related_name="details",
        db_constraint=False,
    )
    pre_or_post = models.CharField(
        db_column="Pre_or_Post",
        max_length=4,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
    )
    question_text = models.CharField(
        db_column="QuestionText",
        max_length=200,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
    )
    response_data_type = models.CharField(
        db_column="ResponseDataType", max_length=36, blank=True, null=True
    )
    response_code = models.CharField(
        db_column="ResponseCode",
        max_length=50,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
        blank=True,
        null=True,
    )
    response = models.CharField(
        db_column="Response",
        max_length=200,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
        blank=True,
        null=True,
    )

    class Meta:
        managed = False
        db_table = "CompletedTransectsInfo"
        verbose_name = "Completed transect info"
        verbose_name_plural = "Completed transect info"

    def __str__(self) -> str:
        return f"{self.pre_or_post} - {self.question_text}"


class CompletedTransectTrack(models.Model):
    id = models.AutoField(db_column="ID", primary_key=True)
    user = models.CharField(
        db_column="User",
        max_length=64,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
    )
    transect = models.ForeignKey(
        CompletedTransect,
        models.DO_NOTHING,
        db_column="CompletedTransectUID",
        related_name="track_points",
        db_constraint=False,
    )
    time = models.DateTimeField(db_column="Time")
    lat = models.DecimalField(db_column="Lat", max_digits=12, decimal_places=8)
    long = models.DecimalField(db_column="Long", max_digits=12, decimal_places=8)
    is_start = models.BooleanField(db_column="isStart")
    is_checkpoint = models.BooleanField(db_column="isCheckPoint")
    is_occurrence = models.BooleanField(db_column="isOccurrence")
    is_turn_point = models.BooleanField(db_column="isTurnPoint")
    is_end = models.BooleanField(db_column="isEnd")

    class Meta:
        managed = False
        db_table = "CompletedTransectsTrack"
        unique_together = (
            (
                "transect",
                "user",
                "time",
                "is_start",
                "is_checkpoint",
                "is_occurrence",
                "is_turn_point",
                "is_end",
            ),
        )
        verbose_name = "Completed transect track point"
        verbose_name_plural = "Completed transect track points"

    def __str__(self) -> str:
        return f"{self.user} @ {self.time:%Y-%m-%d %H:%M:%S}"


class CompletedOccurrence(models.Model):
    id = models.AutoField(db_column="ID", primary_key=True)
    transect = models.ForeignKey(
        CompletedTransect,
        models.DO_NOTHING,
        db_column="TransectUID",
        related_name="occurrences",
        db_constraint=False,
    )
    occurrence_number = models.IntegerField(db_column="OccurrenceNumber")
    recording_start_time = models.DateTimeField(db_column="RecordingStartTime")
    recording_end_time = models.DateTimeField(
        db_column="RecordingEndTime", blank=True, null=True
    )
    lat = models.DecimalField(
        db_column="Lat", max_digits=12, decimal_places=8, blank=True, null=True
    )
    long = models.DecimalField(
        db_column="Long", max_digits=12, decimal_places=8, blank=True, null=True
    )
    note = models.CharField(
        db_column="Note",
        max_length=50,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
        blank=True,
        null=True,
    )
    state = models.CharField(
        db_column="State",
        max_length=50,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
        blank=True,
        null=True,
    )

    history = HistoricalRecords()

    objects = CompletedOccurrenceManager()

    class Meta:
        managed = False
        db_table = "CompletedOccurrences"
        verbose_name = "Completed occurrence"
        verbose_name_plural = "Completed occurrences"

    def __str__(self) -> str:
        return f"Occurrence {self.occurrence_number} (transect {self.transect_id})"


class CompletedOccurrenceInfo(models.Model):
    occurrence = models.ForeignKey(
        CompletedOccurrence,
        models.DO_NOTHING,
        db_column="OccurrenceID",
        related_name="details",
        db_constraint=False,
    )
    pre_or_post = models.CharField(
        db_column="Pre_or_Post",
        max_length=4,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
    )
    question_text = models.CharField(
        db_column="QuestionText",
        max_length=200,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
    )
    response_data_type = models.CharField(
        db_column="ResponseDataType", max_length=36, blank=True, null=True
    )
    response_code = models.CharField(
        db_column="ResponseCode",
        max_length=50,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
        blank=True,
        null=True,
    )
    response = models.CharField(
        db_column="Response",
        max_length=200,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
        blank=True,
        null=True,
    )

    class Meta:
        managed = False
        db_table = "CompletedOccurrencesInfo"
        verbose_name = "Completed occurrence info"
        verbose_name_plural = "Completed occurrence info"

    def __str__(self) -> str:
        return f"{self.pre_or_post} - {self.question_text}"


class CompletedWorkflow(models.Model):
    uid = models.CharField(db_column="UID", primary_key=True, max_length=36)
    occurrence = models.ForeignKey(
        CompletedOccurrence,
        models.DO_NOTHING,
        db_column="OccurrenceID",
        related_name="workflows",
        db_constraint=False,
    )
    template_workflow = models.ForeignKey(
        "bones.TemplateWorkflow",
        models.DO_NOTHING,
        db_column="TemplateWorkflowID",
        related_name="completed_workflows",
        db_constraint=False,
    )
    instance_number = models.IntegerField(db_column="InstanceNumber")
    completed_by = models.CharField(
        db_column="CompletedBy",
        max_length=100,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
        blank=True,
        null=True,
    )

    history = HistoricalRecords()

    objects = CompletedWorkflowManager()

    class Meta:
        managed = False
        db_table = "CompletedWorkflows"
        verbose_name = "Completed workflow"
        verbose_name_plural = "Completed workflows"

    def __str__(self) -> str:
        return f"Workflow {self.uid}"


class CompletedResponse(models.Model):
    id = models.AutoField(db_column="ID", primary_key=True)
    occurrence = models.ForeignKey(
        CompletedOccurrence,
        models.DO_NOTHING,
        db_column="OccurrenceID",
        related_name="responses",
        db_constraint=False,
    )
    workflow = models.ForeignKey(
        CompletedWorkflow,
        models.DO_NOTHING,
        db_column="CompletedWorkflowID",
        related_name="responses",
        db_constraint=False,
    )
    question_number = models.IntegerField(db_column="QuestionNumber", blank=True, null=True)
    question_text = models.CharField(
        db_column="QuestionText",
        max_length=2000,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
    )
    response_code = models.CharField(
        db_column="ResponseCode",
        max_length=50,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
        blank=True,
        null=True,
    )
    response = models.CharField(
        db_column="Response",
        max_length=2000,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
        blank=True,
        null=True,
    )
    skipped = models.BooleanField()
    question = models.ForeignKey(
        "bones.Question",
        models.DO_NOTHING,
        db_column="QuestionID",
        related_name="completed_responses",
        db_constraint=False,
    )

    objects = CompletedResponseManager()

    class Meta:
        managed = False
        db_table = "CompletedResponses"
        verbose_name = "Completed response"
        verbose_name_plural = "Completed responses"

    def __str__(self) -> str:
        return f"Response {self.id}"

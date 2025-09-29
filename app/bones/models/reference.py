"""Reference and configuration models."""
from django.db import models
from simple_history.models import HistoricalRecords


class DataTypeQuerySet(models.QuerySet):
    """Helpers for loading related data type configuration."""

    def with_options(self):
        return self.prefetch_related("options")


class DataTypeManager(models.Manager.from_queryset(DataTypeQuerySet)):
    """Manager exposing helpers for data types."""

    pass


class QuestionQuerySet(models.QuerySet):
    """Helpers for question lookups."""

    def with_related(self):
        return self.select_related("data_type", "workflow")


class QuestionManager(models.Manager.from_queryset(QuestionQuerySet)):
    """Manager exposing helpers for questions."""

    pass


class DataLogFile(models.Model):
    id = models.AutoField(db_column="ID", primary_key=True)
    upload_date = models.DateTimeField(db_column="UploadDate", blank=True, null=True)
    uploaded_by = models.CharField(
        db_column="UploadedBy",
        max_length=100,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
        blank=True,
        null=True,
    )
    contents = models.TextField(
        db_column="Contents",
        db_collation="SQL_Latin1_General_CP1_CI_AS",
        blank=True,
        null=True,
    )

    class Meta:
        managed = False
        db_table = "DataLogFiles"
        verbose_name = "Data log file"
        verbose_name_plural = "Data log files"

    def __str__(self) -> str:
        return f"Data log {self.id}"


class DataType(models.Model):
    id = models.CharField(db_column="ID", primary_key=True, max_length=36)
    name = models.CharField(
        db_column="Name",
        max_length=100,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
    )
    is_user_data_type = models.BooleanField(db_column="isUserDataType")
    csharp_type = models.CharField(
        db_column="CSharp_Type",
        max_length=200,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
        blank=True,
        null=True,
    )

    objects = DataTypeManager()

    class Meta:
        managed = False
        db_table = "DataTypes"
        verbose_name = "Data type"
        verbose_name_plural = "Data types"

    def __str__(self) -> str:
        return self.name


class DataTypeOption(models.Model):
    data_type = models.ForeignKey(
        DataType,
        models.DO_NOTHING,
        db_column="DataTypeID",
        related_name="options",
        db_constraint=False,
    )
    code = models.CharField(
        db_column="ID",
        max_length=200,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
    )
    text = models.CharField(
        db_column="Text",
        max_length=500,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
        blank=True,
        null=True,
    )

    class Meta:
        managed = False
        db_table = "DataTypeOptions"
        unique_together = (("data_type", "code"),)
        verbose_name = "Data type option"
        verbose_name_plural = "Data type options"

    def __str__(self) -> str:
        return f"{self.data_type_id}:{self.code}"


class ProjectConfig(models.Model):
    id = models.AutoField(db_column="ID", primary_key=True)
    publish_date = models.DateTimeField(db_column="PublishDate")
    project = models.CharField(
        db_column="Project",
        max_length=50,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
    )
    config_folder = models.CharField(
        db_column="ConfigFolder",
        max_length=100,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
    )
    config_file = models.TextField(
        db_column="ConfigFile",
        db_collation="SQL_Latin1_General_CP1_CI_AS",
    )
    image = models.TextField(
        db_column="Image",
        db_collation="SQL_Latin1_General_CP1_CI_AS",
        blank=True,
        null=True,
    )
    transects_file = models.TextField(
        db_column="transectsFile",
        db_collation="SQL_Latin1_General_CP1_CI_AS",
    )

    class Meta:
        managed = False
        db_table = "ProjectConfigs"
        verbose_name = "Project config"
        verbose_name_plural = "Project configs"

    def __str__(self) -> str:
        return f"{self.project} @ {self.publish_date:%Y-%m-%d}"


class Question(models.Model):
    id = models.CharField(db_column="ID", primary_key=True, max_length=36)
    prompt = models.CharField(
        db_column="Prompt",
        max_length=2000,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
        blank=True,
        null=True,
    )
    data_type = models.ForeignKey(
        DataType,
        models.DO_NOTHING,
        db_column="DataTypeID",
        related_name="questions",
        db_constraint=False,
    )
    data_type_name = models.CharField(
        db_column="DataTypeName",
        max_length=200,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
    )
    workflow = models.ForeignKey(
        "bones.TemplateWorkflow",
        models.DO_NOTHING,
        db_column="WorkflowID",
        related_name="questions",
        blank=True,
        null=True,
        db_constraint=False,
    )

    history = HistoricalRecords()

    objects = QuestionManager()

    class Meta:
        managed = False
        db_table = "Questions"
        verbose_name = "Question"
        verbose_name_plural = "Questions"

    def __str__(self) -> str:
        return self.prompt or self.id


class TransectDataLog(models.Model):
    id = models.AutoField(db_column="ID", primary_key=True)
    data_log_file = models.ForeignKey(
        DataLogFile,
        models.DO_NOTHING,
        db_column="DataLogFileID",
        related_name="transect_links",
        db_constraint=False,
    )
    transect = models.ForeignKey(
        "bones.CompletedTransect",
        models.DO_NOTHING,
        db_column="TransectID",
        related_name="data_log_links",
        db_constraint=False,
    )
    is_primary = models.BooleanField(db_column="isPrimary", blank=True, null=True)
    username = models.CharField(
        db_column="Username",
        max_length=200,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
        blank=True,
        null=True,
    )

    class Meta:
        managed = False
        db_table = "xTransectDataLog"
        verbose_name = "Transect data log link"
        verbose_name_plural = "Transect data log links"

    def __str__(self) -> str:
        return f"Log {self.data_log_file_id} -> Transect {self.transect_id}"

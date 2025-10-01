from django.db import migrations


CREATE_SCHEDULED_TIME_INDEX = """
IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_TemplateTransects_ScheduledTime'
      AND object_id = OBJECT_ID('TemplateTransects')
)
BEGIN
    CREATE INDEX IX_TemplateTransects_ScheduledTime
        ON TemplateTransects ([Scheduled_time] DESC);
END
"""

DROP_SCHEDULED_TIME_INDEX = """
IF EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_TemplateTransects_ScheduledTime'
      AND object_id = OBJECT_ID('TemplateTransects')
)
BEGIN
    DROP INDEX IX_TemplateTransects_ScheduledTime ON TemplateTransects;
END
"""


class Migration(migrations.Migration):

    dependencies = [
        ("bones", "0004_completedworkflow_indexes"),
    ]

    operations = [
        migrations.RunSQL(
            CREATE_SCHEDULED_TIME_INDEX,
            DROP_SCHEDULED_TIME_INDEX,
        ),
    ]

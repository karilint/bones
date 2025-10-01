from django.db import migrations


CREATE_OCCURRENCE_INSTANCE = """
IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_CompletedWorkflows_Occurrence_InstanceNumber'
      AND object_id = OBJECT_ID('CompletedWorkflows')
)
BEGIN
    CREATE INDEX IX_CompletedWorkflows_Occurrence_InstanceNumber
        ON CompletedWorkflows ([OccurrenceID] ASC, [InstanceNumber] DESC);
END
"""

DROP_OCCURRENCE_INSTANCE = """
IF EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_CompletedWorkflows_Occurrence_InstanceNumber'
      AND object_id = OBJECT_ID('CompletedWorkflows')
)
BEGIN
    DROP INDEX IX_CompletedWorkflows_Occurrence_InstanceNumber ON CompletedWorkflows;
END
"""

CREATE_TEMPLATE = """
IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_CompletedWorkflows_TemplateWorkflow'
      AND object_id = OBJECT_ID('CompletedWorkflows')
)
BEGIN
    CREATE INDEX IX_CompletedWorkflows_TemplateWorkflow
        ON CompletedWorkflows ([TemplateWorkflowID]);
END
"""

DROP_TEMPLATE = """
IF EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_CompletedWorkflows_TemplateWorkflow'
      AND object_id = OBJECT_ID('CompletedWorkflows')
)
BEGIN
    DROP INDEX IX_CompletedWorkflows_TemplateWorkflow ON CompletedWorkflows;
END
"""


class Migration(migrations.Migration):

    dependencies = [
        ("bones", "0003_completedoccurrence_indexes"),
    ]

    operations = [
        migrations.RunSQL(CREATE_OCCURRENCE_INSTANCE, DROP_OCCURRENCE_INSTANCE),
        migrations.RunSQL(CREATE_TEMPLATE, DROP_TEMPLATE),
    ]

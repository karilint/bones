from django.db import migrations


class RunSQLServer(migrations.RunSQL):
    """Run raw index SQL only on the production SQL Server backend."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "microsoft":
            super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "microsoft":
            super().database_backwards(app_label, schema_editor, from_state, to_state)


CREATE_OCCURRENCE_INDEX = """
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_CompletedResponses_OccurrenceID'
      AND object_id = OBJECT_ID('CompletedResponses')
)
BEGIN
    CREATE INDEX IX_CompletedResponses_OccurrenceID
        ON CompletedResponses ([OccurrenceID]);
END
"""

DROP_OCCURRENCE_INDEX = """
IF EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_CompletedResponses_OccurrenceID'
      AND object_id = OBJECT_ID('CompletedResponses')
)
BEGIN
    DROP INDEX IX_CompletedResponses_OccurrenceID ON CompletedResponses;
END
"""

CREATE_WORKFLOW_INDEX = """
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_CompletedResponses_WorkflowID'
      AND object_id = OBJECT_ID('CompletedResponses')
)
BEGIN
    CREATE INDEX IX_CompletedResponses_WorkflowID
        ON CompletedResponses ([CompletedWorkflowID]);
END
"""

DROP_WORKFLOW_INDEX = """
IF EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_CompletedResponses_WorkflowID'
      AND object_id = OBJECT_ID('CompletedResponses')
)
BEGIN
    DROP INDEX IX_CompletedResponses_WorkflowID ON CompletedResponses;
END
"""


class Migration(migrations.Migration):
    dependencies = [("bones", "0028_data_reconciliation_permission")]
    operations = [
        RunSQLServer(CREATE_OCCURRENCE_INDEX, DROP_OCCURRENCE_INDEX),
        RunSQLServer(CREATE_WORKFLOW_INDEX, DROP_WORKFLOW_INDEX),
    ]

from django.db import migrations


class RunSQLServer(migrations.RunSQL):
    """Run raw index SQL only on the production SQL Server backend."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "microsoft":
            super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "microsoft":
            super().database_backwards(app_label, schema_editor, from_state, to_state)


CREATE_OCCURRENCE_INFO_INDEX = """
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_CompletedOccurrencesInfo_OccurrenceID'
      AND object_id = OBJECT_ID('CompletedOccurrencesInfo')
)
BEGIN
    CREATE INDEX IX_CompletedOccurrencesInfo_OccurrenceID
        ON CompletedOccurrencesInfo ([OccurrenceID]);
END
"""

DROP_OCCURRENCE_INFO_INDEX = """
IF EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_CompletedOccurrencesInfo_OccurrenceID'
      AND object_id = OBJECT_ID('CompletedOccurrencesInfo')
)
BEGIN
    DROP INDEX IX_CompletedOccurrencesInfo_OccurrenceID
        ON CompletedOccurrencesInfo;
END
"""

CREATE_TRANSECT_INFO_INDEX = """
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_CompletedTransectsInfo_TransectUID'
      AND object_id = OBJECT_ID('CompletedTransectsInfo')
)
BEGIN
    CREATE INDEX IX_CompletedTransectsInfo_TransectUID
        ON CompletedTransectsInfo ([TransectUID]);
END
"""

DROP_TRANSECT_INFO_INDEX = """
IF EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_CompletedTransectsInfo_TransectUID'
      AND object_id = OBJECT_ID('CompletedTransectsInfo')
)
BEGIN
    DROP INDEX IX_CompletedTransectsInfo_TransectUID
        ON CompletedTransectsInfo;
END
"""


class Migration(migrations.Migration):
    dependencies = [("bones", "0029_completedresponse_relation_indexes")]
    operations = [
        RunSQLServer(CREATE_OCCURRENCE_INFO_INDEX, DROP_OCCURRENCE_INFO_INDEX),
        RunSQLServer(CREATE_TRANSECT_INFO_INDEX, DROP_TRANSECT_INFO_INDEX),
    ]

from django.db import migrations


class RunSQLServer(migrations.RunSQL):
    """Run raw index SQL only on the production SQL Server backend."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "microsoft":
            super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "microsoft":
            super().database_backwards(app_label, schema_editor, from_state, to_state)


def relation_index(name, table, column):
    create_sql = f"""
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = '{name}' AND object_id = OBJECT_ID('{table}')
)
BEGIN
    CREATE INDEX {name} ON {table} ([{column}]);
END
"""
    drop_sql = f"""
IF EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = '{name}' AND object_id = OBJECT_ID('{table}')
)
BEGIN
    DROP INDEX {name} ON {table};
END
"""
    return RunSQLServer(create_sql, drop_sql)


class Migration(migrations.Migration):
    dependencies = [("bones", "0030_completed_info_relation_indexes")]
    operations = [
        relation_index(
            "IX_CompletedResponses_QuestionID",
            "CompletedResponses",
            "QuestionID",
        ),
        relation_index(
            "IX_xTransectDataLog_DataLogFileID",
            "xTransectDataLog",
            "DataLogFileID",
        ),
        relation_index(
            "IX_xTransectDataLog_TransectID",
            "xTransectDataLog",
            "TransectID",
        ),
    ]

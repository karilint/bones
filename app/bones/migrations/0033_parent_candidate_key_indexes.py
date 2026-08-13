from django.db import migrations


class RunSQLServer(migrations.RunSQL):
    """Run raw candidate-key SQL only on SQL Server."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "microsoft":
            super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "microsoft":
            super().database_backwards(app_label, schema_editor, from_state, to_state)


def unique_index(name, table, column):
    create_sql = f"""
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = '{name}' AND object_id = OBJECT_ID('{table}')
)
BEGIN
    IF EXISTS (SELECT 1 FROM [{table}] WHERE [{column}] IS NULL)
        THROW 51000, '{table}.{column} contains NULL values', 1;
    IF EXISTS (
        SELECT [{column}] FROM [{table}]
        GROUP BY [{column}] HAVING COUNT_BIG(*) > 1
    )
        THROW 51000, '{table}.{column} contains duplicate values', 1;
    CREATE UNIQUE NONCLUSTERED INDEX [{name}]
        ON [{table}] ([{column}]);
END
"""
    drop_sql = f"""
IF EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = '{name}' AND object_id = OBJECT_ID('{table}')
)
BEGIN
    DROP INDEX [{name}] ON [{table}];
END
"""
    return RunSQLServer(create_sql, drop_sql)


class Migration(migrations.Migration):
    dependencies = [("bones", "0031_remaining_relation_indexes")]
    operations = [
        unique_index("UX_TemplateTransects_ID", "TemplateTransects", "ID"),
        unique_index("UX_CompletedTransects_UID", "CompletedTransects", "UID"),
        unique_index("UX_CompletedOccurrences_ID", "CompletedOccurrences", "ID"),
        unique_index("UX_TemplateWorkflows_ID", "TemplateWorkflows", "ID"),
        unique_index("UX_CompletedWorkflows_UID", "CompletedWorkflows", "UID"),
        unique_index("UX_Questions_ID", "Questions", "ID"),
        unique_index("UX_DataTypes_ID", "DataTypes", "ID"),
        unique_index("UX_DataLogFiles_ID", "DataLogFiles", "ID"),
    ]

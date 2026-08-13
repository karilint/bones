from django.db import migrations


class RunSQLServer(migrations.RunSQL):
    """Run raw relationship SQL only on SQL Server."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "microsoft":
            super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "microsoft":
            super().database_backwards(app_label, schema_editor, from_state, to_state)


def foreign_key(name, table, column, target_table, target_column):
    create_sql = f"""
IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = '{name}' AND parent_object_id = OBJECT_ID('{table}')
)
BEGIN
    ALTER TABLE [{table}] WITH CHECK
        ADD CONSTRAINT [{name}] FOREIGN KEY ([{column}])
        REFERENCES [{target_table}] ([{target_column}])
        ON DELETE NO ACTION ON UPDATE NO ACTION;
    ALTER TABLE [{table}] CHECK CONSTRAINT [{name}];
END
"""
    drop_sql = f"""
IF EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = '{name}' AND parent_object_id = OBJECT_ID('{table}')
)
BEGIN
    ALTER TABLE [{table}] DROP CONSTRAINT [{name}];
END
"""
    return RunSQLServer(create_sql, drop_sql)


class Migration(migrations.Migration):
    dependencies = [("bones", "0033_parent_candidate_key_indexes")]
    operations = [
        foreign_key(
            "FK_CompletedTransects_Template",
            "CompletedTransects",
            "TransectTemplateID",
            "TemplateTransects",
            "ID",
        ),
        foreign_key(
            "FK_TransectInfo_Transect",
            "CompletedTransectsInfo",
            "TransectUID",
            "CompletedTransects",
            "UID",
        ),
        foreign_key(
            "FK_TransectTrack_Transect",
            "CompletedTransectsTrack",
            "CompletedTransectUID",
            "CompletedTransects",
            "UID",
        ),
        foreign_key(
            "FK_Occurrences_Transect",
            "CompletedOccurrences",
            "TransectUID",
            "CompletedTransects",
            "UID",
        ),
    ]

from django.db import migrations


CREATE_TEMPLATE_START = """
IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_CompletedTransects_Template_StartTime'
      AND object_id = OBJECT_ID('CompletedTransects')
)
BEGIN
    CREATE INDEX IX_CompletedTransects_Template_StartTime
        ON CompletedTransects ([TransectTemplateID] ASC, [start_time] DESC);
END
"""

DROP_TEMPLATE_START = """
IF EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_CompletedTransects_Template_StartTime'
      AND object_id = OBJECT_ID('CompletedTransects')
)
BEGIN
    DROP INDEX IX_CompletedTransects_Template_StartTime ON CompletedTransects;
END
"""

CREATE_STATE = """
IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_CompletedTransects_State'
      AND object_id = OBJECT_ID('CompletedTransects')
)
BEGIN
    CREATE INDEX IX_CompletedTransects_State
        ON CompletedTransects ([state]);
END
"""

DROP_STATE = """
IF EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_CompletedTransects_State'
      AND object_id = OBJECT_ID('CompletedTransects')
)
BEGIN
    DROP INDEX IX_CompletedTransects_State ON CompletedTransects;
END
"""

CREATE_END_TIME = """
IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_CompletedTransects_EndTime'
      AND object_id = OBJECT_ID('CompletedTransects')
)
BEGIN
    CREATE INDEX IX_CompletedTransects_EndTime
        ON CompletedTransects ([end_time] DESC);
END
"""

DROP_END_TIME = """
IF EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_CompletedTransects_EndTime'
      AND object_id = OBJECT_ID('CompletedTransects')
)
BEGIN
    DROP INDEX IX_CompletedTransects_EndTime ON CompletedTransects;
END
"""


class Migration(migrations.Migration):

    dependencies = [
        ("bones", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(CREATE_TEMPLATE_START, DROP_TEMPLATE_START),
        migrations.RunSQL(CREATE_STATE, DROP_STATE),
        migrations.RunSQL(CREATE_END_TIME, DROP_END_TIME),
    ]

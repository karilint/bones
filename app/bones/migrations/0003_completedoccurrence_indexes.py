from django.db import migrations


CREATE_TRANSECT_START = """
IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_CompletedOccurrences_Transect_StartTime'
      AND object_id = OBJECT_ID('CompletedOccurrences')
)
BEGIN
    CREATE INDEX IX_CompletedOccurrences_Transect_StartTime
        ON CompletedOccurrences ([TransectUID] ASC, [RecordingStartTime] DESC);
END
"""

DROP_TRANSECT_START = """
IF EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_CompletedOccurrences_Transect_StartTime'
      AND object_id = OBJECT_ID('CompletedOccurrences')
)
BEGIN
    DROP INDEX IX_CompletedOccurrences_Transect_StartTime ON CompletedOccurrences;
END
"""

CREATE_END_TIME = """
IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_CompletedOccurrences_EndTime'
      AND object_id = OBJECT_ID('CompletedOccurrences')
)
BEGIN
    CREATE INDEX IX_CompletedOccurrences_EndTime
        ON CompletedOccurrences ([RecordingEndTime] DESC);
END
"""

DROP_END_TIME = """
IF EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_CompletedOccurrences_EndTime'
      AND object_id = OBJECT_ID('CompletedOccurrences')
)
BEGIN
    DROP INDEX IX_CompletedOccurrences_EndTime ON CompletedOccurrences;
END
"""

CREATE_STATE = """
IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_CompletedOccurrences_State'
      AND object_id = OBJECT_ID('CompletedOccurrences')
)
BEGIN
    CREATE INDEX IX_CompletedOccurrences_State
        ON CompletedOccurrences ([State]);
END
"""

DROP_STATE = """
IF EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_CompletedOccurrences_State'
      AND object_id = OBJECT_ID('CompletedOccurrences')
)
BEGIN
    DROP INDEX IX_CompletedOccurrences_State ON CompletedOccurrences;
END
"""

CREATE_OCCURRENCE_NUMBER = """
IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_CompletedOccurrences_OccurrenceNumber'
      AND object_id = OBJECT_ID('CompletedOccurrences')
)
BEGIN
    CREATE INDEX IX_CompletedOccurrences_OccurrenceNumber
        ON CompletedOccurrences ([OccurrenceNumber]);
END
"""

DROP_OCCURRENCE_NUMBER = """
IF EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_CompletedOccurrences_OccurrenceNumber'
      AND object_id = OBJECT_ID('CompletedOccurrences')
)
BEGIN
    DROP INDEX IX_CompletedOccurrences_OccurrenceNumber ON CompletedOccurrences;
END
"""


class Migration(migrations.Migration):

    dependencies = [
        ("bones", "0002_completedtransect_indexes"),
    ]

    operations = [
        migrations.RunSQL(CREATE_TRANSECT_START, DROP_TRANSECT_START),
        migrations.RunSQL(CREATE_END_TIME, DROP_END_TIME),
        migrations.RunSQL(CREATE_STATE, DROP_STATE),
        migrations.RunSQL(CREATE_OCCURRENCE_NUMBER, DROP_OCCURRENCE_NUMBER),
    ]

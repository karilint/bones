from django.db import migrations


CREATE_TRACK_MAP_INDEX = """
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_CompletedTransectsTrack_Map'
      AND object_id = OBJECT_ID('CompletedTransectsTrack')
)
BEGIN
    CREATE INDEX IX_CompletedTransectsTrack_Map
        ON CompletedTransectsTrack ([CompletedTransectUID], [Time], [ID])
        INCLUDE ([Lat], [Long]);
END
"""

DROP_TRACK_MAP_INDEX = """
IF EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_CompletedTransectsTrack_Map'
      AND object_id = OBJECT_ID('CompletedTransectsTrack')
)
BEGIN
    DROP INDEX IX_CompletedTransectsTrack_Map ON CompletedTransectsTrack;
END
"""

CREATE_OCCURRENCE_MAP_INDEX = """
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_CompletedOccurrences_Transect_Occurrence_Map'
      AND object_id = OBJECT_ID('CompletedOccurrences')
)
BEGIN
    CREATE INDEX IX_CompletedOccurrences_Transect_Occurrence_Map
        ON CompletedOccurrences ([TransectUID], [OccurrenceNumber], [ID])
        INCLUDE ([Lat], [Long]);
END
"""

DROP_OCCURRENCE_MAP_INDEX = """
IF EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_CompletedOccurrences_Transect_Occurrence_Map'
      AND object_id = OBJECT_ID('CompletedOccurrences')
)
BEGIN
    DROP INDEX IX_CompletedOccurrences_Transect_Occurrence_Map
        ON CompletedOccurrences;
END
"""


class Migration(migrations.Migration):
    dependencies = [("bones", "0019_correct_completed_response_key")]

    operations = [
        migrations.RunSQL(CREATE_TRACK_MAP_INDEX, DROP_TRACK_MAP_INDEX),
        migrations.RunSQL(CREATE_OCCURRENCE_MAP_INDEX, DROP_OCCURRENCE_MAP_INDEX),
    ]
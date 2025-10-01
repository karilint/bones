from django.db import migrations


CREATE_UPLOAD_DATE_INDEX = """
IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_DataLogFiles_UploadDate'
      AND object_id = OBJECT_ID('DataLogFiles')
)
BEGIN
    CREATE INDEX IX_DataLogFiles_UploadDate
        ON DataLogFiles ([UploadDate] DESC);
END
"""

DROP_UPLOAD_DATE_INDEX = """
IF EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_DataLogFiles_UploadDate'
      AND object_id = OBJECT_ID('DataLogFiles')
)
BEGIN
    DROP INDEX IX_DataLogFiles_UploadDate ON DataLogFiles;
END
"""


class Migration(migrations.Migration):

    dependencies = [
        ("bones", "0007_projectconfig_publish_date_index"),
    ]

    operations = [
        migrations.RunSQL(CREATE_UPLOAD_DATE_INDEX, DROP_UPLOAD_DATE_INDEX),
    ]

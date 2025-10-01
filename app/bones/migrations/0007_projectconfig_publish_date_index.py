from django.db import migrations


CREATE_PUBLISH_DATE_INDEX = """
IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_ProjectConfigs_PublishDate'
      AND object_id = OBJECT_ID('ProjectConfigs')
)
BEGIN
    CREATE INDEX IX_ProjectConfigs_PublishDate
        ON ProjectConfigs ([PublishDate] DESC);
END
"""

DROP_PUBLISH_DATE_INDEX = """
IF EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_ProjectConfigs_PublishDate'
      AND object_id = OBJECT_ID('ProjectConfigs')
)
BEGIN
    DROP INDEX IX_ProjectConfigs_PublishDate ON ProjectConfigs;
END
"""


class Migration(migrations.Migration):

    dependencies = [
        ("bones", "0006_question_indexes"),
    ]

    operations = [
        migrations.RunSQL(CREATE_PUBLISH_DATE_INDEX, DROP_PUBLISH_DATE_INDEX),
    ]

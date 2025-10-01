"""Add indexes that support question list ordering and select2 filters."""

from django.db import migrations


CREATE_WORKFLOW_ID = """
IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_Questions_WorkflowID'
      AND object_id = OBJECT_ID('Questions')
)
BEGIN
    CREATE INDEX IX_Questions_WorkflowID
        ON Questions ([WorkflowID]);
END
"""


DROP_WORKFLOW_ID = """
IF EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_Questions_WorkflowID'
      AND object_id = OBJECT_ID('Questions')
)
BEGIN
    DROP INDEX IX_Questions_WorkflowID ON Questions;
END
"""


CREATE_DATA_TYPE_ID = """
IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_Questions_DataTypeID'
      AND object_id = OBJECT_ID('Questions')
)
BEGIN
    CREATE INDEX IX_Questions_DataTypeID
        ON Questions ([DataTypeID]);
END
"""


DROP_DATA_TYPE_ID = """
IF EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_Questions_DataTypeID'
      AND object_id = OBJECT_ID('Questions')
)
BEGIN
    DROP INDEX IX_Questions_DataTypeID ON Questions;
END
"""


CREATE_PROMPT = """
IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_Questions_Prompt'
      AND object_id = OBJECT_ID('Questions')
)
BEGIN
    CREATE INDEX IX_Questions_Prompt
        ON Questions ([Prompt] ASC);
END
"""


DROP_PROMPT = """
IF EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_Questions_Prompt'
      AND object_id = OBJECT_ID('Questions')
)
BEGIN
    DROP INDEX IX_Questions_Prompt ON Questions;
END
"""


class Migration(migrations.Migration):

    dependencies = [
        ("bones", "0005_templatetransect_indexes"),
    ]

    operations = [
        migrations.RunSQL(CREATE_WORKFLOW_ID, DROP_WORKFLOW_ID),
        migrations.RunSQL(CREATE_DATA_TYPE_ID, DROP_DATA_TYPE_ID),
        migrations.RunSQL(CREATE_PROMPT, DROP_PROMPT),
    ]


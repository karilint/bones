from django.db import migrations
from django.utils import timezone


BASELINE_MODELS = (
    ("EntityImage", "HistoricalEntityImage"),
    ("ImageImportBatch", "HistoricalImageImportBatch"),
    ("TemplateTransect", "HistoricalTemplateTransect"),
    ("TemplateWorkflow", "HistoricalTemplateWorkflow"),
    ("DataType", "HistoricalDataType"),
    ("DataTypeOption", "HistoricalDataTypeOption"),
    ("ProjectConfig", "HistoricalProjectConfig"),
    ("DataLogFile", "HistoricalDataLogFile"),
    ("TransectDataLog", "HistoricalTransectDataLog"),
)


def create_baselines(apps, schema_editor):
    database = schema_editor.connection.alias
    recorded_at = timezone.now()
    for source_name, history_name in BASELINE_MODELS:
        source_model = apps.get_model("bones", source_name)
        history_model = apps.get_model("bones", history_name)
        history_fields = {
            field.attname: field
            for field in history_model._meta.concrete_fields
            if not field.name.startswith("history_") and field.name != "history_id"
        }
        rows = []
        for source in source_model.objects.using(database).all().iterator(chunk_size=500):
            values = {}
            for field in source_model._meta.concrete_fields:
                if field.attname not in history_fields:
                    continue
                value = getattr(source, field.attname)
                if field.get_internal_type() in {"FileField", "ImageField"}:
                    value = str(value)
                values[field.attname] = value
            rows.append(history_model(**values, history_date=recorded_at, history_type="+", history_change_reason="Baseline snapshot when audit history was enabled"))
            if len(rows) >= 500:
                history_model.objects.using(database).bulk_create(rows, batch_size=500)
                rows = []
        if rows:
            history_model.objects.using(database).bulk_create(rows, batch_size=500)


class Migration(migrations.Migration):
    dependencies = [("bones", "0013_audit_remaining_models")]
    operations = [migrations.RunPython(create_baselines, migrations.RunPython.noop)]
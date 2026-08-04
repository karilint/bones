from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("bones", "0027_occurrence_info_import_batch")]
    operations = [
        migrations.AlterModelOptions(
            name="datalogfile",
            options={
                "managed": False,
                "permissions": (("run_data_reconciliation_report", "Can run data reconciliation reports"),),
                "verbose_name": "Data log file",
                "verbose_name_plural": "Data log files",
            },
        ),
    ]

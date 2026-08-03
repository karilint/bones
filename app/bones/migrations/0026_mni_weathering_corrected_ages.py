from django.db import migrations, models


def populate_corrected_ages(apps, schema_editor):
    from bones.mni_seed import WEATHERING_CORRECTED_RANGES

    Rule = apps.get_model("bones", "MNIWeatheringRule")
    for source_class, (age_min, age_max) in WEATHERING_CORRECTED_RANGES.items():
        Rule.objects.filter(source_class=source_class).update(
            age_min_corrected=age_min,
            age_max_corrected=age_max,
        )


class Migration(migrations.Migration):
    dependencies = [("bones", "0025_mni_weathering_rules")]
    operations = [
        migrations.AddField(
            model_name="mniweatheringrule",
            name="age_min_corrected",
            field=models.DecimalField(decimal_places=1, max_digits=4, null=True),
        ),
        migrations.AddField(
            model_name="mniweatheringrule",
            name="age_max_corrected",
            field=models.DecimalField(decimal_places=1, max_digits=4, null=True),
        ),
        migrations.RunPython(populate_corrected_ages, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="mniweatheringrule",
            name="age_min_corrected",
            field=models.DecimalField(decimal_places=1, max_digits=4),
        ),
        migrations.AlterField(
            model_name="mniweatheringrule",
            name="age_max_corrected",
            field=models.DecimalField(decimal_places=1, max_digits=4),
        ),
    ]

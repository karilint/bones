from django.db import migrations, models


def seed_rules(apps, schema_editor):
    from bones.mni_seed import WEATHERING_RULES

    Rule = apps.get_model("bones", "MNIWeatheringRule")
    Rule.objects.bulk_create([
        Rule(
            source_class=source,
            canonical_class=canonical,
            age_min=age_min,
            age_max=age_max,
            reviewed=True,
            notes="Seeded from Weathering class.xlsx.",
        )
        for source, canonical, age_min, age_max in WEATHERING_RULES
    ])


def unseed_rules(apps, schema_editor):
    apps.get_model("bones", "MNIWeatheringRule").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("bones", "0024_occurrencedeletion_historicaloccurrencedeletion_and_more")]
    operations = [
        migrations.CreateModel(
            name="MNIWeatheringRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_class", models.CharField(max_length=20, unique=True)),
                ("canonical_class", models.CharField(max_length=20)),
                ("age_min", models.DecimalField(decimal_places=1, max_digits=4)),
                ("age_max", models.DecimalField(decimal_places=1, max_digits=4)),
                ("active", models.BooleanField(default=True)),
                ("reviewed", models.BooleanField(default=True)),
                ("notes", models.CharField(blank=True, max_length=500)),
            ],
            options={
                "ordering": ("source_class",),
                "verbose_name": "MNI weathering rule",
                "verbose_name_plural": "MNI weathering rules",
            },
        ),
        migrations.RunPython(seed_rules, unseed_rules),
    ]

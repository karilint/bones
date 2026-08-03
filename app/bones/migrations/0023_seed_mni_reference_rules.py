from django.db import migrations


def seed_rules(apps, schema_editor):
    from bones.mni_seed import DEFAULT_EXCLUDED_TAXA, ELEMENT_RULES, TAXON_RULES, UNPAIRED_ELEMENTS
    ElementRule = apps.get_model("bones", "MNIElementRule")
    TaxonRule = apps.get_model("bones", "MNITaxonRule")
    ElementRule.objects.bulk_create([
        ElementRule(canonical_name=name, display_name=name, divisor=divisor,
                    paired=name not in UNPAIRED_ELEMENTS, reviewed=True,
                    notes="Seeded from Element counts.xlsx; paired flag requires scientific review.")
        for name, divisor in ELEMENT_RULES
    ])
    TaxonRule.objects.bulk_create([
        TaxonRule(source_alias=alias, canonical_label=canonical,
                  default_excluded=(alias.casefold() in DEFAULT_EXCLUDED_TAXA or
                                    canonical.casefold() in DEFAULT_EXCLUDED_TAXA),
                  notes="Seeded from Taxa_lookup.xlsx.")
        for alias, canonical in TAXON_RULES
    ])


def unseed_rules(apps, schema_editor):
    apps.get_model("bones", "MNIElementRule").objects.all().delete()
    apps.get_model("bones", "MNITaxonRule").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("bones", "0022_mni_reference_rules")]
    operations = [migrations.RunPython(seed_rules, unseed_rules)]

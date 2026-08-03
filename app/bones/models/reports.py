"""Application-managed reference data used by analytical reports."""
from django.core.validators import MinValueValidator
from django.db import models


class MNIElementRule(models.Model):
    canonical_name = models.CharField(max_length=120, unique=True)
    display_name = models.CharField(max_length=120)
    divisor = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    paired = models.BooleanField(default=False)
    excluded = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    reviewed = models.BooleanField(default=True)
    notes = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("canonical_name",)
        verbose_name = "MNI element rule"
        verbose_name_plural = "MNI element rules"

    def __str__(self):
        return self.display_name


class MNITaxonRule(models.Model):
    source_alias = models.CharField(max_length=120, unique=True)
    canonical_label = models.CharField(max_length=120)
    default_excluded = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    notes = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("canonical_label", "source_alias")
        verbose_name = "MNI taxon rule"
        verbose_name_plural = "MNI taxon rules"

    def __str__(self):
        return f"{self.source_alias} -> {self.canonical_label}"


class MNIWeatheringRule(models.Model):
    source_class = models.CharField(max_length=20, unique=True)
    canonical_class = models.CharField(max_length=20)
    age_min = models.DecimalField(max_digits=4, decimal_places=1)
    age_max = models.DecimalField(max_digits=4, decimal_places=1)
    age_min_corrected = models.DecimalField(max_digits=4, decimal_places=1)
    age_max_corrected = models.DecimalField(max_digits=4, decimal_places=1)
    active = models.BooleanField(default=True)
    reviewed = models.BooleanField(default=True)
    notes = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("source_class",)
        verbose_name = "MNI weathering rule"
        verbose_name_plural = "MNI weathering rules"

    def __str__(self):
        return f"{self.source_class} -> {self.canonical_class}"

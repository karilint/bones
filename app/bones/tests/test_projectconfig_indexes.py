from __future__ import annotations

from datetime import timedelta
from unittest import SkipTest

from django.db import connection
from django.test import TestCase
from django.utils import timezone

from bones.models import ProjectConfig


class ProjectConfigIndexTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        if connection.vendor != "sqlite":
            raise SkipTest("Query plan assertions rely on SQLite EXPLAIN output.")

        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ProjectConfigs (
                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    PublishDate DATETIME NOT NULL,
                    Project VARCHAR(50) NOT NULL,
                    ConfigFolder VARCHAR(100) NOT NULL,
                    ConfigFile TEXT NOT NULL,
                    Image TEXT NULL,
                    transectsFile TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS IX_ProjectConfigs_PublishDate
                ON ProjectConfigs (PublishDate DESC)
                """
            )

    @classmethod
    def tearDownClass(cls) -> None:
        if connection.vendor == "sqlite":
            with connection.cursor() as cursor:
                cursor.execute("DROP TABLE IF EXISTS ProjectConfigs")
        super().tearDownClass()

    def setUp(self) -> None:
        ProjectConfig.objects.all().delete()

    def test_list_ordering_uses_publish_date_index(self) -> None:
        """Project config list queries should leverage the PublishDate index."""

        base_time = timezone.now()
        ProjectConfig.objects.bulk_create(
            [
                ProjectConfig(
                    publish_date=base_time - timedelta(days=offset),
                    project=f"Project {offset}",
                    config_folder="folder",
                    config_file="config",
                    transects_file="transects",
                )
                for offset in range(5)
            ]
        )

        query_plan = ProjectConfig.objects.order_by("-publish_date").explain()

        self.assertIn("USING COVERING INDEX IX_ProjectConfigs_PublishDate", query_plan)

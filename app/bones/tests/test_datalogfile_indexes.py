from __future__ import annotations

from datetime import timedelta
from unittest import SkipTest

from django.db import connection
from django.test import TestCase
from django.utils import timezone

from bones.models import DataLogFile


class DataLogFileIndexTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        if connection.vendor != "sqlite":
            raise SkipTest("Query plan assertions rely on SQLite EXPLAIN output.")

        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS DataLogFiles (
                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    UploadDate DATETIME NULL,
                    UploadedBy VARCHAR(100) NULL,
                    Contents TEXT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS IX_DataLogFiles_UploadDate
                ON DataLogFiles (UploadDate DESC)
                """
            )

    @classmethod
    def tearDownClass(cls) -> None:
        if connection.vendor == "sqlite":
            with connection.cursor() as cursor:
                cursor.execute("DROP TABLE IF EXISTS DataLogFiles")
        super().tearDownClass()

    def setUp(self) -> None:
        DataLogFile.objects.all().delete()

    def _create_logs(self) -> None:
        base_time = timezone.now()
        DataLogFile.objects.bulk_create(
            [
                DataLogFile(
                    upload_date=base_time - timedelta(days=offset),
                    uploaded_by=f"user-{offset}",
                    contents="data",
                )
                for offset in range(5)
            ]
        )

    def test_list_ordering_uses_upload_date_index(self) -> None:
        """Data log list queries should leverage the UploadDate index."""

        self._create_logs()

        query_plan = DataLogFile.objects.order_by("-upload_date").explain()

        self.assertIn("USING INDEX IX_DataLogFiles_UploadDate", query_plan)

    def test_upload_date_filters_use_index(self) -> None:
        """Date filters should use the UploadDate index for efficient lookups."""

        self._create_logs()
        base_time = DataLogFile.objects.order_by("upload_date").first().upload_date
        assert base_time is not None

        newer_plan = (
            DataLogFile.objects.filter(upload_date__gte=base_time)
            .order_by("-upload_date")
            .explain()
        )
        older_plan = (
            DataLogFile.objects.filter(upload_date__lte=base_time)
            .order_by("-upload_date")
            .explain()
        )

        self.assertIn("USING INDEX IX_DataLogFiles_UploadDate", newer_plan)
        self.assertIn("USING INDEX IX_DataLogFiles_UploadDate", older_plan)

import json
import tempfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse
from openpyxl import load_workbook

from ..forms_reports import DataReconciliationReportForm
from ..navigation import navigation_context
from ..reports.data_log_reconciliation import SHEETS, gps_status, parse_log, summary_rows, workbook_bytes, write_workbook
from ..views.reports import DataReconciliationReportView


class DataLogParserTests(SimpleTestCase):
    def test_nested_json_entities_are_normalized(self):
        payload = {
            "transects": [{
                "TransectUID": 17, "Name": "T-17", "StartTime": "2025-06-01T10:00:00Z",
                "occurrences": [{
                    "OccurrenceID": 91, "OccurrenceNumber": 2, "TransectUID": 17,
                    "workflows": [{"CompletedWorkflowID": "wf-1", "InstanceNumber": 3, "OccurrenceID": 91}],
                }],
                "track": [{"CompletedTransectUID": 17, "Time": "2025-06-01T10:01:00Z", "Lat": 60.1, "Long": 24.9, "isStart": True}],
            }]
        }
        result = parse_log(4, json.dumps(payload))
        self.assertEqual(result.error, "")
        self.assertEqual(result.transects[0]["uid"], 17)
        self.assertEqual(result.occurrences[0]["number"], 2)
        self.assertEqual(result.instances[0]["number"], 3)
        self.assertEqual(len(result.track_points), 1)

    def test_xml_and_malformed_logs_are_reported(self):
        xml = "<Log><Transect><TransectUID>7</TransectUID><Name>A</Name><StartTime>2024-01-01</StartTime></Transect></Log>"
        self.assertEqual(parse_log(1, xml).transects[0]["uid"], 7)
        self.assertTrue(parse_log(2, "not structured data").error)
        self.assertTrue(parse_log(3, "").error)

    def test_bones_line_log_entities_and_cancellations_are_normalized(self):
        payload = "\n".join([
            "STARTTRANSECT template-guid 4354068 2.4,-1.4 17-Feb-2003 16:50:58 1",
            "/STARTTRANSECT primary 2.4,-1.4 User",
            "STARTOCCURRENCE 1 2.4,-1.4 17-Feb-2003 16:54:40",
            "/STARTOCCURRENCE primary User",
            "STARTWORKFLOW workflow-template workflow-uid 3 Bone",
            "CHECKPOINT 2.4,-1.4 17-Feb-2003 16:55:00",
            "CANCELOCCURRENCE 17-Feb-2003 16:56:00",
            "CANCELTRANSECT 17-Feb-2003 16:57:00",
        ])
        result = parse_log(9, payload)
        self.assertEqual(result.format, "Bones line log")
        self.assertEqual(result.transects[0]["uid"], 4354068)
        self.assertEqual(result.transects[0]["state"], "cancelled")
        self.assertEqual(result.occurrences[0]["number"], 1)
        self.assertEqual(result.occurrences[0]["state"], "cancelled")
        self.assertEqual(result.instances[0]["workflow_uid"], "workflow-uid")
        self.assertEqual(result.instances[0]["number"], 3)
        self.assertEqual(len(result.track_points), 1)
        self.assertEqual(result.track_points[0]["event"], "CHECKPOINT")
        self.assertEqual(result.track_points[0]["lat"], 2.4)
        self.assertEqual(result.track_points[0]["long"], -1.4)
        self.assertEqual(result.track_points[0]["user"], "User")
        self.assertEqual(result.instances[0]["response_count"], 0)

    def test_gps_expectation_is_explicit(self):
        self.assertEqual(gps_status(2001, 0, 0, 2010), "GPS_NOT_EXPECTED_EARLY_MANUAL")
        self.assertEqual(gps_status(2020, 0, 0, 2010), "GPS_MISSING")
        self.assertEqual(gps_status(2020, 1, 0, 2010), "GPS_PRESENT")
        self.assertEqual(gps_status(2020, 0, 0, None), "GPS_EXPECTATION_UNKNOWN")


class ReconciliationWorkbookTests(SimpleTestCase):
    def test_summary_counts_status_columns_not_identifiers(self):
        rows = {
            "Transects": [[1, 17, None, "T", 2025, "MISSING"]],
            "Occurrences": [[1, 17, None, 2, None, "DELETED_CONFIRMED"]],
            "Instances": [[1, 17, None, 2, 3, "", [], "HISTORICAL_ONLY"]],
        }
        summary = dict(summary_rows(rows))
        self.assertEqual(summary["Status: MISSING"], 1)
        self.assertEqual(summary["Status: DELETED_CONFIRMED"], 1)
        self.assertEqual(summary["Status: HISTORICAL_ONLY"], 1)

    def test_workbook_has_review_sheets_and_headers(self):
        with tempfile.TemporaryDirectory() as folder:
            target = write_workbook(Path(folder) / "report.xlsx", {"Summary": [["Logs", 2]]})
            workbook = load_workbook(target, read_only=True)
            self.assertEqual(workbook.sheetnames, list(SHEETS))
            self.assertEqual(workbook["Summary"]["A1"].value, "Metric")
            self.assertEqual(workbook["Summary"]["A2"].value, "Logs")
            workbook.close()

    def test_workbook_can_omit_unselected_sheets_but_keeps_summary(self):
        workbook = load_workbook(BytesIO(workbook_bytes({}, ["GPS"])), read_only=True)
        self.assertEqual(workbook.sheetnames, ["Summary", "GPS"])
        workbook.close()


class ReconciliationReportUITests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_defaults_are_exception_focused(self):
        form = DataReconciliationReportForm()
        statuses = set(form.fields["statuses"].initial)
        self.assertIn("MISSING", statuses)
        self.assertNotIn("CURRENT_EXACT", statuses)
        self.assertNotIn("LOG_CANCELLED", statuses)
        self.assertNotIn("GPS_PRESENT", statuses)
        recovery = set(form.fields["recovery_statuses"].initial)
        self.assertIn("READY_FOR_IMPORT", recovery)
        self.assertNotIn("INTENTIONALLY_DELETED", recovery)
        self.assertNotIn("CANCELLED_IN_LOG", dict(form.fields["recovery_statuses"].choices))

    def test_year_range_must_be_chronological(self):
        form = DataReconciliationReportForm(data={
            "from_year": 2025, "to_year": 2020,
            "contents": ["Critical findings"], "statuses": ["MISSING"],
        })
        self.assertFalse(form.is_valid())
        self.assertIn("to_year", form.errors)

    def test_view_uses_dedicated_permission(self):
        self.assertEqual(
            DataReconciliationReportView.permission_required,
            "bones.run_data_reconciliation_report",
        )

    def test_route_and_reports_navigation_are_available(self):
        url = reverse("bones:reports:data_reconciliation")
        self.assertEqual(url, "/reports/data-reconciliation/")
        reports = next(section for section in navigation_context(None)["navigation_sections"] if section["label"] == "Reports")
        link = next(child for child in reports["children"] if child["label"] == "Data Reconciliation")
        self.assertEqual(link["url"], url)

    def test_template_is_semantic_responsive_and_accessible(self):
        template = (Path(__file__).resolve().parents[1] / "templates" / "bones" / "reports" / "data_reconciliation.html").read_text(encoding="utf-8")
        self.assertIn("<header", template)
        self.assertIn("<section", template)
        self.assertIn("w3-row-padding", template)
        self.assertIn('aria-label="Data reconciliation report filters"', template)
        self.assertIn("fa-file-excel", template)

    @patch("bones.views.reports.workbook_bytes", return_value=b"xlsx")
    @patch("bones.views.reports.collect_reconciliation_rows")
    @patch("bones.views.reports.DataReconciliationReportForm")
    def test_valid_export_returns_timestamped_workbook(self, form_class, collect_rows, build_workbook):
        form = MagicMock()
        form.is_valid.return_value = True
        form.cleaned_data = {
            "from_year": None, "to_year": None, "logs": [],
            "gps_required_from_year": None, "statuses": ["MISSING"],
            "recovery_statuses": ["READY_FOR_IMPORT"],
            "contents": ["Critical findings", "Methodology"],
        }
        form_class.return_value = form
        collect_rows.return_value = ({name: [] for name in SHEETS}, 37)
        request = self.factory.get("/reports/data-reconciliation/", {"export": "xlsx"})
        request.user = SimpleNamespace(
            is_authenticated=True, has_perms=lambda permissions: True,
            get_full_name=lambda: "Report User", get_username=lambda: "report-user",
        )
        response = DataReconciliationReportView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"xlsx")
        self.assertIn("data-reconciliation-", response["Content-Disposition"])
        build_workbook.assert_called_once()

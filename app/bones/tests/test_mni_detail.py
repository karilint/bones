from types import SimpleNamespace
from unittest.mock import patch

from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from ..mni_seed import DEFAULT_EXCLUDED_TAXA
from ..reports.mni import GroupMNI, Observation, ReportResult
from ..reports.mni_detail import build_mni_detail, empty_mni_detail
from ..views.instance import CompletedInstanceDetailView


class MNIDetailPresentationTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("bones.reports.mni_detail.MNIElementRule.objects")
    @patch("bones.reports.mni_detail.build_report")
    def test_occurrence_scope_keeps_transect_mni_and_filters_evidence(
        self, build_report, rule_objects
    ):
        observations = [
            Observation(10, 20, 1, "Taxon A", "F", "Adult", "1-2", "femur", "left", True),
            Observation(10, 21, 2, "Taxon A", "F", "Adult", "1-2", "femur", "right", True),
        ]
        result = ReportResult(
            [], [], [{"transect_id": 10, "taxon": "Taxon A", "mni": 1}],
            [GroupMNI(10, "Taxon A", "F", "Adult", "1-2", 1)],
            [], observations, observations,
        )
        build_report.return_value = (result, [SimpleNamespace(pk=10)], [])
        rule_objects.all.return_value = [
            SimpleNamespace(canonical_name="femur", divisor=1, paired=True,
                            excluded=False, active=True, reviewed=True)
        ]

        detail = build_mni_detail(10, occurrence_id=20)

        build_report.assert_called_once_with(
            {"transects": [10], "excluded_taxa": list(DEFAULT_EXCLUDED_TAXA)},
            apply_population_rules=False,
        )
        self.assertEqual(detail["total_mni"], 1)
        self.assertEqual(detail["contributing_instance_count"], 1)
        self.assertEqual([row["occurrence_id"] for row in detail["evidence_rows"]], [20])
        self.assertEqual(detail["evidence_rows"][0]["status"], "Included")

    def test_empty_state_is_safe_and_explicit(self):
        detail = empty_mni_detail("MNI is temporarily unavailable.")
        self.assertFalse(detail["available"])
        self.assertEqual(detail["message"], "MNI is temporarily unavailable.")

    def test_shared_template_renders_accessible_table_and_method_note(self):
        html = render_to_string("bones/completed_instances/_mni.html", {
            "mni_detail": {
                **empty_mni_detail(), "available": True,
                "evidence_rows": [{
                    "instance_url": "/instances/1/", "instance_number": 1,
                    "taxon": "Taxon A", "element": "femur", "side": "left",
                    "complete": True, "sex": "F", "age": "Adult",
                    "weathering": "1-2", "divisor": 1, "paired": True,
                    "status": "Included", "reason": "Included in calculation",
                }],
            }
        })
        self.assertIn("MNI evidence", html)
        self.assertIn("<caption", html)
        self.assertIn("complete transect", html)

    @patch("bones.views.instance.image_context", return_value={})
    @patch("bones.views.instance.build_mni_detail", return_value={})
    def test_instance_view_registers_mni_evidence_tab(self, _build, _images):
        view = CompletedInstanceDetailView()
        view.setup(
            self.factory.get("/occurrences/20/instances/1/"),
            occurrence_pk=20, instance_number=1,
        )
        view.request.user = SimpleNamespace()
        view.occurrence = SimpleNamespace(pk=20, transect_id=10)
        view.workflows = []

        context = view.get_context_data()

        mni_tab = next(tab for tab in context["tabs"] if tab["id"] == "mni")
        self.assertEqual(mni_tab["label"], "MNI evidence")

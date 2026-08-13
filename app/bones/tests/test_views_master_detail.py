from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.template.loader import render_to_string
from django.core.paginator import Paginator
from django.test import RequestFactory, SimpleTestCase

from ..models import CompletedOccurrence
from ..views.master_detail import (
    BonesMasterDetailView,
    CompletedOccurrenceDetailView,
    CompletedTransectDetailView,
)


class MasterDetailViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_base_breadcrumbs_include_dashboard(self):
        class DummyMasterDetail(BonesMasterDetailView):
            template_name = "bones/completed_transect_detail.html"

        view = DummyMasterDetail()
        request = self.factory.get("/dummy/1/")
        view.setup(request, pk=1)
        view.object = SimpleNamespace(pk=1)
        breadcrumbs = view.get_breadcrumbs()
        self.assertEqual(breadcrumbs[0]["label"], "Dashboard")

    def test_completed_transect_tabs_include_history(self):
        view = CompletedTransectDetailView()
        request = self.factory.get("/transects/1/")
        view.setup(request, pk=1)
        view.object = SimpleNamespace(pk=1, history=SimpleNamespace(all=lambda: []))
        tabs = list(view.get_tabs())
        tab_ids = [tab["id"] for tab in tabs]
        self.assertIn("history", tab_ids)
        self.assertIn("mni", tab_ids)
        self.assertIn("images", tab_ids)
        self.assertIn("map", tab_ids)
        self.assertEqual(
            next(tab["label"] for tab in tabs if tab["id"] == "related"),
            "Occurrences",
        )

    def test_completed_transect_occurrences_include_taxon_values(self):
        class DummyManager:
            def __init__(self, items):
                self._items = items

            def all(self):
                return self._items

        occurrence = SimpleNamespace(
            pk=7,
            occurrence_number=3,
            state="Complete",
            recording_start_time=None,
            recording_end_time=None,
            responses=[],
            workflows=[],
            element_responses=[
                SimpleNamespace(
                    response="Femur", workflow=SimpleNamespace(instance_number=1)
                ),
                SimpleNamespace(
                    response="Tibia", workflow=SimpleNamespace(instance_number=2)
                ),
            ],
            dentition_workflows=[SimpleNamespace(instance_number=3)],
            details=DummyManager(
                [
                    SimpleNamespace(
                        pre_or_post="Pre", question_text="Taxon", response="Bird"
                    ),
                    SimpleNamespace(
                        pre_or_post="Post",
                        question_text="Taxon Guess?",
                        response="Robin",
                    ),
                ]
            ),
        )
        view = CompletedTransectDetailView()
        view.object = SimpleNamespace(occurrences=DummyManager([occurrence]))

        headers, rows = view.get_occurrence_table()

        self.assertEqual(
            [header["label"] for header in headers][1:3],
            ["Taxon", "Taxon Guess"],
        )
        self.assertEqual(
            [cell["value"] for cell in rows[0]][1:3], ["Bird", "Robin"]
        )
        labels = [header["label"] for header in headers]
        self.assertEqual(
            rows[0][labels.index("Elements")]["value"],
            "(1) Femur, (2) Tibia, (3) tooth",
        )

    def test_dentition_does_not_replace_an_explicit_element(self):
        occurrence = SimpleNamespace(
            element_responses=[
                SimpleNamespace(
                    response="Molar", workflow=SimpleNamespace(instance_number=3)
                )
            ],
            dentition_workflows=[SimpleNamespace(instance_number=3)],
        )

        self.assertEqual(
            CompletedTransectDetailView._occurrence_elements(occurrence), "(3) Molar"
        )
    def test_completed_transect_occurrence_counts_use_annotations(self):
        class UnexpectedRelationAccess:
            def all(self):
                raise AssertionError("Nested relation should not be loaded for a count")

        occurrence = SimpleNamespace(
            pk=7,
            occurrence_number=3,
            state="Complete",
            recording_start_time=None,
            recording_end_time=None,
            response_count=12,
            workflow_count=4,
            responses=UnexpectedRelationAccess(),
            workflows=UnexpectedRelationAccess(),
            details=[],
        )
        view = CompletedTransectDetailView()
        view.object = SimpleNamespace(
            occurrences=SimpleNamespace(all=lambda: [occurrence])
        )

        headers, rows = view.get_occurrence_table()

        labels = [header["label"] for header in headers]
        self.assertEqual(rows[0][labels.index("Responses")]["value"], 12)
        self.assertEqual(rows[0][labels.index("Workflows")]["value"], 4)

    def test_related_counts_use_independent_correlated_subqueries(self):
        sql = str(CompletedOccurrence.objects.with_related_counts().query)

        self.assertIn("SELECT COUNT(", sql)
        self.assertNotIn("LEFT OUTER JOIN", sql)
    def test_completed_occurrence_tabs_include_images(self):
        view = CompletedOccurrenceDetailView()
        self.assertIn("images", [tab["id"] for tab in view.get_tabs()])
        self.assertIn("map", [tab["id"] for tab in view.get_tabs()])
        self.assertIn("mni", [tab["id"] for tab in view.get_tabs()])

    def test_transect_track_table_identifies_recording_device(self):
        view = CompletedTransectDetailView()
        view.object = SimpleNamespace(
            track_points=SimpleNamespace(
                all=lambda: [SimpleNamespace(
                    user="Briana", time=None, lat=1, long=2,
                    is_start=False, is_checkpoint=True, is_occurrence=False,
                    is_turn_point=False, is_end=False,
                )]
            )
        )

        headers, rows = view.get_track_point_table()

        self.assertEqual(headers[0]["label"], "User / device")
        self.assertEqual(rows[0][0]["value"], "Briana")

    @patch("bones.views.master_detail.CompletedOccurrence.objects")
    def test_occurrence_detail_does_not_prefetch_all_responses(self, objects):
        selected = MagicMock()
        workflows = MagicMock()
        details = MagicMock()
        objects.select_related.return_value = selected
        selected.with_workflows.return_value = workflows
        workflows.with_details.return_value = details

        queryset = CompletedOccurrenceDetailView().get_queryset()

        self.assertIs(queryset, details)
        selected.with_related_data.assert_not_called()

    def test_response_pagination_preserves_filter_parameters(self):
        view = CompletedOccurrenceDetailView()
        request = self.factory.get(
            "/occurrences/1/",
            {
                "response_page": "2",
                "response_filter_applied": "1",
                "response_question": ["Side", "Complete?"],
            },
        )
        view.setup(request, pk=1)

        querystring = view._response_page_querystring()

        self.assertNotIn("response_page", querystring)
        self.assertIn("response_filter_applied=1", querystring)
        self.assertEqual(querystring.count("response_question="), 2)

    @patch("bones.views.master_detail.build_mni_detail")
    def test_occurrence_mni_is_deferred_on_initial_page(self, build_mni_detail):
        view = CompletedOccurrenceDetailView()
        view.setup(self.factory.get("/occurrences/1260/"), pk=1260)
        view.object = SimpleNamespace(pk=1260, transect_id=3966264)

        self.assertIsNone(view.get_mni_detail())
        build_mni_detail.assert_not_called()

    @patch("bones.views.master_detail.build_mni_detail", return_value={"available": True})
    def test_occurrence_mni_loads_only_when_requested(self, build_mni_detail):
        view = CompletedOccurrenceDetailView()
        request = self.factory.get(
            "/occurrences/1260/", {"load_mni": "1", "response_page": "2"}
        )
        view.setup(request, pk=1260)
        view.object = SimpleNamespace(pk=1260, transect_id=3966264)

        self.assertEqual(view.get_mni_detail(), {"available": True})
        build_mni_detail.assert_called_once_with(3966264, occurrence_id=1260)
        self.assertEqual(
            view.get_mni_load_url(),
            "?load_mni=1&response_page=2#mni",
        )

    def test_occurrence_mni_template_offers_deferred_load_action(self):
        html = render_to_string(
            "bones/completed_occurrences/_mni.html",
            {"mni_detail": None, "mni_load_url": "?load_mni=1#mni"},
        )

        self.assertIn("Load MNI analysis", html)
        self.assertIn('?load_mni=1#mni', html)

    def test_related_template_renders_response_page_controls(self):
        page = Paginator(list(range(101)), 100).get_page(1)
        html = render_to_string(
            "bones/completed_occurrences/_related.html",
            {
                "request": self.factory.get("/occurrences/1/"),
                "occurrence_response_page": page,
                "response_page_querystring": "&response_filter_applied=1",
                "occurrence_instances": [],
                "response_question_choices": [],
                "match_question": "",
                "match_response": "",
            },
        )

        self.assertIn("Response page 1 of 2 (101 responses)", html)
        self.assertIn("response_page=2&amp;response_filter_applied=1#related", html)
        self.assertIn("Response pagination", html)
    def test_completed_occurrence_related_tab_is_named_instances(self):
        view = CompletedOccurrenceDetailView()
        tabs = list(view.get_tabs())
        self.assertEqual(
            next(tab["label"] for tab in tabs if tab["id"] == "related"),
            "Instances",
        )
    def test_completed_occurrence_extra_actions_use_safe_reverse(self):
        view = CompletedOccurrenceDetailView()
        request = self.factory.get("/occurrences/1/")
        view.setup(request, pk=1)
        view.object = SimpleNamespace(pk=1, transect=None, history=SimpleNamespace(all=lambda: []))
        actions = list(view.get_extra_actions())
        self.assertTrue(actions)
        for action in actions:
            self.assertIn("label", action)
            self.assertIn("icon", action)

    def test_format_coordinates_handles_missing_values(self):
        result = CompletedTransectDetailView._format_coordinates(None, 12)
        self.assertEqual(result, "—")
        formatted = CompletedTransectDetailView._format_coordinates(1.23, 4.56)
        self.assertIn("Lat", formatted)

    def test_completed_occurrence_instance_summaries_grouped_by_instance(self):
        class DummyManager:
            def __init__(self, items):
                self._items = list(items)

            def all(self):
                return list(self._items)

        view = CompletedOccurrenceDetailView()
        request = self.factory.get("/occurrences/42/")
        view.setup(request, pk=42)

        workflows = [
            SimpleNamespace(
                pk=1,
                template_workflow=SimpleNamespace(name="Alpha"),
                instance_number=1,
                completed_by="Alice",
            ),
            SimpleNamespace(
                pk=2,
                template_workflow=SimpleNamespace(name="Beta"),
                instance_number=2,
                completed_by="Bob",
            ),
            SimpleNamespace(
                pk=3,
                template_workflow=SimpleNamespace(name="Alpha"),
                instance_number=1,
                completed_by="Cara",
            ),
        ]
        responses = [
            SimpleNamespace(
                question_number=2,
                question_text="Second question",
                response="Answer two",
                response_code="R2",
                skipped=False,
                workflow=workflows[0],
            ),
            SimpleNamespace(
                question_number=1,
                question_text="First question",
                response="Answer one",
                response_code="R1",
                skipped=False,
                workflow=workflows[2],
            ),
            SimpleNamespace(
                question_number=1,
                question_text="Beta question",
                response="Answer beta",
                response_code="R4",
                skipped=False,
                workflow=workflows[1],
            ),
            SimpleNamespace(
                question_number=2,
                question_text="Skipped question",
                response="Should hide",
                response_code="R5",
                skipped=True,
                workflow=workflows[1],
            ),
        ]

        view.object = SimpleNamespace(
            pk=42,
            responses=DummyManager(responses),
            workflows=DummyManager(workflows),
        )

        with patch("bones.views.master_detail.safe_reverse", return_value="/workflows/"):
            instance_summaries = view.get_instance_summaries()

        self.assertEqual([summary["number"] for summary in instance_summaries], [1, 2])
        self.assertNotIn("—", [summary["display_number"] for summary in instance_summaries])

        instance_one = instance_summaries[0]
        instance_two = instance_summaries[1]

        self.assertEqual(len(instance_one["response_rows"]), 2)
        self.assertEqual(len(instance_one["workflow_rows"]), 2)
        self.assertEqual(instance_one["url"], "/workflows/")

        self.assertEqual(len(instance_two["response_rows"]), 1)
        self.assertEqual(len(instance_two["workflow_rows"]), 1)
        self.assertEqual(instance_two["url"], "/workflows/")

        instance_one_question_order = [row[0]["value"] for row in instance_one["response_rows"]]
        self.assertEqual(instance_one_question_order, ["First question", "Second question"])

        instance_two_questions = [row[0]["value"] for row in instance_two["response_rows"]]
        self.assertEqual(instance_two_questions, ["Beta question"])

    def test_completed_occurrence_instance_summaries_include_matching_images(self):
        view = CompletedOccurrenceDetailView()
        view.object = SimpleNamespace(pk=42)
        image = SimpleNamespace(pk=uuid4())

        with patch("bones.views.master_detail.safe_reverse", return_value="/workflows/"):
            summaries = view.get_instance_summaries(
                workflows=[
                    SimpleNamespace(
                        pk=1,
                        template_workflow=SimpleNamespace(name="Alpha"),
                        instance_number=1,
                        completed_by="Alice",
                    )
                ],
                responses=[],
                images_by_instance={1: [image]},
            )

        self.assertEqual(summaries[0]["images"], [image])

    def test_occurrence_instance_responses_can_be_filtered_by_question(self):
        workflow = SimpleNamespace(
            pk=1,
            template_workflow=SimpleNamespace(name="Bones"),
            instance_number=1,
            completed_by="Alice",
        )
        responses = [
            SimpleNamespace(question_number=1,question_text="What element is this?",response="Femur",response_code="femur",skipped=False,workflow=workflow),
            SimpleNamespace(question_number=2,question_text="Side",response="Left",response_code="left",skipped=False,workflow=workflow),
            SimpleNamespace(question_number=3,question_text="Weathering class",response="2",response_code="2",skipped=False,workflow=workflow),
            SimpleNamespace(question_number=4,question_text="Other question",response="Hidden",response_code="hidden",skipped=False,workflow=workflow),
        ]
        view = CompletedOccurrenceDetailView()
        view.object = SimpleNamespace(pk=42)

        with patch("bones.views.master_detail.safe_reverse", return_value="/workflows/"):
            summaries = view.get_instance_summaries(
                workflows=[workflow],
                responses=responses,
                question_texts={"What element is this?", "Side", "Weathering class"},
            )

        self.assertEqual(
            [row[0]["value"] for row in summaries[0]["response_rows"]],
            ["What element is this?", "Side", "Weathering class"],
        )

    def test_response_question_choices_are_unique_sorted_and_skip_hidden_answers(self):
        choices = CompletedOccurrenceDetailView.get_response_question_choices([
            SimpleNamespace(question_text="Side",skipped=False),
            SimpleNamespace(question_text="Weathering class",skipped=False),
            SimpleNamespace(question_text="Side",skipped=False),
            SimpleNamespace(question_text="Skipped",skipped=True),
        ])

        self.assertEqual(choices,["Side","Weathering class"])

    def test_occurrence_instances_can_be_filtered_by_question_response_pair(self):
        workflows = [
            SimpleNamespace(pk=1,template_workflow=SimpleNamespace(name="Bones"),instance_number=1,completed_by="Alice"),
            SimpleNamespace(pk=2,template_workflow=SimpleNamespace(name="Bones"),instance_number=2,completed_by="Bob"),
        ]
        responses = [
            SimpleNamespace(question_number=1,question_text="What element is this?",response="Humerus",response_code="humerus",skipped=False,workflow=workflows[0]),
            SimpleNamespace(question_number=1,question_text="What element is this?",response="Femur",response_code="femur",skipped=False,workflow=workflows[1]),
        ]
        view = CompletedOccurrenceDetailView()
        view.object = SimpleNamespace(pk=42)

        with patch("bones.views.master_detail.safe_reverse", return_value="/workflows/"):
            summaries = view.get_instance_summaries(
                workflows=workflows,
                responses=responses,
                match_question="What element is this?",
                match_response="humerus",
            )

        self.assertEqual([summary["number"] for summary in summaries],[1])

    def test_default_response_questions_match_requested_rows(self):
        self.assertEqual(
            CompletedOccurrenceDetailView.default_response_questions,
            ("What element is this?","Complete?","Side","Weathering class"),
        )

    def test_instance_image_gallery_is_read_only(self):
        image = SimpleNamespace(
            pk=uuid4(),
            alt_text="Instance photograph",
            generated_alt_text="Generated description",
        )

        html = render_to_string(
            "bones/images/_readonly_gallery.html",
            {
                "images": [image],
                "instance_number": 1,
                "instance_display_number": "1",
            },
        )

        self.assertIn("Images for instance 1", html)
        self.assertIn("Instance photograph", html)
        self.assertIn("/thumbnail/", html)
        self.assertNotIn("<form", html)
        self.assertNotIn("Upload image", html)
        self.assertNotIn("Remove link", html)

    def test_instance_image_gallery_is_omitted_when_empty(self):
        html = render_to_string(
            "bones/images/_readonly_gallery.html",
            {
                "images": [],
                "instance_number": 1,
                "instance_display_number": "1",
            },
        )

        self.assertEqual(html.strip(), "")

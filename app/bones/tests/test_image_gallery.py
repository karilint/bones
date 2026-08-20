from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django import forms
from django.template.loader import get_template, render_to_string
from django.test import SimpleTestCase
from django.urls import resolve, reverse

from ..image_forms import ImageGalleryFilterForm
from ..navigation import navigation_context
from ..views.images import ImageGalleryView


class ImageGalleryTests(SimpleTestCase):
    def test_gallery_url_navigation_and_template_are_available(self):
        self.assertIs(resolve("/images/").func.view_class, ImageGalleryView)
        section = next(
            item for item in navigation_context(object())["navigation_sections"]
            if item["label"] == "Images"
        )
        self.assertEqual(section["url"], reverse("bones:images"))
        self.assertEqual(section["icon"], "fa-solid fa-images")
        self.assertIsNotNone(get_template("bones/images/gallery.html"))

    @patch.object(
        ImageGalleryFilterForm,
        "_linked_choice_values",
        return_value={
            "habitat": ["Grass open", "Shrubs closed"],
            "taxon": ["Wildebeest", "Zebra"],
            "element": ["Mandible", "Scapula"],
        },
    )
    def test_example_filters_are_valid(self, _linked_choice_values):
        form = ImageGalleryFilterForm(
            {"habitat": "Grass open", "taxon": "Zebra", "element": "Mandible"}
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsInstance(form.fields["habitat"].widget, forms.Select)
        self.assertIsInstance(form.fields["taxon"].widget, forms.Select)
        self.assertIsInstance(form.fields["element"].widget, forms.Select)
        self.assertIn(("Zebra", "Zebra"), form.fields["taxon"].choices)

    @patch("bones.views.images.CompletedWorkflow.objects.filter")
    @patch("bones.views.images.CompletedOccurrence.objects.filter")
    @patch("bones.views.images.CompletedTransect.objects.all")
    def test_example_filters_follow_hierarchy(
        self, transect_all, occurrence_filter, workflow_filter
    ):
        transects = MagicMock()
        habitat_transects = MagicMock()
        transect_all.return_value = transects
        transects.filter.return_value = habitat_transects
        occurrences = MagicMock()
        taxon_occurrences = MagicMock()
        occurrence_filter.return_value = occurrences
        occurrences.filter.return_value = taxon_occurrences
        workflows = MagicMock()
        element_workflows = MagicMock()
        workflow_filter.return_value = workflows
        workflows.filter.return_value = element_workflows
        element_workflows.values_list.return_value.distinct.return_value = [(17, 4)]
        images = MagicMock()
        matching_image = SimpleNamespace(entity_type="instance", entity_id="17:4")
        images.prefetch_related.return_value = [matching_image]

        result = ImageGalleryView._filter_queryset(images, {
            "transect": "", "habitat": "Grass open", "occurrence": None,
            "taxon": "Zebra", "instance": None, "element": "Mandible",
        })

        transects.filter.assert_called_once_with(
            details__pre_or_post__iexact="Pre",
            details__question_text__iexact="Transect physical habitat",
            details__response__iexact="Grass open",
        )
        occurrences.filter.assert_called_once_with(
            details__question_text__in=("Taxon Guess?", "Taxon"),
            details__response__iexact="Zebra",
        )
        workflows.filter.assert_called_once_with(
            responses__skipped=False,
            responses__question_text__iexact="What element is this?",
            responses__response__iexact="Mandible",
        )
        self.assertEqual(result, [matching_image])

    def test_linked_target_can_match_when_primary_entity_does_not(self):
        target = SimpleNamespace(entity_type="instance", entity_id="17:4")
        image = SimpleNamespace(
            entity_type="occurrence",
            entity_id="17",
            targets=SimpleNamespace(all=lambda: [target]),
        )
        self.assertTrue(
            ImageGalleryView._matches_allowed_entity(
                image, {"instance": {"17:4"}}
            )
        )

    def test_gallery_metadata_links_to_each_detail_level(self):
        metadata = {
            "transect_uid": 123,
            "transect_name": "North",
            "occurrence_id": 17,
            "occurrence_number": 2,
            "instance_number": 4,
            "habitat": "Grass open",
            "taxon": "Zebra",
            "element": "Mandible",
            "side": "Left",
        }
        image = SimpleNamespace(
            pk="2df1c9d2-284a-43d6-a877-a8b713863175",
            alt_text="Zebra bone",
            generated_alt_text="Image",
            entity_type="instance",
            parsed_metadata=metadata,
            gallery_metadata=metadata,
        )
        html = render_to_string("bones/images/gallery.html", {
            "filter_form": [], "filter_error": None, "result_count": 1,
            "images": [image], "is_paginated": False,
        })
        self.assertIn(reverse("bones:transects:detail", args=[123]), html)
        self.assertIn(reverse("bones:occurrences:detail", args=[17]), html)
        self.assertIn("bones-image-card-media", html)
        self.assertIn("bones-image-card-body", html)
        for value in ("Grass open", "Zebra", "Mandible", "Left"):
            self.assertIn(value, html)
        self.assertIn(
            reverse("bones:occurrences:instance_detail", args=[17, 4]), html
        )

    def test_hierarchy_captions_follow_image_level_and_show_photo_role(self):
        metadata = {
            "transect_uid": 123, "transect_name": "North",
            "occurrence_id": 17, "occurrence_number": 2,
            "instance_number": 4, "transect_photo_role": "Start",
        }
        base = {
            "pk": "2df1c9d2-284a-43d6-a877-a8b713863175",
            "alt_text": "Survey image", "generated_alt_text": "Image",
            "gallery_metadata": metadata,
        }
        context = {
            "filter_form": [], "filter_error": None, "result_count": 1,
            "is_paginated": False,
        }
        transect_html = render_to_string(
            "bones/images/gallery.html",
            {**context, "images": [SimpleNamespace(**base, entity_type="transect")]},
        )
        self.assertIn("Start", transect_html)
        self.assertNotIn("Occurrence 2", transect_html)
        self.assertNotIn("Instance 4", transect_html)
        self.assertIn("<dt>Habitat</dt>", transect_html)
        self.assertNotIn("<dt>Taxon</dt>", transect_html)
        self.assertNotIn("<dt>Element</dt>", transect_html)
        self.assertNotIn("<dt>Side</dt>", transect_html)

        occurrence_html = render_to_string(
            "bones/images/gallery.html",
            {**context, "images": [SimpleNamespace(**base, entity_type="occurrence")]},
        )
        self.assertIn("Occurrence 2", occurrence_html)
        self.assertNotIn("Instance 4", occurrence_html)
        self.assertIn("<dt>Taxon</dt>", occurrence_html)
        self.assertNotIn("<dt>Element</dt>", occurrence_html)
        self.assertNotIn("<dt>Side</dt>", occurrence_html)

    @patch("bones.views.images.CompletedTransect.objects.filter")
    @patch("bones.views.images.CompletedOccurrence.objects.filter")
    def test_legacy_image_gets_transect_name_from_uid(
        self, occurrence_filter, transect_filter
    ):
        occurrence_filter.return_value.only.return_value = []
        transect_filter.return_value.only.return_value = [
            SimpleNamespace(pk=4478950, name="105")
        ]
        image = SimpleNamespace(
            entity_type="transect",
            entity_id="4478950",
            parsed_metadata={"transect_uid": 4478950},
            targets=SimpleNamespace(all=lambda: []),
        )

        with patch.object(
            ImageGalleryView,
            "_related_display_values",
            return_value={"habitats": {}, "taxa": {}, "elements": {}, "sides": {}},
        ):
            ImageGalleryView._add_display_metadata([image])

        self.assertEqual(image.gallery_metadata["transect_name"], "105")

    @patch("bones.views.images.CompletedTransect.objects.filter")
    @patch("bones.views.images.CompletedOccurrence.objects.filter")
    def test_current_instance_link_overrides_stale_import_metadata(
        self, occurrence_filter, transect_filter
    ):
        occurrence_filter.return_value.only.return_value = [
            SimpleNamespace(pk=1260, occurrence_number=6, transect_id=3966264)
        ]
        transect_filter.return_value.only.return_value = [
            SimpleNamespace(pk=3966264, name="94")
        ]
        image = SimpleNamespace(
            entity_type="instance",
            entity_id="1260:18",
            parsed_metadata={
                "occurrence_id": 599,
                "occurrence_number": 2,
                "instance_number": 18,
            },
            targets=SimpleNamespace(all=lambda: []),
        )

        with patch.object(
            ImageGalleryView,
            "_related_display_values",
            return_value={"habitats": {}, "taxa": {}, "elements": {}, "sides": {}},
        ):
            ImageGalleryView._add_display_metadata([image])

        self.assertEqual(image.gallery_metadata["occurrence_id"], 1260)
        self.assertEqual(image.gallery_metadata["occurrence_number"], 6)
        self.assertEqual(image.gallery_metadata["instance_number"], 18)
        self.assertEqual(image.gallery_metadata["transect_name"], "94")

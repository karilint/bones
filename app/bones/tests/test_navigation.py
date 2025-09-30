from django.test import SimpleTestCase
from django.urls import reverse

from ..navigation import _materialise_link, navigation_context


class NavigationContextTests(SimpleTestCase):
    def _find_link(self, label: str):
        context = navigation_context(object())
        sections = context["navigation_sections"]

        for section in sections:
            if section.get("label") == label:
                return section
            for child in section.get("children", []):
                if child.get("label") == label:
                    return child
        self.fail(f"Navigation link with label '{label}' was not found")

    def test_navigation_context_provides_sections(self):
        context = navigation_context(object())
        sections = context["navigation_sections"]
        self.assertTrue(sections)
        for section in sections:
            self.assertIn("label", section)
            self.assertIn("icon", section)
            self.assertIn("url", section)
            self.assertIn("children", section)

    def test_materialise_link_uses_fallback_url(self):
        link = _materialise_link(
            {
                "label": "Example",
                "icon": "fa-solid fa-circle-info",
                "fallback_url": "/placeholder/",
                "children": [{"label": "Child", "fallback_url": "/child/"}],
            }
        )
        self.assertEqual(link["url"], "/placeholder/")
        self.assertEqual(link["children"][0]["url"], "/child/")

    def test_materialise_link_uses_descendant_when_no_direct_fallback(self):
        link = _materialise_link(
            {
                "label": "Parent",
                "children": [
                    {
                        "label": "Child",
                        "url": "/child/",
                    }
                ],
            }
        )

        self.assertEqual(link["url"], "/child/")

    def test_completed_transects_link_points_to_list_view(self):
        link = self._find_link("Completed Transects")
        self.assertEqual(link["url"], reverse("bones:transects:list"))

    def test_completed_occurrences_link_points_to_list_view(self):
        link = self._find_link("Completed Occurrences")
        self.assertEqual(link["url"], reverse("bones:occurrences:list"))

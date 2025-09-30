from django.test import SimpleTestCase

from ..navigation import _materialise_link, navigation_context


class NavigationContextTests(SimpleTestCase):
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
                "children": [{"label": "Child", "fallback_url": "#"}],
            }
        )
        self.assertEqual(link["url"], "/placeholder/")
        self.assertEqual(link["children"][0]["url"], "#")

from pathlib import Path

from django.test import SimpleTestCase


class TemplateMarkupTests(SimpleTestCase):
    def setUp(self):
        self.templates_dir = Path(__file__).resolve().parents[1] / "templates" / "bones"

    def test_base_template_references_w3css(self):
        base_html = (self.templates_dir / "base.html").read_text(encoding="utf-8")
        self.assertIn("w3.css", base_html)
        self.assertIn("w3-content", base_html)

    def test_table_partial_includes_w3_table_classes(self):
        table_html = (self.templates_dir / "partials" / "table.html").read_text(encoding="utf-8")
        self.assertIn("w3-table", table_html)
        self.assertIn("w3-bordered", table_html)

    def test_tabs_partial_exposes_tablist_markup(self):
        tabs_html = (self.templates_dir / "partials" / "tabs.html").read_text(encoding="utf-8")
        self.assertIn("role=\"tablist\"", tabs_html)
        self.assertIn("w3-bar", tabs_html)

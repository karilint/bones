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

    def test_transect_note_filter_partial_uses_select2_multi_response(self):
        partial_html = (
            self.templates_dir / "partials" / "transect_note_filters.html"
        ).read_text(encoding="utf-8")
        self.assertIn("bones-select2", partial_html)
        self.assertIn("data-note-filter-add", partial_html)
        self.assertIn("multiple", partial_html)
        self.assertIn("transect-note-response-map", partial_html)
        self.assertIn("note_{{ row.index }}_note", partial_html)
        self.assertIn("note_{{ row.index }}_response", partial_html)

    def test_transect_list_binds_select2_change_for_note_filters(self):
        list_html = (self.templates_dir / "completed_transect_list.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("window.jQuery(list).on('change'", list_html)
        self.assertIn("handleNoteChange(this)", list_html)

    def test_occurrence_note_filters_render_both_reusable_groups(self):
        partial_html = (
            self.templates_dir / "partials" / "occurrence_note_filters.html"
        ).read_text(encoding="utf-8")
        group_html = (
            self.templates_dir / "partials" / "note_filter_group.html"
        ).read_text(encoding="utf-8")
        list_html = (
            self.templates_dir / "completed_occurrence_list.html"
        ).read_text(encoding="utf-8")

        self.assertIn('prefix="transect_note_"', partial_html)
        self.assertIn('prefix="occurrence_note_"', partial_html)
        self.assertIn("data-note-filter-group", group_html)
        self.assertIn("multiple", group_html)
        self.assertIn("bones/js/note_filters.js", list_html)
        script_html = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "bones"
            / "js"
            / "note_filters.js"
        ).read_text(encoding="utf-8")
        self.assertIn("window.jQuery(list).on(", script_html)
        self.assertIn("function () { handleNoteChange(this); }", script_html)


class MapInteractionAssetTests(SimpleTestCase):
    def test_shared_map_script_enables_hover_popups(self):
        from pathlib import Path
        from django.conf import settings

        script = Path(settings.BASE_DIR, "bones", "static", "bones", "js", "maps.js").read_text(encoding="utf-8")
        self.assertIn('featureLayer.on("mouseover focus"', script)
        self.assertIn("bindHoverPopup(featureLayer)", script)
        self.assertIn("summary_line", script)

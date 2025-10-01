import unittest

from django.core.paginator import Paginator

from ..templatetags.pagination_tags import compact_page_range


class CompactPageRangeTests(unittest.TestCase):
    def _build_page(self, total_items, per_page, number):
        paginator = Paginator(range(total_items), per_page)
        return paginator.page(number)

    def test_returns_all_pages_when_total_below_window(self):
        page = self._build_page(total_items=5, per_page=5, number=1)
        self.assertEqual(list(compact_page_range(page, max_length=3)), [1])

    def test_centers_current_page_when_possible(self):
        page = self._build_page(total_items=50, per_page=5, number=5)
        self.assertEqual(list(compact_page_range(page, max_length=3)), [4, 5, 6])

    def test_shifts_window_to_start_when_near_beginning(self):
        page = self._build_page(total_items=50, per_page=5, number=1)
        self.assertEqual(list(compact_page_range(page, max_length=3)), [1, 2, 3])

    def test_shifts_window_to_end_when_near_finish(self):
        page = self._build_page(total_items=50, per_page=5, number=10)
        self.assertEqual(list(compact_page_range(page, max_length=3)), [8, 9, 10])

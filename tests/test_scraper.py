"""
Tests for scraper.py

All tests are offline — they parse the HTML fixtures in this directory
and never make network requests.
"""

import sys
from datetime import date, datetime
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

# Allow importing scraper from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper import (
    _parse_date_headers,
    _parse_event_cell,
    _resolve_cell_columns,
    scrape_week,
)

FIXTURES = Path(__file__).resolve().parent


def _load(filename: str) -> BeautifulSoup:
    return BeautifulSoup((FIXTURES / filename).read_text(), "html.parser")


# ---------------------------------------------------------------------------
# _parse_date_headers
# ---------------------------------------------------------------------------

class TestParseDateHeaders:
    def test_normal_week(self):
        soup = _load("fixture_week.html")
        col_to_date = _parse_date_headers(soup, reference_year=2026)

        # col 1 = Mon 27.04.2026, col 4 = Tue 28.04.2026, ... col 13 = Fri 01.05.2026
        assert col_to_date[1] == date(2026, 4, 27)
        assert col_to_date[4] == date(2026, 4, 28)
        assert col_to_date[7] == date(2026, 4, 29)
        assert col_to_date[10] == date(2026, 4, 30)
        assert col_to_date[13] == date(2026, 5, 1)

    def test_year_wrap(self):
        """Thu 01.01. must resolve to 2026, not 2025."""
        soup = _load("fixture_year_wrap.html")
        col_to_date = _parse_date_headers(soup, reference_year=2025)

        assert col_to_date[1] == date(2025, 12, 29)
        assert col_to_date[4] == date(2025, 12, 30)
        assert col_to_date[7] == date(2025, 12, 31)
        assert col_to_date[10] == date(2026, 1, 1)   # year incremented
        assert col_to_date[13] == date(2026, 1, 2)

    def test_returns_empty_for_no_headers(self):
        soup = BeautifulSoup("<html></html>", "html.parser")
        assert _parse_date_headers(soup, 2026) == {}


# ---------------------------------------------------------------------------
# _resolve_cell_columns
# ---------------------------------------------------------------------------

class TestResolveCellColumns:
    def test_assigns_correct_column_indices(self):
        """The week_block event cells must land at the expected column indices."""
        soup = _load("fixture_week.html")
        table = soup.find("table", class_="week_table")
        cell_cols = _resolve_cell_columns(table)

        week_blocks = [
            (cell, col)
            for cell, col in cell_cols
            if "week_block" in (cell.get("class") or [])
        ]

        # E1 is in the first sub-column of Monday (col 1)
        # E2 is in the first sub-column of Tuesday (col 4)
        cols = [col for _, col in week_blocks]
        assert 1 in cols, "E1 (Lineare Algebra) should be at col 1"
        assert 4 in cols, "E2 (Programmieren) should be at col 4"

    def test_no_blocks_in_empty_table(self):
        soup = BeautifulSoup(
            "<table class='week_table'><tr><td></td></tr></table>",
            "html.parser",
        )
        table = soup.find("table")
        cell_cols = _resolve_cell_columns(table)
        week_blocks = [c for c, _ in cell_cols if "week_block" in (c.get("class") or [])]
        assert week_blocks == []


# ---------------------------------------------------------------------------
# _parse_event_cell
# ---------------------------------------------------------------------------

class TestParseEventCell:
    def _get_block(self, soup, index=0):
        table = soup.find("table", class_="week_table")
        cell_cols = _resolve_cell_columns(table)
        blocks = [(c, col) for c, col in cell_cols if "week_block" in (c.get("class") or [])]
        return blocks[index]

    def test_e1_fields(self):
        soup = _load("fixture_week.html")
        col_to_date = _parse_date_headers(soup, 2026)
        cell, col = self._get_block(soup, 0)
        event = _parse_event_cell(cell, col_to_date, col)

        assert event is not None
        assert event["title"] == "Lineare Algebra"
        assert event["location"] == "A101"
        assert event["start"] == datetime(2026, 4, 27, 8, 0)
        assert event["end"] == datetime(2026, 4, 27, 10, 0)

    def test_e2_fields(self):
        soup = _load("fixture_week.html")
        col_to_date = _parse_date_headers(soup, 2026)
        cell, col = self._get_block(soup, 1)
        event = _parse_event_cell(cell, col_to_date, col)

        assert event is not None
        assert event["title"] == "Programmieren"
        assert event["location"] == "B202"
        assert event["start"] == datetime(2026, 4, 28, 9, 0)
        assert event["end"] == datetime(2026, 4, 28, 11, 0)

    def test_year_wrap_event(self):
        soup = _load("fixture_year_wrap.html")
        col_to_date = _parse_date_headers(soup, 2025)
        cell, col = self._get_block(soup, 0)
        event = _parse_event_cell(cell, col_to_date, col)

        assert event is not None
        assert event["title"] == "Einführung"
        assert event["start"] == datetime(2026, 1, 1, 10, 0)
        assert event["end"] == datetime(2026, 1, 1, 12, 0)

    def test_returns_none_for_cell_without_anchor(self):
        from bs4 import BeautifulSoup as BS
        soup = BS('<td class="week_block"><span>no anchor</span></td>', "html.parser")
        cell = soup.find("td")
        assert _parse_event_cell(cell, {}, 1) is None


# ---------------------------------------------------------------------------
# scrape_week (offline — monkeypatched fetch)
# ---------------------------------------------------------------------------

class TestScrapeWeek:
    def test_returns_two_events_from_fixture(self, monkeypatch):
        html = (FIXTURES / "fixture_week.html").read_text()
        monkeypatch.setattr("scraper.fetch_page", lambda *a, **kw: html)

        events = scrape_week(date(2026, 4, 27))
        assert len(events) == 2

        titles = {e["title"] for e in events}
        assert titles == {"Lineare Algebra", "Programmieren"}

    def test_deduplication(self, monkeypatch):
        """Calling scrape_week twice with the same HTML should not duplicate events."""
        html = (FIXTURES / "fixture_week.html").read_text()
        call_count = 0

        def fake_fetch(*a, **kw):
            nonlocal call_count
            call_count += 1
            return html

        monkeypatch.setattr("scraper.fetch_page", fake_fetch)
        events = scrape_week(date(2026, 4, 27))
        keys = [(e["title"], e["start"]) for e in events]
        assert len(keys) == len(set(keys)), "Duplicate events returned"

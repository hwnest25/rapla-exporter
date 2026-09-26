"""
scraper.py: Fetch and parse the Rapla HTML calendar into structured event dicts.

Computer Science concepts used here:
  - HTTP requests (requests library)
  - HTML parsing via a DOM tree (BeautifulSoup)
  - Table geometry: Resolving column index to date, rowspan to duration
  - Regex for extracting time strings from mixed text
  - datetime arithmetic (timedelta)
"""

from __future__ import annotations

import re
import requests
from datetime import date, datetime, timedelta
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://rapla.dhbw.de/rapla/calendar"
DEFAULT_USER = "Britta.konrath@intern.mosbach.dhbw.de"
DEFAULT_FILE = "Vorlesungsplan TINFO25"

# Rapla encodes the calendar as 15-minute row slots.
MINUTES_PER_ROW = 15

# The time column (leftmost) is always column index 0 inside the tbody.
# Days start at column index 1 and each day occupies 3 sub-columns in the HTML
# (for overlapping events). We only care about the first sub-column of each
# day to determine the date.
COLS_PER_DAY = 3
FIRST_DAY_COL = 1  # 0 = time label column


# ---------------------------------------------------------------------------
# HTTP fetching
# ---------------------------------------------------------------------------

def fetch_page(
    start_date: date,
    pages: int = 1,
    user: str = DEFAULT_USER,
    file: str = DEFAULT_FILE,
) -> str:
    """
    Fetch one HTML page of the Rapla calendar.

    `pages` is Rapla's "number of weeks to show" parameter (1 to 20).
    We always fetch one week at a time and paginate ourselves so parsing
    stays simple.

    CS Concept --> HTTP Requests: Query parameters are key=value pairs appended
    to the URL after '?', separated by '&'. The requests library encodes them
    safely (e.g. spaces to %20, '@' to %40).
    """
    params = {
        "user": user,
        "file": file,
        "day": start_date.day,
        "month": start_date.month,
        "year": start_date.year,
        "pages": pages,
    }
    response = requests.get(BASE_URL, params=params, timeout=15)
    response.raise_for_status()  # Raises an exception for 4xx/5xx status codes
    return response.text


# ---------------------------------------------------------------------------
# Date header parsing
# ---------------------------------------------------------------------------

def _parse_date_headers(soup: BeautifulSoup, reference_year: int) -> dict[int, date]:
    """
    Parse the column-index to date mapping from the week header row.

    The header row looks like:
        <th class="week_number">KW 18</th>
        <td class="week_header" colspan="3"><nobr>Mo 27.04.</nobr></td>
        <td class="week_header" colspan="3"><nobr>Di 28.04.</nobr></td>
        ...

    Note: The <tr> itself has no class. The class "week_header" lives on the
    inner <td> elements. We find any such <td> first, then walk up to its
    parent <tr> to get the full row.

    CS Concept --> Table Geometry/Positional Indexing: We walk the header cells
    in order and track a running column counter. Each day-header cell has
    colspan=3 (for the 3 sub-columns that allow overlapping events), so one
    visible header cell actually occupies 3 column positions.

    Returns {absolute_column_index: date_object, ...}
    """
    col_to_date: dict[int, date] = {}

    # Find the first td.week_header and get its parent <tr>.
    first_header_cell = soup.find("td", class_="week_header")
    if first_header_cell is None:
        return col_to_date
    header_row = first_header_cell.find_parent("tr")
    if header_row is None:
        return col_to_date

    col_idx = 0
    prev_month = None

    for cell in header_row.find_all(["th", "td"]):
        colspan = int(cell.get("colspan", 1))

        if "week_header" in (cell.get("class") or []):
            text = cell.get_text(strip=True)  # e.g. "Mo 27.04."
            match = re.search(r"(\d{1,2})\.(\d{1,2})\.", text)
            if match:
                day, month = int(match.group(1)), int(match.group(2))
                # Handle year wrap: If month goes from 12 back to 1 within the
                # same week (e.g. a week spanning Dec 29 to Jan 4), increment
                # the year for the January dates.
                year = reference_year
                if prev_month == 12 and month == 1:
                    year += 1
                col_to_date[col_idx] = date(year, month, day)
                prev_month = month

        col_idx += colspan

    return col_to_date


# ---------------------------------------------------------------------------
# Event cell parsing
# ---------------------------------------------------------------------------

def _parse_event_cell(cell, col_to_date: dict[int, date], cell_col: int) -> dict | None:
    """
    Parse a single <td class="week_block"> into an event dict.

    CS Concept --> Regex: The cell's anchor text looks like
    "08:00 -10:00\nLineare Algebra". We use a regular expression to capture
    the two time groups regardless of minor spacing variations (e.g.
    "08:00 - 10:00" vs "08:00 -10:00").

    Pattern breakdown:
        (\d{2}:\d{2})   --> capture group 1: start time  HH:MM
        \s*-\s*         --> literal dash, optional surrounding spaces
        (\d{2}:\d{2})   --> capture group 2: end time    HH:MM
    """
    anchor = cell.find("a")
    if anchor is None:
        return None

    raw_text = anchor.get_text(separator="\n").strip()
    time_match = re.match(r"(\d{2}:\d{2})\s*[-]\s*(\d{2}:\d{2})", raw_text)
    if not time_match:
        return None

    start_str, end_str = time_match.group(1), time_match.group(2)

    # Title is everything after the time portion.
    title_part = raw_text[time_match.end():].strip().lstrip("\n").strip()

    # Location is in <span class="resource">.
    resource_span = cell.find("span", class_="resource")
    location = resource_span.get_text(strip=True) if resource_span else ""

    # Find the event date from the column mapping.
    # We look for the largest column key that is still <= cell_col.
    event_date = None
    for col in sorted(col_to_date.keys()):
        if col <= cell_col:
            event_date = col_to_date[col]

    if event_date is None:
        return None

    sh, sm = map(int, start_str.split(":"))
    eh, em = map(int, end_str.split(":"))

    start_dt = datetime(event_date.year, event_date.month, event_date.day, sh, sm)
    end_dt = datetime(event_date.year, event_date.month, event_date.day, eh, em)

    return {
        "title": title_part,
        "location": location,
        "start": start_dt,
        "end": end_dt,
    }


# ---------------------------------------------------------------------------
# Table grid reconstruction
# ---------------------------------------------------------------------------

def _resolve_cell_columns(table) -> list[tuple]:
    """
    Walk every row/cell in the table and assign an absolute column index to
    each <td>. Returns a list of (td_element, col_index) tuples.

    CS Concept --> 2D Grid Reconstruction with rowspan/colspan:
    HTML tables allow cells to span multiple rows (rowspan) and columns
    (colspan). The browser visually merges these, but in the raw HTML you
    only see the cell in the row where it starts. To know a cell's true
    column, we must simulate the browser's layout engine:
      - Keep an "occupied" dict of (row, col) pairs blocked by a spanning
        cell from a previous row.
      - For each row, skip column positions that are already occupied, place
        the current cell at the next free column, then mark all positions
        it occupies (rowspan x colspan) as occupied.
    """
    occupied: dict[tuple[int, int], bool] = {}
    results = []

    rows = table.find_all("tr")
    for row_idx, row in enumerate(rows):
        col_idx = 0
        for cell in row.find_all(["td", "th"]):
            # Advance past any columns occupied by spanning cells above.
            while occupied.get((row_idx, col_idx)):
                col_idx += 1

            colspan = int(cell.get("colspan", 1))
            rowspan = int(cell.get("rowspan", 1))

            results.append((cell, col_idx))

            # Mark all cells this element spans as occupied.
            for r in range(row_idx, row_idx + rowspan):
                for c in range(col_idx, col_idx + colspan):
                    occupied[(r, c)] = True

            col_idx += colspan

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scrape_week(start_date: date, user: str = DEFAULT_USER, file: str = DEFAULT_FILE) -> list[dict]:
    """
    Fetch and parse one week of the Rapla calendar starting at `start_date`.
    Returns a list of event dicts:
        {"title": str, "location": str, "start": datetime, "end": datetime}
    """
    html = fetch_page(start_date, user=user, file=file)
    soup = BeautifulSoup(html, "html.parser")

    col_to_date = _parse_date_headers(soup, start_date.year)

    table = soup.find("table", class_="week_table")
    if table is None:
        return []

    cell_columns = _resolve_cell_columns(table)

    events = []
    seen = set()  # Deduplicate: Same event can appear on multiple pages.

    for cell, col_idx in cell_columns:
        if "week_block" not in (cell.get("class") or []):
            continue

        event = _parse_event_cell(cell, col_to_date, col_idx)
        if event is None:
            continue

        # Use (title, start) as a deduplication key.
        key = (event["title"], event["start"])
        if key in seen:
            continue
        seen.add(key)
        events.append(event)

    return events


def scrape_weeks(start_date: date, num_weeks: int, user: str = DEFAULT_USER, file: str = DEFAULT_FILE) -> list[dict]:
    """
    Scrape `num_weeks` consecutive weeks beginning at `start_date`.
    Iterates by advancing 7 days per week.

    CS Concept --> Date Arithmetic: timedelta(weeks=1) adds exactly 7 days
    to a date object, correctly handling month/year boundaries.
    """
    all_events = []
    seen: set[tuple] = set()  # Cross-week deduplication key set.
    current = start_date
    for _ in range(num_weeks):
        print(f"  Fetching week of {current.isoformat()} ...")
        week_events = scrape_week(current, user=user, file=file)
        for event in week_events:
            key = (event["title"], event["start"])
            if key not in seen:
                seen.add(key)
                all_events.append(event)
        current += timedelta(weeks=1)
    return all_events

"""
This exporter.py converts structured event dicts into an RFC 5545 iCalendar file.

Computer Science concepts used here:
  - File I/O (writing bytes to disk)
  - The iCalendar standard (RFC 5545): a plain-text format for calendar data
  - Timezones and UTC offsets (pytz / zoneinfo)
  - UUIDs for stable, unique event identifiers
"""

import uuid
import pytz
from datetime import datetime
from pathlib import Path
from icalendar import Calendar, Event, vText

# Germany uses the "Europe/Berlin" timezone:
#   - UTC+1 in winter (CET)
#   - UTC+2 in summer (CEST, daylight saving time)
# Using a named timezone (not a fixed offset) means DST transitions are
# handled automatically. Outlook will display events at the correct local
# time regardless of the time of year.
BERLIN_TZ = pytz.timezone("Europe/Berlin")

CALENDAR_NAME = "DHBW Vorlesungsplan TINFO25"
CALENDAR_DESCRIPTION = "Automatically exported from rapla.dhbw.de"


def _make_aware(dt: datetime) -> datetime:
    """
    Attach the Europe/Berlin timezone to a naive datetime (one with no tz info).

    CS Concept --> Timezone-aware vs Naive datetimes:
    Python's datetime can be "naive" (no timezone) or "aware" (has tz info).
    iCal requires aware datetimes so Outlook knows the correct UTC equivalent.
    pytz.localize() converts naive → aware using the correct DST offset for
    that specific date — it's smarter than just adding a fixed +1h offset.
    """
    if dt.tzinfo is not None:
        return dt  # Already aware, nothing to do
    return BERLIN_TZ.localize(dt)


def build_calendar(events: list[dict]) -> Calendar:
    """
    Build an icalendar.Calendar object from a list of event dicts.

    iCalendar file structure (RFC 5545):
        BEGIN:VCALENDAR
          PRODID:...        ← identifies the software that created this file
          VERSION:2.0
          X-WR-CALNAME:...  ← calendar display name (Outlook reads this)
          BEGIN:VEVENT
            UID:...         ← globally unique ID — must be stable per event
            DTSTART;TZID=Europe/Berlin:20260127T080000
            DTEND;TZID=Europe/Berlin:20260127T100000
            SUMMARY:...     ← event title
            LOCATION:...
          END:VEVENT
          ...
        END:VCALENDAR

    The icalendar library handles serialising these blocks to the correct
    text format; we just set properties on Python objects.
    """
    cal = Calendar()

    # PRODID identifies the creator of the file (reverse-domain convention)
    cal.add("PRODID", "-//rapla-exporter//DHBW TINFO25//DE")
    cal.add("VERSION", "2.0")
    cal.add("X-WR-CALNAME", vText(CALENDAR_NAME))
    cal.add("X-WR-CALDESC", vText(CALENDAR_DESCRIPTION))
    # Tell clients to refresh every 6 hours (in seconds)
    cal.add("X-PUBLISHED-TTL", "PT6H")

    for ev in events:
        vevent = Event()

        # UID: a stable unique identifier for this event.
        # We derive it deterministically from the event data (title + start time)
        # so that re-running the exporter produces the same UIDs.  If we used
        # random UUIDs each run, Outlook would import duplicates every time.
        uid_base = f"{ev['title']}|{ev['start'].isoformat()}"
        stable_uid = str(uuid.uuid5(uuid.NAMESPACE_URL, uid_base))
        vevent.add("UID", stable_uid)

        vevent.add("SUMMARY", ev["title"])
        vevent.add("DTSTART", _make_aware(ev["start"]))
        vevent.add("DTEND", _make_aware(ev["end"]))

        if ev.get("location"):
            vevent.add("LOCATION", ev["location"])

        # DTSTAMP is required by RFC 5545. This is the timestamp when this iCal
        # object was created (i.e. now, in UTC).
        vevent.add("DTSTAMP", datetime.now(pytz.utc))

        cal.add_component(vevent)

    return cal


def write_ics(events: list[dict], output_path: str) -> Path:
    """
    Build the calendar and write it to an .ics file.

   CS Concept --> Binary vs text file I/O:
    The icalendar library's .to_ical() returns bytes (not a string) because
    iCal files must use CRLF (\\r\\n) line endings per the RFC, and encoding
    is always UTF-8.  We open the file in binary write mode ("wb") to preserve
    those exact bytes.
    """
    cal = build_calendar(events)
    path = Path(output_path)
    path.write_bytes(cal.to_ical())
    return path

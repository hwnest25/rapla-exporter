# rapla-exporter

Exports the DHBW New Study Rapla lecture calendar to the iCalendar format (`.ics`) so it can be imported into or subscribed to from any calendar app, including Microsoft Outlook, Google Calendar, and Apple Calendar.

DHBW provides timetables through [Rapla](https://rapla.dhbw.de), a web-based scheduling system. Rapla does not expose a public iCal subscription URL for student calendars, so this tool scrapes the HTML calendar view and converts it to a standards-compliant `.ics` feed.

---

## Requirements

- Python 3.9 or later
- The dependencies listed in `requirements.txt`

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Usage

There are two modes: a one-time file export and a live server.

### One-time export

Scrapes the calendar and writes a `.ics` file you can import manually.

```bash
python3 main.py --weeks 12 --start-date 2026-01-09 --output dhbw_tinfo25.ics
```

| Flag | Default | Description |
|---|---|---|
| `--weeks N` | `8` | Number of weeks to export |
| `--start-date YYYY-MM-DD` | Today | First week to include |
| `--output FILE` | `dhbw_tinfo25.ics` | Output filename |

To import into Outlook: double-click the `.ics` file, or go to **File > Open & Export > Import/Export > Import an iCalendar file**.

Note: One-time imports are static. If Rapla is updated after you import, your calendar will not reflect the change. Use the live server below for automatic updates.

### Live server (recommended)

Runs a local HTTP server. Outlook subscribes to it and polls for updates automatically, so any change in Rapla appears in your calendar within a few hours.

```bash
python3 server.py --weeks 12 --start-date 2026-01-09
```

| Flag | Default | Description |
|---|---|---|
| `--port N` | `8080` | Port to listen on |
| `--weeks N` | `12` | Number of weeks to include in the feed |
| `--start-date YYYY-MM-DD` | Today | First week to include |

The server prints a URL when it starts:

```
Rapla live server started.
  Calendar URL : http://localhost:8080/calendar.ics
```

#### Subscribing in Outlook

1. Open Outlook.
2. Go to **File > Account Settings > Account Settings**.
3. Select the **Internet Calendars** tab.
4. Click **New** and paste the URL: `http://localhost:8080/calendar.ics`
5. Click **Add**, then **Close**.

Outlook will poll the URL roughly every hour while the server is running. Every poll triggers a fresh scrape of Rapla, so cancelled or rescheduled lectures are reflected automatically.

The server must be running on your laptop for Outlook to sync. Start it before opening Outlook, or leave it running in a terminal session.

---

## Project structure

```
rapla-exporter/
├── main.py          — CLI entry point for one-time export
├── server.py        — Local HTTP server for live Outlook subscription
├── scraper.py       — Fetches and parses the Rapla HTML calendar
├── exporter.py      — Converts parsed events to RFC 5545 iCalendar format
└── requirements.txt — Python dependencies
```

---

## How it Works & Relevant Computer Science Concepts

1. **Web Scraping and HTTP Requests:** `scraper.py` sends an HTTP GET request to `rapla.dhbw.de` with the cohort's user and file parameters. No official API exists, so we fetch the raw HTML the browser would normally render.

2. **HTML/DOM Parsing and Table Geometry:** BeautifulSoup parses the HTML table. Each lecture is a `<td class="week_block">` cell. The date is inferred from the cell's column position relative to the week header row. The duration is inferred from the cell's `rowspan` value (each row represents 15 minutes). Because cells can span multiple rows and columns, the parser reconstructs the full 2D grid to correctly assign dates and durations.

3. **Regex:** Times are embedded as plain text inside each cell (e.g. `08:30 -10:00`). A regular expression extracts the start and end time regardless of minor spacing variations.

4. **Timezones and Aware Datetimes:** `exporter.py` attaches the `Europe/Berlin` timezone to every event using `pytz`. This handles daylight saving time transitions automatically, so Outlook always displays the correct local time.

5. **iCalendar Standard (RFC 5545):** Events are written as `VEVENT` blocks inside a `VCALENDAR` envelope. This is the open standard that Outlook, Google Calendar, and Apple Calendar all understand.

6. **Deterministic UUIDs:** Each event's UID is derived from its title and start time using UUID version 5. Re-running the tool produces identical UIDs for unchanged events, preventing duplicate imports.

7. **Client/Server Model and the HTTP Request/Response Cycle:** `server.py` runs a persistent local HTTP server. Outlook acts as the client, polling `http://localhost:8080/calendar.ics` on a schedule. Each request triggers a fresh scrape of Rapla and returns the result as an HTTP response with `Content-Type: text/calendar`.

---

## Limitations

- The server must be running on your machine for Outlook to sync. It is not a hosted service.
- If Rapla's HTML structure changes, the parser may need to be updated.
- The calendar user and file name are currently hardcoded in `scraper.py` for the TINFO25 cohort. To use with a different cohort, update `DEFAULT_USER` and `DEFAULT_FILE` at the top of that file.

# rapla-exporter

Exports the DHBW TINFO25 Rapla lecture calendar to the iCalendar format (`.ics`) so it can be subscribed to from any calendar app — Microsoft Outlook, Google Calendar, or Apple Calendar — with automatic updates and no duplicates.

DHBW provides timetables through [Rapla](https://rapla.dhbw.de), a web-based scheduling system. Rapla does not expose a public iCal subscription URL for student calendars, so this tool scrapes the HTML calendar view and converts it to a standards-compliant `.ics` feed.

---

## Quickstart: subscribe to the hosted feed

The easiest way to use this is to subscribe to the hosted feed. It updates automatically every Sunday — no installation, no laptop required.

**Subscription URL:**
```
https://hwnest25.github.io/rapla-exporter/dhbw_tinfo25.ics
```

Add this URL as an internet calendar subscription in your app:

**Outlook:** File > Account Settings > Internet Calendars > New > paste URL > Add

**Google Calendar:** Other calendars > + > From URL > paste URL > Add Calendar

**Apple Calendar:** File > New Calendar Subscription > paste URL > Subscribe

> **Do not import the `.ics` file manually.** Subscribe using the URL above so your app polls for updates automatically. Manual imports create duplicates; subscriptions apply only the diff.

---

## Running locally

Install dependencies first:

```bash
pip install -r requirements.txt
```

### One-time export

Scrapes the calendar and writes a `.ics` file.

```bash
python3 main.py --weeks 12 --start-date 2026-01-09 --output dhbw_tinfo25.ics
```

| Flag | Default | Description |
|------|---------|-------------|
| `--weeks N` | `8` | Number of weeks to export |
| `--start-date YYYY-MM-DD` | Today | First week to include |
| `--output FILE` | `dhbw_tinfo25.ics` | Output filename |
| `--user EMAIL` | TINFO25 default | Rapla user parameter |
| `--file NAME` | TINFO25 default | Rapla file parameter |

**Note:** One-time exports are static. If Rapla is updated after you export, your calendar will not reflect the change. Use the hosted feed above for automatic updates.

### Live server

Runs a local HTTP server that serves a fresh `.ics` on every poll. Useful for local testing or if you prefer not to use the hosted feed.

```bash
python3 server.py --weeks 12 --start-date 2026-01-09
```

| Flag | Default | Description |
|------|---------|-------------|
| `--port N` | `8080` | Port to listen on |
| `--weeks N` | `12` | Number of weeks to include |
| `--start-date YYYY-MM-DD` | Today | First week to include |
| `--user EMAIL` | TINFO25 default | Rapla user parameter |
| `--file NAME` | TINFO25 default | Rapla file parameter |

The server prints its URL on startup:
```
Rapla live server started.
  Calendar URL : http://localhost:8080/calendar.ics
```

Subscribe to that URL in your calendar app using the same steps as above, replacing the hosted URL with `http://localhost:8080/calendar.ics`.

**Note:** The server must be running on your laptop for your calendar to sync.

---

## How the hosted feed works

A GitHub Actions workflow runs every Sunday at 03:00 UTC:

1. Scrapes Rapla and writes a fresh `.ics` to `docs/dhbw_tinfo25.ics`
2. Commits and pushes the file if anything changed
3. GitHub Pages deploys the updated file to the subscription URL above

You can also trigger a manual update at any time: **Actions → Update calendar → Run workflow**.

---

## Project structure

```
rapla-exporter/
├── main.py          — CLI entry point for one-time export
├── server.py        — Local HTTP server for live calendar subscription
├── scraper.py       — Fetches and parses the Rapla HTML calendar
├── exporter.py      — Converts parsed events to RFC 5545 iCalendar format
├── requirements.txt — Python dependencies
├── docs/
│   ├── index.html             — GitHub Pages landing page
│   └── dhbw_tinfo25.ics       — Published calendar feed (updated by CI)
├── tests/
│   ├── test_scraper.py        — Offline unit tests (pytest)
│   ├── fixture_week.html      — Synthetic Rapla HTML for a normal week
│   └── fixture_year_wrap.html — Edge-case fixture for Dec→Jan year wrap
└── .github/workflows/
    └── update_calendar.yml    — Weekly scrape + GitHub Pages deployment
```

---

## How it works: relevant computer science concepts

### 1. Web scraping and HTTP requests
`scraper.py` sends an HTTP GET request to `rapla.dhbw.de` with the cohort's user and file parameters. No official API exists, so we fetch the raw HTML the browser would normally render.

### 2. HTML/DOM parsing and table geometry
BeautifulSoup parses the HTML table. Each lecture is a `<td class="week_block">` cell. The date is inferred from the cell's column position relative to the week header row. The duration is inferred from the cell's `rowspan` value (each row represents 15 minutes). Because cells can span multiple rows and columns, the parser reconstructs the full 2D grid to correctly assign dates and durations.

### 3. Regex
Times are embedded as plain text inside each cell (e.g. `08:30 -10:00`). A regular expression extracts the start and end time regardless of minor spacing variations.

### 4. Timezones and aware datetimes
`exporter.py` attaches the `Europe/Berlin` timezone to every event using `pytz`. This handles daylight saving time transitions automatically, so Outlook always displays the correct local time.

### 5. iCalendar standard (RFC 5545)
Events are written as `VEVENT` blocks inside a `VCALENDAR` envelope. This is the open standard that Outlook, Google Calendar, and Apple Calendar all understand.

### 6. Deterministic UUIDs
Each event's UID is derived from its title and start time using UUID version 5. Re-running the tool produces identical UIDs for unchanged events. This is what allows calendar apps to apply updates without creating duplicates — the app matches on UID and updates in place.

### 7. Client/server model and the HTTP request/response cycle
`server.py` runs a persistent local HTTP server. Outlook acts as the client, polling the URL on a schedule. Each request triggers a fresh scrape of Rapla and returns the result as an HTTP response with `Content-Type: text/calendar`.

---

## Limitations

- The hosted feed refreshes weekly. For same-day changes, trigger a manual run from the Actions tab.
- If Rapla's HTML structure changes, the parser may need to be updated.
- To use with a different cohort, pass `--user` and `--file` flags with the appropriate Rapla parameters.

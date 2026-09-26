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

## Usage (There are two modes): 
1. One-time file export
2. Live server.

### 1. One-time export
Scrapes the calendar and writes a `.ics` file you can import manually.

```bash
python3 main.py --weeks 12 --start-date 2026-01-09 --output dhbw_tinfo25.ics
```

| Flag | Default | Description |
|---|---|---|
| `--weeks N` | `8` | Number of weeks to export |
| `--start-date YYYY-MM-DD` | Today | First week to include |
| `--output FILE` | `dhbw_tinfo25.ics` | Output filename |

#### To import into your calendar application (Outlook, Google Calendar, Apple Calendar, etc): 
- Double-click the `.ics` file, or go to **File > Open & Export > Import/Export > Import an iCalendar file**.

**Note:** One-time imports are static. If Rapla is updated after you import, your calendar will not reflect the change. Use the live server mode/options below if you prefer automatic updates.

### 2. Live server (recommended):
Rapla does not provide an iCalendar subscription URL, so calendar apps like Outlook, Google Calendar, and Apple Calendar have no way to subscribe directly. This mode solves that by running a local HTTP server that exposes a subscription URL (`http://localhost:8080/calendar.ics`) which calendar apps can subscribe to and poll for updates automatically. Any change in Rapla then appears in your calendar within a few hours.

**Important:** Simply opening the URL in a browser does nothing useful. The URL must be added as a calendar subscription (see instructions below). **The server must also be running on your laptop whenever you want your calendar to sync.**

```bash
python3 server.py --weeks 12 --start-date 2026-01-09
```

| Flag | Default | Description |
|---|---|---|
| `--port N` | `8080` | Port to listen on |
| `--weeks N` | `12` | Number of weeks to include in the feed |
| `--start-date YYYY-MM-DD` | Today | First week to include |

#### The server prints a URL when it starts:
```
Rapla live server started.
  Calendar URL : http://localhost:8080/calendar.ics
```

#### Subscribing in Outlook:
The exact steps vary by Outlook version. In classic Outlook:
1. Open Outlook.
2. Go to **File > Account Settings > Account Settings**.
3. Select the **Internet Calendars** tab.
4. Click **New** and paste the URL: `http://localhost:8080/calendar.ics`
5. Click **Add**, then **Close**.

**Note:** If the Internet Calendars tab is not visible, the current organizational IT policy may have disabled external calendar subscriptions. In that case, use the one-time export option (Mode 1) instead.

In the Live Server Mode, Outlook or your calendar of choice, will poll the URL roughly every hour while the server is running. Every poll triggers a fresh scrape of Rapla, so cancelled or rescheduled lectures are reflected automatically.

**NOTE:** The server must be running on your laptop for your calendar to sync. Start the server before opening Outlook (Google Calendar, or Apple Calendar), or leave it running in a terminal session.

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

## How it Works & Relevant Computer Science Concepts

### 1. **Web Scraping and HTTP Requests:** 
`scraper.py` sends an HTTP GET request to `rapla.dhbw.de` with the cohort's user and file parameters. No official API exists, so we fetch the raw HTML the browser would normally render.

### 2. **HTML/DOM Parsing and Table Geometry:** 
BeautifulSoup parses the HTML table. Each lecture is a `<td class="week_block">` cell. The date is inferred from the cell's column position relative to the week header row. The duration is inferred from the cell's `rowspan` value (each row represents 15 minutes). Because cells can span multiple rows and columns, the parser reconstructs the full 2D grid to correctly assign dates and durations.

### 3. **Regex:** 
Times are embedded as plain text inside each cell (e.g. `08:30 -10:00`). A regular expression extracts the start and end time regardless of minor spacing variations.

### 4. **Timezones and Aware Datetimes:** 
`exporter.py` attaches the `Europe/Berlin` timezone to every event using `pytz`. This handles daylight saving time transitions automatically, so Outlook always displays the correct local time.

### 5. **iCalendar Standard (RFC 5545):** 
Events are written as `VEVENT` blocks inside a `VCALENDAR` envelope. This is the open standard that Outlook, Google Calendar, and Apple Calendar all understand.

### 6. **Deterministic UUIDs:** 
Each event's UID is derived from its title and start time using UUID version 5. Re-running the tool produces identical UIDs for unchanged events, preventing duplicate imports.

### 7. **Client/Server Model and the HTTP Request/Response Cycle:** 
`server.py` runs a persistent local HTTP server. Outlook acts as the client, polling `http://localhost:8080/calendar.ics` on a schedule. Each request triggers a fresh scrape of Rapla and returns the result as an HTTP response with `Content-Type: text/calendar`.

---

## Hosted calendar feed (GitHub Actions + GitHub Pages)

The repo includes a GitHub Actions workflow that scrapes Rapla on a weekly schedule and publishes a fresh `.ics` file to GitHub Pages. This gives you a **stable public subscription URL** — no laptop required.

### How it works

1. Every Sunday at 03:00 UTC, the workflow runs `main.py` and writes the result to `docs/dhbw_tinfo25.ics`.
2. If the calendar changed, it commits the new file and pushes.
3. GitHub Pages serves the file at:

   ```
   https://YOUR_GITHUB_USERNAME.github.io/rapla-exporter/dhbw_tinfo25.ics
   ```

4. You add that URL **once** as a calendar subscription. Your app polls it automatically and applies only the diff — no duplicates.

You can also trigger a manual update at any time via **Actions → Update calendar → Run workflow**.

### Setup (one-time)

**1. Add secrets**

Go to your repo → Settings → Secrets and variables → Actions → New repository secret.

Add two secrets:

| Name | Value |
|------|-------|
| `RAPLA_USER` | The Rapla user email (e.g. `Britta.konrath@intern.mosbach.dhbw.de`) |
| `RAPLA_FILE` | The Rapla file name (e.g. `Vorlesungsplan TINFO25`) |

**2. Enable GitHub Pages**

Go to your repo → Settings → Pages → Source → select **GitHub Actions**.

**3. Subscribe in your calendar app**

Replace `YOUR_GITHUB_USERNAME` with your actual username in the URL above, then add it as an internet calendar subscription (see [Usage](#usage-there-are-two-modes) above for app-specific steps).

---

## Limitations

- If Rapla's HTML structure changes, the parser may need to be updated.
- The hosted feed refreshes weekly. For same-day changes, trigger a manual run from the Actions tab or run `main.py` locally.

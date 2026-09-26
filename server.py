"""
server.py: A local HTTP server that serves the Rapla calendar as a live .ics feed.

CS Concept --> Client/Server Model: Instead of producing a static file once,
we run a persistent process that listens for incoming HTTP requests. Outlook
acts as the client: it polls our server URL on a schedule (typically every few
hours) and receives a freshly scraped .ics response each time. This means any
change made in Rapla automatically appears in Outlook on the next poll, with
no manual re-export needed.

CS Concept --> HTTP Request/Response Cycle: Every poll from Outlook is a
standard HTTP GET request. Our server responds with the correct Content-Type
header ("text/calendar") and the .ics bytes as the response body. Outlook
reads the Content-Type to know how to interpret the data.

Usage:
    python3 server.py
    python3 server.py --port 8080 --weeks 12 --start-date 2026-01-09

Then in Outlook: File > Account Settings > Internet Calendars > New
Enter: http://localhost:8080/calendar.ics
"""

import argparse
import sys
import traceback
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from exporter import build_calendar
from scraper import scrape_weeks, DEFAULT_USER, DEFAULT_FILE

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_PORT = 8080
DEFAULT_WEEKS = 12
CALENDAR_PATH = "/calendar.ics"


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------

class RaplaHandler(BaseHTTPRequestHandler):
    """
    Handles each incoming HTTP GET request.

    CS Concept --> Inheritance and Polymorphism: Python's standard library
    provides BaseHTTPRequestHandler with the full HTTP parsing logic already
    built in. We subclass it and override only do_GET, the method called for
    every GET request. Everything else (reading headers, managing the socket,
    sending the status line) is handled by the parent class.
    """

    # These are set on the class by the factory function below so each
    # handler instance can access the CLI arguments without globals.
    start_date: date = None
    num_weeks: int = DEFAULT_WEEKS
    rapla_user: str = DEFAULT_USER
    rapla_file: str = DEFAULT_FILE

    def do_GET(self):
        if self.path != CALENDAR_PATH:
            self._send(404, "text/plain", b"Not found. Use /calendar.ics")
            return

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Outlook polled. Scraping Rapla ...")
        try:
            events = scrape_weeks(self.start_date, self.num_weeks, user=self.rapla_user, file=self.rapla_file)
            events.sort(key=lambda e: e["start"])
            cal_bytes = build_calendar(events).to_ical()
            self._send(200, "text/calendar; charset=utf-8", cal_bytes)
            print(f"  Served {len(events)} events.")
        except Exception:
            traceback.print_exc()
            self._send(500, "text/plain", b"Error scraping Rapla. Check the terminal.")

    def _send(self, status: int, content_type: str, body: bytes):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Suppress the default Apache-style access log so our own print()
        # messages stay readable.
        pass


# ---------------------------------------------------------------------------
# CLI and server startup
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        prog="rapla-server",
        description="Serve the DHBW TINFO25 Rapla calendar as a live iCal feed.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to listen on (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=DEFAULT_WEEKS,
        metavar="N",
        help=f"Number of weeks to include in the feed (default: {DEFAULT_WEEKS})",
    )
    parser.add_argument(
        "--start-date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=date.today(),
        metavar="YYYY-MM-DD",
        help="First day to export from (default: today)",
    )
    parser.add_argument(
        "--user",
        default=DEFAULT_USER,
        metavar="EMAIL",
        help=f"Rapla user parameter (default: {DEFAULT_USER})",
    )
    parser.add_argument(
        "--file",
        default=DEFAULT_FILE,
        metavar="NAME",
        help=f"Rapla file parameter (default: {DEFAULT_FILE})",
    )
    return parser.parse_args()


def make_handler(start_date: date, num_weeks: int, rapla_user: str, rapla_file: str):
    """
    CS Concept --> Factory Function / Closure: HTTPServer requires a handler
    class, not an instance, so we cannot pass arguments via __init__. Instead,
    we create a fresh subclass at runtime with the configuration baked in as
    class attributes. This is a common pattern when working with frameworks
    that control object construction.
    """
    class ConfiguredHandler(RaplaHandler):
        pass

    ConfiguredHandler.start_date = start_date
    ConfiguredHandler.num_weeks = num_weeks
    ConfiguredHandler.rapla_user = rapla_user
    ConfiguredHandler.rapla_file = rapla_file
    return ConfiguredHandler


def main():
    args = parse_args()

    handler_class = make_handler(args.start_date, args.weeks, args.user, args.file)
    server = HTTPServer(("localhost", args.port), handler_class)

    url = f"http://localhost:{args.port}{CALENDAR_PATH}"
    print(f"Rapla live server started.")
    print(f"  Calendar URL : {url}")
    print(f"  Start date   : {args.start_date.isoformat()}")
    print(f"  Weeks        : {args.weeks}")
    print()
    print("Add this URL to Outlook:")
    print("  File > Account Settings > Internet Calendars > New")
    print(f"  {url}")
    print()
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()

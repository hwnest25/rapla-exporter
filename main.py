"""
This main.py is the CLI entry point for the Rapla → iCal exporter.

CS Concept --> Argparse:
argparse is Python's standard library for building command-line interfaces.
It parses sys.argv (the list of strings the shell passes to Python), validates
types, and generates --help documentation automatically.

Usage examples:
    # Export the next 4 weeks starting today
    python main.py --weeks 4

    # Export 8 weeks starting from a specific date
    python main.py --weeks 8 --start-date 2026-01-27

    # Save to a custom filename
    python main.py --weeks 4 --output my_lectures.ics
"""

import argparse
import sys
from datetime import date, datetime

from scraper import scrape_weeks
from exporter import write_ics


def parse_args():
    parser = argparse.ArgumentParser(
        prog="rapla-exporter",
        description="Export the DHBW TINFO25 Rapla calendar to an Outlook-compatible .ics file.",
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=8,
        metavar="N",
        help="Number of weeks to export (default: 8)",
    )
    parser.add_argument(
        "--start-date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=date.today(),
        metavar="YYYY-MM-DD",
        help="First day to export from (default: today)",
    )
    parser.add_argument(
        "--output",
        default="dhbw_tinfo25.ics",
        metavar="FILE",
        help="Output .ics filename (default: dhbw_tinfo25.ics)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print(f"Rapla Exporter: DHBW TINFO25")
    print(f"  Start date : {args.start_date.isoformat()}")
    print(f"  Weeks      : {args.weeks}")
    print(f"  Output     : {args.output}")
    print()

    print("Fetching calendar data from rapla.dhbw.de ...")
    try:
        events = scrape_weeks(args.start_date, args.weeks)
    except Exception as e:
        print(f"Error fetching calendar: {e}", file=sys.stderr)
        sys.exit(1)

    if not events:
        print("No events found. The calendar may be empty for this date range.")
        sys.exit(0)

    # Sort events chronologically before writing
    events.sort(key=lambda e: e["start"])

    print(f"\nFound {len(events)} events. Writing to {args.output} ...")
    output_path = write_ics(events, args.output)
    print(f"Done! File written to: {output_path.resolve()}")
    print()
    print("To import into Outlook:")
    print("  File > Open & Export > Import/Export > Import an iCalendar (.ics) file")
    print("  — or —")
    print("  Double-click the .ics file to open it directly in Outlook.")


if __name__ == "__main__":
    main()

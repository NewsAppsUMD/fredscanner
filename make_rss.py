"""Create an RSS feed with the latest alerts."""
from __future__ import annotations

import csv
from collections import Counter
from operator import itemgetter
from pathlib import Path
import shutil

import dateutil.parser
from feedgen.entry import FeedEntry
from feedgen.feed import FeedGenerator
import pytz
from datetime import datetime

# Set directories we'll use
THIS_DIR = Path(__file__).parent.absolute()

# An incident is "priority" if it's a large response, on the working-fire
# radio channel, or an event type that's historically rare.
UNIT_COUNT_THRESHOLD = 10
RARE_EVENT_THRESHOLD = 20
WORKING_FIRE_RADIO = "Radio: 9D"


def unit_count(units: str) -> int:
    """Count the responding units listed in a Units field value."""
    marker = "Units:"
    if marker not in units:
        return 0
    unit_list = units.split(marker, 1)[1]
    return len([u for u in unit_list.split(",") if u.strip()])


def is_priority(row: dict, event_counts: Counter) -> bool:
    """Decide whether an incident is worth flagging for reporters."""
    if unit_count(row["Units"]) >= UNIT_COUNT_THRESHOLD:
        return True
    if WORKING_FIRE_RADIO in row["Units"]:
        return True
    if event_counts[row["Event"]] < RARE_EVENT_THRESHOLD:
        return True
    return False


def build_feed(title: str, description: str, entries: list[dict]) -> FeedGenerator:
    """Build a feed from a list of incident rows."""
    feed = FeedGenerator()
    feed.title(title)
    feed.link(href="https://github.com/NewsAppsUMD/fredscanner")
    feed.description(description)
    eastern_tz = pytz.timezone("US/Eastern")
    for r in entries:
        date_time = datetime.strptime(r["Datetime"], "%Y-%m-%d %H:%M:%S")
        date_time_eastern = eastern_tz.localize(date_time)
        entry = FeedEntry()
        entry.id(r["Datetime"])
        entry.title(r["Event"] + ": " + r["Time"])
        entry.published(date_time_eastern)
        entry.description(r["Location"] + ' ' + r["Units"])
        feed.add_entry(entry, order="append")
    return feed


def main():
    """Create an RSS feed with the latest alerts."""
    # Get data
    with open(THIS_DIR / "incidents.csv") as f:
        data = list(csv.DictReader(f))

    # Parse dates
    for r in data:
        r["discovered"] = dateutil.parser.isoparse(r["Datetime"])

    # Sort reverse chronological
    sorted_data = sorted(
        data,
        key=itemgetter("Datetime"),
        reverse=True,
    )

    # Latest-alerts feed: the 50 most recent incidents, unfiltered
    feed = build_feed(
        "Latest alerts from fredscanner.com",
        "An unofficial feed created by Derek Willis.",
        sorted_data[:50],
    )
    feed.rss_file(THIS_DIR / "site" / "latest.rss", pretty=True)

    # Priority-alerts feed: large responses, working fires, and rare event
    # types, drawn from a wider recent window since they're sparser.
    event_counts = Counter(r["Event"] for r in data)
    priority_entries = [r for r in sorted_data[:200] if is_priority(r, event_counts)][:50]
    priority_feed = build_feed(
        "Priority alerts from fredscanner.com",
        "Large responses, working fires, and rare incident types from Frederick County Fire & Rescue.",
        priority_entries,
    )
    priority_feed.rss_file(THIS_DIR / "site" / "priority.rss", pretty=True)

    # Copy incidents.csv to site directory for the dashboard
    shutil.copy2(THIS_DIR / "incidents.csv", THIS_DIR / "site" / "incidents.csv")


if __name__ == "__main__":
    main()
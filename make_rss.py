"""Create an RSS feed with the latest alerts."""
from __future__ import annotations

import csv
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

    # Create feed
    feed = FeedGenerator()
    feed.title("Latest alerts from fredscanner.com")
    feed.link(href="https://github.com/NewsAppsUMD/fredscanner")
    feed.description("An unofficial feed created by Derek Willis.")
    eastern_tz = pytz.timezone("US/Eastern")
    for r in sorted_data[:50]:
        date_time = datetime.strptime(r["Datetime"], "%Y-%m-%d %H:%M:%S")
        date_time_eastern = eastern_tz.localize(date_time)
        entry = FeedEntry()
        entry.id(r["Datetime"])
        entry.title(r["Event"] + ": " + r["Time"])
        entry.published(date_time_eastern)
        entry.description(r["Location"] + ' ' + r["Units"])
        feed.add_entry(entry, order="append")

    # Write it out
    feed.rss_file(THIS_DIR / "site" / "latest.rss", pretty=True)

    # Copy incidents.csv to site directory for the dashboard
    shutil.copy2(THIS_DIR / "incidents.csv", THIS_DIR / "site" / "incidents.csv")


if __name__ == "__main__":
    main()
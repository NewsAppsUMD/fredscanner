"""Create RSS feeds with the latest alerts."""
from __future__ import annotations

import csv
from collections import Counter
from operator import itemgetter
from pathlib import Path

from feedgen.entry import FeedEntry
from feedgen.feed import FeedGenerator
import pytz
from datetime import datetime

from threads import assign_threads

# Set directories we'll use
THIS_DIR = Path(__file__).parent.absolute()

# A thread is "priority" if it's a large response, on the working-fire
# radio channel, or an event type that's historically rare.
UNIT_COUNT_THRESHOLD = 10
RARE_EVENT_THRESHOLD = 20
WORKING_FIRE_RADIO = "9D"

EASTERN = pytz.timezone("US/Eastern")


def is_priority_thread(thread: dict, event_counts: Counter) -> bool:
    """Decide whether a thread is worth flagging for reporters."""
    if len(thread["unit_union"]) >= UNIT_COUNT_THRESHOLD:
        return True
    if WORKING_FIRE_RADIO in thread["channels"]:
        return True
    if event_counts[thread["headline_event"]] < RARE_EVENT_THRESHOLD:
        return True
    return False


def build_feed(title: str, description: str, entries: list[dict]) -> FeedGenerator:
    """Build a feed from a list of individual incident posts."""
    feed = FeedGenerator()
    feed.title(title)
    feed.link(href="https://github.com/NewsAppsUMD/fredscanner")
    feed.description(description)
    for r in entries:
        date_time = datetime.strptime(r["Datetime"], "%Y-%m-%d %H:%M:%S")
        entry = FeedEntry()
        entry.id(r["Datetime"])
        entry.title(r["Event"] + ": " + r["Time"])
        entry.published(EASTERN.localize(date_time))
        entry.description(r["Location"] + ' ' + r["Units"])
        feed.add_entry(entry, order="append")
    return feed


def build_thread_feed(title: str, description: str, threads: list[dict]) -> FeedGenerator:
    """Build a feed from incident threads, one entry per thread.

    Each entry's guid is the thread id, which is stable across rebuilds, so
    feed readers treat a growing incident as an updated item rather than a
    new duplicate. The published date is the thread's last update, so an
    escalating incident resurfaces at the top of the feed.
    """
    feed = FeedGenerator()
    feed.title(title)
    feed.link(href="https://github.com/NewsAppsUMD/fredscanner")
    feed.description(description)
    for t in threads:
        date_time = datetime.strptime(t["last_updated"], "%Y-%m-%d %H:%M:%S")
        entry = FeedEntry()
        entry.id(t["id"])
        title_text = f"{t['headline_event']}: {t['first_time']}"
        description_text = f"{t['location']} — units: {', '.join(t['unit_union'])}"
        if t["post_count"] > 1:
            title_text += f" ({len(t['unit_union'])} units, {t['post_count']} updates)"
            description_text += f" (first reported {t['first_time']})"
        entry.title(title_text)
        entry.published(EASTERN.localize(date_time))
        entry.description(description_text)
        feed.add_entry(entry, order="append")
    return feed


def main():
    """Create RSS feeds with the latest alerts."""
    # Get data
    with open(THIS_DIR / "incidents.csv") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        data = list(reader)

    event_counts = Counter(r["Event"] for r in data)
    rows, threads = assign_threads(data)

    # Sort reverse chronological
    sorted_rows = sorted(rows, key=itemgetter("Datetime"), reverse=True)
    sorted_threads = sorted(threads, key=itemgetter("last_updated"), reverse=True)

    # Latest-alerts feed: the 50 most recent individual posts, unfiltered
    feed = build_feed(
        "Latest alerts from fredscanner.com",
        "An unofficial feed created by Derek Willis.",
        sorted_rows[:50],
    )
    feed.rss_file(THIS_DIR / "site" / "latest.rss", pretty=True)

    # Priority-alerts feed: large responses, working fires, and rare event
    # types, one entry per incident thread, drawn from a wider recent
    # window since qualifying threads are sparser than raw posts.
    priority_threads = [t for t in sorted_threads[:200] if is_priority_thread(t, event_counts)][:50]
    priority_feed = build_thread_feed(
        "Priority alerts from fredscanner.com",
        "Large responses, working fires, and rare incident types from Frederick County Fire & Rescue.",
        priority_threads,
    )
    priority_feed.rss_file(THIS_DIR / "site" / "priority.rss", pretty=True)

    # Copy incidents.csv to the site directory for the dashboard, with an
    # added ThreadID column so the dashboard can group posts into incidents.
    # The raw incidents.csv in the repo is left untouched.
    with open(THIS_DIR / "site" / "incidents.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames) + ["ThreadID"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()

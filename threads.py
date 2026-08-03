"""Group repeat CAD posts for the same incident into threads.

The source site re-posts an incident every time its dispatch changes (units
added, event reclassified). This groups those re-posts so counts, feeds, and
the dashboard reflect one incident instead of every post about it.
"""
from __future__ import annotations

import re
from datetime import datetime

GAP_MINUTES = 60
SPAN_CAP_MINUTES = 120

# Events that are never chained into a thread with anything else -- each
# post is its own incident. These are administrative, not dispatches.
NEVER_THREAD_EVENT_KEYWORDS = ("TRANSFER TO OTHER STATION", "TEST CALL", "TEST EVENT", "DETAIL")

# Locations where nearly all measured over-merge risk concentrates
# (station move-ups, training burns) -- never chain posts here.
NEVER_THREAD_LOCATION_RE = re.compile(r",\s*STATION\s+\d+|PUBLIC SAFETY PL")

# Events that can plausibly follow (or precede) any other event at the same
# location without it being a miscategorized merge -- e.g. an incident that
# gets closed out as a service call.
FLEXIBLE_EVENT_PREFIXES = ("MUTUAL AID", "SERVICE CALL", "INVESTIGATION", "CHECK UP AFTER ACCIDENT")

# Category pairs that represent a plausible escalation/reclassification of
# the same incident, even though the coarse category differs.
ESCALATION_PAIRS = {
    frozenset(("alarm", "structure_fire")),
    frozenset(("hazmat_odor", "structure_fire")),
    frozenset(("outside_fire", "structure_fire")),
    frozenset(("accident", "rescue")),
    frozenset(("accident", "ems")),
}

# Radio-channel tokens (e.g. "9C", "91C") that leak into the unit list.
RADIO_TOKEN_RE = re.compile(r"^9\d*[A-Z]?$")
RADIO_MARKER_RE = re.compile(r"Radio:\s*(\S+)")


def parse_units(units_str: str) -> list[str]:
    """Parse a Units field into a list of responding-unit tokens.

    Handles the three source formats ("Units: ...", "Radio: 9C Units: ...",
    and a few rows with a glued "LL: <lat>, <lon>Radio: ... Units: ..."
    prefix) by splitting on the last "Units:" occurrence, and strips
    radio-channel tokens that otherwise leak into the unit list.
    """
    if not units_str:
        return []
    marker = "Units:"
    idx = units_str.rfind(marker)
    if idx == -1:
        return []
    unit_list = units_str[idx + len(marker):]
    tokens = [u.strip() for u in unit_list.split(",") if u.strip()]
    return [t for t in tokens if not RADIO_TOKEN_RE.match(t)]


def extract_radio_channel(units_str: str) -> str | None:
    """Extract the radio talkgroup (e.g. "9D") from a Units field, if present."""
    match = RADIO_MARKER_RE.search(units_str or "")
    return match.group(1) if match else None


def categorize(event: str) -> str:
    """Bucket an event string into a coarse category for thread-chaining."""
    e = event.upper()
    if e.startswith(FLEXIBLE_EVENT_PREFIXES):
        return "flexible"
    if "ALARM" in e:
        return "alarm"
    if "HOUSE FIRE" in e or "BUILDING FIRE" in e or "APARTMENT FIRE" in e or "STRUCTURE FIRE" in e or "STRUCTURAL COLLAPSE" in e:
        return "structure_fire"
    if "OUTSIDE FIRE" in e or "BRUSH FIRE" in e or "GRASS FIRE" in e or "WOODS FIRE" in e:
        return "outside_fire"
    if "VEHICLE FIRE" in e:
        return "vehicle_fire"
    if "HELICOPTER" in e or "LANDING ZONE" in e or e.endswith(" LZ"):
        return "helo_lz"
    if "ACCIDENT" in e or "PEDESTRIAN" in e or "STRUCK" in e:
        return "accident"
    if "RESCUE" in e:
        return "rescue"
    if "ALS" in e or "BLS" in e or "MEDICAL" in e or "EMS" in e or "SHOOTING" in e or "STABBING" in e or "OVERDOSE" in e:
        return "ems"
    if "GAS" in e or "HAZMAT" in e or "HAZARDOUS" in e or "ODOR" in e or "CO DET" in e or "CARBON MONOXIDE" in e or "FUEL SPILL" in e or "WIRES DOWN" in e or "FLOOD" in e or "LIGHTNING" in e:
        return "hazmat_odor"
    return "admin_other"


def is_never_threaded(row: dict) -> bool:
    """Whether a post should always be its own thread."""
    event = row["Event"].upper()
    location = row["Location"].upper()
    if any(keyword in event for keyword in NEVER_THREAD_EVENT_KEYWORDS):
        return True
    return bool(NEVER_THREAD_LOCATION_RE.search(location))


def categories_compatible(cat_a: str, cat_b: str) -> bool:
    if cat_a == cat_b:
        return True
    if cat_a == "flexible" or cat_b == "flexible":
        return True
    return frozenset((cat_a, cat_b)) in ESCALATION_PAIRS


def assign_threads(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Group re-posts of the same incident into threads.

    Takes a list of CSV row dicts (each with Time, Event, Location, Units,
    Date, Datetime) and returns (rows, threads):
      - rows: the deduplicated input rows, each with an added "ThreadID" key
      - threads: a list of dicts with id, location, first_seen, last_updated,
        first_time, last_time, post_count, unit_union, channels,
        headline_event
    """
    # Drop exact duplicate posts, keeping the first occurrence in file order.
    seen = set()
    deduped = []
    for index, row in enumerate(rows):
        key = (row["Datetime"], row["Event"], row["Location"], row["Units"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append((index, row))

    # Stable sort by (Datetime, original index) so equal timestamps don't
    # reorder unpredictably between runs.
    deduped.sort(key=lambda pair: (pair[1]["Datetime"], pair[0]))

    open_threads: dict[str, dict] = {}  # location -> in-progress thread
    threads: list[dict] = []

    for _, row in deduped:
        location = row["Location"]
        post_dt = datetime.strptime(row["Datetime"], "%Y-%m-%d %H:%M:%S")
        category = categorize(row["Event"])
        never_threaded = is_never_threaded(row)

        thread = None
        if not never_threaded:
            candidate = open_threads.get(location)
            if candidate is not None:
                gap = (post_dt - candidate["_last_dt"]).total_seconds() / 60
                span = (post_dt - candidate["_first_dt"]).total_seconds() / 60
                if (
                    gap <= GAP_MINUTES
                    and span <= SPAN_CAP_MINUTES
                    and categories_compatible(candidate["_last_category"], category)
                ):
                    thread = candidate

        if thread is None:
            thread = {
                "id": f"{row['Datetime']}|{location}",
                "location": location,
                "first_seen": row["Datetime"],
                "last_updated": row["Datetime"],
                "first_time": row["Time"],
                "last_time": row["Time"],
                "post_count": 0,
                "unit_union": [],
                "channels": [],
                "headline_event": row["Event"],
                "_last_dt": post_dt,
                "_first_dt": post_dt,
                "_last_category": category,
                "_headline_unit_count": -1,
            }
            threads.append(thread)
            if not never_threaded:
                open_threads[location] = thread

        row["ThreadID"] = thread["id"]
        thread["last_updated"] = row["Datetime"]
        thread["last_time"] = row["Time"]
        thread["_last_dt"] = post_dt
        thread["_last_category"] = category
        thread["post_count"] += 1

        for unit in parse_units(row["Units"]):
            if unit not in thread["unit_union"]:
                thread["unit_union"].append(unit)

        channel = extract_radio_channel(row["Units"])
        if channel and channel not in thread["channels"]:
            thread["channels"].append(channel)

        unit_count = len(parse_units(row["Units"]))
        if unit_count >= thread["_headline_unit_count"]:
            thread["_headline_unit_count"] = unit_count
            thread["headline_event"] = row["Event"]

    for thread in threads:
        del thread["_last_dt"], thread["_first_dt"], thread["_last_category"], thread["_headline_unit_count"]

    result_rows = [row for _, row in deduped]
    return result_rows, threads

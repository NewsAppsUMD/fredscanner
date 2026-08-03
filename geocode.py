"""Geocode incident locations for the map view.

Uses the Census Bureau's free Geocoding Services API
(https://geocoding.geo.census.gov/geocoder/), which needs no API key.
Locations here are CAD dispatch strings, not mailing addresses, so they
need cleaning first: "BLOCK" addresses become an approximate street
number, landmark/apartment text appended after a comma is dropped, and
intersections use "&" instead of "/". Highway locations that only carry a
mile marker (no named cross street) have no street to look up and are
skipped entirely -- those are covered separately by the Highway Hotspots
dashboard panel.

Results are cached in geocode_cache.csv, keyed by the exact raw Location
string, and a location is never re-queried once it's been attempted --
including a failed match, so an unmappable address isn't retried forever.
A location is only left out of the cache (and retried next run) if the
attempt itself failed for a transient reason (network error, timeout,
non-2xx response) rather than the geocoder returning a clean "no match".
"""
from __future__ import annotations

import csv
import io
import re
import sys
from pathlib import Path

import requests

THIS_DIR = Path(__file__).parent.absolute()
INCIDENTS_FILE = THIS_DIR / "incidents.csv"
CACHE_FILE = THIS_DIR / "geocode_cache.csv"
CACHE_FIELDNAMES = ["Location", "Lat", "Lon", "Status"]

GEOCODER_ONE_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
GEOCODER_BATCH_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
BENCHMARK = "Public_AR_Current"
STATE = "MD"
REQUEST_TIMEOUT = 30
BATCH_SIZE = 9000  # Census batch endpoint caps at 10,000 records/request
BATCH_THRESHOLD = 20  # below this, geocoding one at a time is simpler and fine

MILE_MARKER_RE = re.compile(r'\d+\s?MM\b', re.IGNORECASE)
BLOCK_RE = re.compile(r'\bBLOCK\b', re.IGNORECASE)
SLASH_RE = re.compile(r'\s*/\s*')
WHITESPACE_RE = re.compile(r'\s+')


def clean_for_geocoding(location: str) -> str | None:
    """Convert a raw dispatch Location string into a street address
    suitable for geocoding (no city/state/zip -- callers add those per
    the geocoder endpoint's expected format), or None if the location
    can't reasonably be geocoded.
    """
    # Landmark, apartment/unit, and building text is appended after the
    # first comma and isn't part of the street address.
    text = location.split(",")[0].strip()

    # A bare mile marker (e.g. "38MM") isn't a street and actively
    # confuses a geocoder if passed through -- these are covered by the
    # Highway Hotspots panel instead.
    if MILE_MARKER_RE.search(text):
        return None

    text = BLOCK_RE.sub('', text)
    text = SLASH_RE.sub(' & ', text)
    text = WHITESPACE_RE.sub(' ', text).strip()
    return text or None


def read_cache() -> dict[str, dict]:
    """Read the geocode cache into a dict keyed by raw Location string."""
    cache = {}
    try:
        with open(CACHE_FILE, "r", newline="") as f:
            for row in csv.DictReader(f):
                cache[row["Location"]] = row
    except FileNotFoundError:
        pass
    return cache


def append_to_cache(rows: list[dict]) -> None:
    """Append newly-resolved rows to the cache file, creating it (with a
    header) if it doesn't exist yet."""
    if not rows:
        return
    file_exists = CACHE_FILE.exists()
    with open(CACHE_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CACHE_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def geocode_one(street: str) -> tuple[float, float] | None:
    """Geocode a single cleaned street address via the Census one-line
    address endpoint. Returns (lat, lon) on a match, None on a clean
    "no match". Raises requests.RequestException on a network/HTTP
    error -- callers should treat that as transient and not cache it,
    so the location is retried on the next run.
    """
    one_line = f"{street}, Frederick County, {STATE}"
    response = requests.get(
        GEOCODER_ONE_URL,
        params={"address": one_line, "benchmark": BENCHMARK, "format": "json"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    matches = response.json()["result"]["addressMatches"]
    if not matches:
        return None
    coords = matches[0]["coordinates"]
    return (coords["y"], coords["x"])


def geocode_batch(id_to_street: dict[str, str]) -> dict[str, tuple[float, float] | None]:
    """Geocode many addresses in one request via the Census batch
    endpoint (accepts up to 10,000 records per call). Returns a dict
    mapping each input id to (lat, lon) on a match or None on no match.
    Raises requests.RequestException on a network/HTTP error for the
    whole batch -- callers should treat the entire batch as transient
    and retry it, rather than assuming any of it failed to match.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for record_id, street in id_to_street.items():
        # Batch format: Unique ID, Street address, City, State, ZIP.
        # City/ZIP are left blank -- dispatch locations span multiple
        # towns within the county and we don't have city info per row.
        writer.writerow([record_id, street, "", STATE, ""])
    payload = buffer.getvalue()

    response = requests.post(
        GEOCODER_BATCH_URL,
        data={"benchmark": BENCHMARK},
        files={"addressFile": ("addresses.csv", payload, "text/csv")},
        timeout=REQUEST_TIMEOUT * 4,
    )
    response.raise_for_status()

    results = {}
    reader = csv.reader(response.text.splitlines())
    for row in reader:
        if len(row) < 6:
            continue
        record_id, _input_address, match_status = row[0], row[1], row[2]
        if match_status == "Match":
            lon, lat = row[5].split(",")
            results[record_id] = (float(lat), float(lon))
        else:
            results[record_id] = None
    return results


def find_new_locations(incidents_file: Path = INCIDENTS_FILE) -> list[str]:
    """Distinct Location values from incidents.csv not yet in the cache."""
    with open(incidents_file) as f:
        distinct = sorted({row["Location"] for row in csv.DictReader(f)})
    cache = read_cache()
    return [loc for loc in distinct if loc not in cache]


def geocode_locations(locations: list[str]) -> None:
    """Geocode a list of raw Location strings and append results to the
    cache. Locations clean_for_geocoding() can't handle are cached
    immediately as "Skipped" with no API call. The rest are geocoded via
    the batch endpoint (chunked to the API's per-request cap) when there
    are enough to be worth a batch call, or one at a time otherwise --
    which means this same function naturally handles both the one-time
    historical backfill (thousands of candidates) and routine incremental
    runs (usually a handful of newly-seen locations).
    """
    to_cache = []
    candidates = []  # list of (raw_location, cleaned_street)
    for location in locations:
        cleaned = clean_for_geocoding(location)
        if cleaned is None:
            to_cache.append({"Location": location, "Lat": "", "Lon": "", "Status": "Skipped"})
        else:
            candidates.append((location, cleaned))

    if len(candidates) >= BATCH_THRESHOLD:
        for chunk_start in range(0, len(candidates), BATCH_SIZE):
            chunk = candidates[chunk_start:chunk_start + BATCH_SIZE]
            id_to_street = {str(i): street for i, (_location, street) in enumerate(chunk)}
            try:
                results = geocode_batch(id_to_street)
            except requests.RequestException as exc:
                print(f"Batch geocoding failed for {len(chunk)} locations, will retry next run: {exc}", file=sys.stderr)
                continue
            for i, (location, _street) in enumerate(chunk):
                coords = results.get(str(i))
                if coords:
                    to_cache.append({"Location": location, "Lat": coords[0], "Lon": coords[1], "Status": "Match"})
                else:
                    to_cache.append({"Location": location, "Lat": "", "Lon": "", "Status": "No Match"})
    else:
        for location, street in candidates:
            try:
                coords = geocode_one(street)
            except requests.RequestException as exc:
                print(f"Skipping {location!r} this run (transient error: {exc})", file=sys.stderr)
                continue
            if coords:
                to_cache.append({"Location": location, "Lat": coords[0], "Lon": coords[1], "Status": "Match"})
            else:
                to_cache.append({"Location": location, "Lat": "", "Lon": "", "Status": "No Match"})

    append_to_cache(to_cache)


def main():
    new_locations = find_new_locations()
    if not new_locations:
        print("No new locations to geocode.")
        return
    print(f"Geocoding {len(new_locations)} new location(s)...")
    geocode_locations(new_locations)
    print("Done.")


if __name__ == "__main__":
    main()

"""Plain-assert tests for geocode.py. Run with: python test_geocode.py"""
import tempfile
from pathlib import Path

import requests

import geocode
from geocode import clean_for_geocoding, read_cache, append_to_cache, classify_match, is_within_region


def test_block_address():
    assert clean_for_geocoding("5500 BLOCK UPSHUR SQ") == "5500 UPSHUR SQ"


def test_drops_landmark_suffix_after_comma():
    assert clean_for_geocoding(
        "7200 BLOCK MCKINNEY CIR, BUILDERS FIRST SOURCE - MCKINNEY CIR"
    ) == "7200 MCKINNEY CIR"


def test_drops_apartment_unit_suffix():
    assert clean_for_geocoding("100 BLOCK DEPAUL ST, Apt/Unit:,, STATION 6") == "100 DEPAUL ST"


def test_intersection_uses_ampersand():
    assert clean_for_geocoding("WORTHINGTON BLVD / LEW WALLACE ST") == "WORTHINGTON BLVD & LEW WALLACE ST"


def test_skips_bare_mile_marker():
    assert clean_for_geocoding("I70EB / 38MM") is None


def test_skips_mile_marker_with_duplicated_comma_segment():
    assert clean_for_geocoding("RT340WB / 11MM, RT340WB / 11MM") is None


def test_attempts_highway_intersection_without_mile_marker():
    # No mile marker present -- worth attempting even though the match
    # rate for two route numbers is uncertain without live testing.
    assert clean_for_geocoding("I70WB / RT85, I70EB / RT85") == "I70WB & RT85"


def test_empty_or_degenerate_location_returns_none():
    assert clean_for_geocoding("") is None
    assert clean_for_geocoding(",") is None
    assert clean_for_geocoding("BLOCK") is None


def test_cache_round_trip():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "geocode_cache.csv"
        original_path = geocode.CACHE_FILE
        geocode.CACHE_FILE = cache_path
        try:
            assert read_cache() == {}

            append_to_cache([
                {"Location": "5500 BLOCK UPSHUR SQ", "Lat": "39.4143", "Lon": "-77.4105", "Status": "Match"},
                {"Location": "I70EB / 38MM", "Lat": "", "Lon": "", "Status": "Skipped"},
            ])
            cache = read_cache()
            assert len(cache) == 2
            assert cache["5500 BLOCK UPSHUR SQ"]["Lat"] == "39.4143"
            assert cache["I70EB / 38MM"]["Status"] == "Skipped"

            # Appending more rows preserves what's already there.
            append_to_cache([
                {"Location": "WORTHINGTON BLVD / LEW WALLACE ST", "Lat": "", "Lon": "", "Status": "No Match"},
            ])
            cache = read_cache()
            assert len(cache) == 3
        finally:
            geocode.CACHE_FILE = original_path


def test_find_new_locations_diffs_against_cache():
    with tempfile.TemporaryDirectory() as tmpdir:
        incidents_path = Path(tmpdir) / "incidents.csv"
        cache_path = Path(tmpdir) / "geocode_cache.csv"
        with open(incidents_path, "w", newline="") as f:
            f.write("Time,Event,Location,Units,Date,Datetime\n")
            f.write("6:35 pm,OUTSIDE FIRE,5500 BLOCK UPSHUR SQ,Units: E311,05/08/2024,2024-05-08 18:35:00\n")
            f.write("7:17 pm,HOUSE FIRE,100 BLOCK MAIN ST,Units: E11,05/08/2024,2024-05-08 19:17:00\n")

        original_cache_file = geocode.CACHE_FILE
        geocode.CACHE_FILE = cache_path
        try:
            append_to_cache([{"Location": "100 BLOCK MAIN ST", "Lat": "1", "Lon": "2", "Status": "Match"}])
            new_locations = geocode.find_new_locations(incidents_path)
            assert new_locations == ["5500 BLOCK UPSHUR SQ"]
        finally:
            geocode.CACHE_FILE = original_cache_file


def test_geocode_locations_one_at_a_time_below_threshold():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "geocode_cache.csv"
        original_cache_file = geocode.CACHE_FILE
        original_geocode_one = geocode.geocode_one
        geocode.CACHE_FILE = cache_path

        calls = []

        def fake_geocode_one(street):
            calls.append(street)
            return (39.4, -77.4) if street == "100 MAIN ST" else None

        geocode.geocode_one = fake_geocode_one
        try:
            geocode.geocode_locations([
                "100 BLOCK MAIN ST",     # -> match
                "200 BLOCK NOWHERE RD",  # -> no match
                "I70EB / 38MM",          # -> skipped, no API call
            ])
            cache = read_cache()
            assert cache["100 BLOCK MAIN ST"]["Status"] == "Match"
            assert cache["100 BLOCK MAIN ST"]["Lat"] == "39.4"
            assert cache["200 BLOCK NOWHERE RD"]["Status"] == "No Match"
            assert cache["I70EB / 38MM"]["Status"] == "Skipped"
            assert calls == ["100 MAIN ST", "200 NOWHERE RD"]
        finally:
            geocode.CACHE_FILE = original_cache_file
            geocode.geocode_one = original_geocode_one


def test_geocode_locations_batch_path_above_threshold():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "geocode_cache.csv"
        original_cache_file = geocode.CACHE_FILE
        original_geocode_batch = geocode.geocode_batch
        original_threshold = geocode.BATCH_THRESHOLD
        geocode.CACHE_FILE = cache_path
        geocode.BATCH_THRESHOLD = 2  # force the batch path with a small test list

        def fake_geocode_batch(id_to_street):
            # Small offsets that stay well within REGION_BOUNDS regardless
            # of record_id, unlike real Frederick County coordinates which
            # only span a couple of degrees.
            return {
                record_id: (39.4 + int(record_id) * 0.01, -77.4)
                for record_id in id_to_street
                if int(record_id) % 2 == 0
            }

        geocode.geocode_batch = fake_geocode_batch
        try:
            locations = [f"{n} BLOCK TEST RD" for n in range(5)]
            geocode.geocode_locations(locations)
            cache = read_cache()
            assert len(cache) == 5
            assert cache["0 BLOCK TEST RD"]["Status"] == "Match"
            assert cache["1 BLOCK TEST RD"]["Status"] == "No Match"
            assert cache["2 BLOCK TEST RD"]["Status"] == "Match"
        finally:
            geocode.CACHE_FILE = original_cache_file
            geocode.geocode_batch = original_geocode_batch
            geocode.BATCH_THRESHOLD = original_threshold


def test_geocode_locations_batch_failure_is_not_cached():
    # A transient batch failure must not poison the cache with a false
    # "no match" -- the location should be retried on the next run.
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "geocode_cache.csv"
        original_cache_file = geocode.CACHE_FILE
        original_geocode_batch = geocode.geocode_batch
        original_threshold = geocode.BATCH_THRESHOLD
        geocode.CACHE_FILE = cache_path
        geocode.BATCH_THRESHOLD = 1

        def failing_geocode_batch(id_to_street):
            raise requests.RequestException("boom")

        geocode.geocode_batch = failing_geocode_batch
        try:
            geocode.geocode_locations(["100 BLOCK TEST RD", "I70EB / 38MM"])
            cache = read_cache()
            assert cache["I70EB / 38MM"]["Status"] == "Skipped"
            assert "100 BLOCK TEST RD" not in cache
        finally:
            geocode.CACHE_FILE = original_cache_file
            geocode.geocode_batch = original_geocode_batch
            geocode.BATCH_THRESHOLD = original_threshold


def test_is_within_region_accepts_frederick_county():
    assert is_within_region(39.4143, -77.4105)  # Frederick, MD


def test_is_within_region_accepts_mutual_aid_neighbor():
    assert is_within_region(39.575, -76.996)  # Westminster, MD (Carroll County)


def test_is_within_region_rejects_distant_mismatches():
    # These are the real mismatches observed in practice: a street-name
    # match with no city to disambiguate it lands 30-50 miles away.
    assert not is_within_region(39.2904, -76.6122)  # Baltimore, MD
    assert not is_within_region(39.4015, -76.6019)  # Towson, MD
    assert not is_within_region(38.9784, -76.4922)  # Annapolis, MD


def test_classify_match_no_coords():
    assert classify_match(None) == {"Lat": "", "Lon": "", "Status": "No Match"}


def test_classify_match_in_region():
    assert classify_match((39.4143, -77.4105)) == {"Lat": 39.4143, "Lon": -77.4105, "Status": "Match"}


def test_classify_match_out_of_region():
    assert classify_match((39.2904, -76.6122)) == {"Lat": "", "Lon": "", "Status": "Out of Region"}


def test_geocode_locations_rejects_out_of_region_match():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "geocode_cache.csv"
        original_cache_file = geocode.CACHE_FILE
        original_geocode_one = geocode.geocode_one
        geocode.CACHE_FILE = cache_path

        geocode.geocode_one = lambda street: (39.2904, -76.6122)  # Baltimore
        try:
            geocode.geocode_locations(["100 BLOCK MAIN ST"])
            cache = read_cache()
            assert cache["100 BLOCK MAIN ST"]["Status"] == "Out of Region"
            assert cache["100 BLOCK MAIN ST"]["Lat"] == ""
        finally:
            geocode.CACHE_FILE = original_cache_file
            geocode.geocode_one = original_geocode_one


def test_revalidate_cache_downgrades_bad_matches_without_api_calls():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "geocode_cache.csv"
        original_cache_file = geocode.CACHE_FILE
        geocode.CACHE_FILE = cache_path
        try:
            append_to_cache([
                {"Location": "100 BLOCK MAIN ST", "Lat": "39.4143", "Lon": "-77.4105", "Status": "Match"},
                {"Location": "200 BLOCK BAD ST", "Lat": "39.2904", "Lon": "-76.6122", "Status": "Match"},
                {"Location": "I70EB / 38MM", "Lat": "", "Lon": "", "Status": "Skipped"},
            ])
            changed = geocode.revalidate_cache()
            assert changed == 1
            cache = read_cache()
            assert cache["100 BLOCK MAIN ST"]["Status"] == "Match"
            assert cache["200 BLOCK BAD ST"]["Status"] == "Out of Region"
            assert cache["200 BLOCK BAD ST"]["Lat"] == ""
            assert cache["I70EB / 38MM"]["Status"] == "Skipped"
        finally:
            geocode.CACHE_FILE = original_cache_file


def run_all():
    tests = [obj for name, obj in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run_all()

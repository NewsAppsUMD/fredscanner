"""Plain-assert tests for threads.py. Run with: python test_threads.py"""
from datetime import datetime, timedelta

from threads import assign_threads, parse_units, extract_radio_channel


def row(time, event, location, units, date, datetime_):
    return {
        "Time": time,
        "Event": event,
        "Location": location,
        "Units": units,
        "Date": date,
        "Datetime": datetime_,
    }


def test_parse_units_plain_format():
    assert parse_units("Units: E311, R2") == ["E311", "R2"]


def test_parse_units_radio_format():
    assert parse_units("Radio: 9C Units: E11, TT4") == ["E11", "TT4"]


def test_parse_units_strips_leaked_radio_tokens():
    # Radio-channel tokens sometimes leak into the unit list itself.
    assert parse_units("Units: E152, 91C") == ["E152"]
    assert parse_units("Units: CCE102, 9C, E172") == ["CCE102", "E172"]


def test_parse_units_glued_latlon_prefix():
    units = "LL: 39.38003296, -77.30024571Radio: 91C Units: E11, R2"
    assert parse_units(units) == ["E11", "R2"]


def test_parse_units_empty():
    assert parse_units("") == []
    assert parse_units("Radio: 9C") == []


def test_extract_radio_channel():
    assert extract_radio_channel("Radio: 9D Units: E11") == "9D"
    assert extract_radio_channel("Units: E11") is None


def test_dedupes_exact_duplicate_rows():
    rows = [
        row("6:35 pm", "OUTSIDE FIRE", "5500 BLOCK UPSHUR SQ", "Units: E311", "05/08/2024", "2024-05-08 18:35:00"),
        row("6:35 pm", "OUTSIDE FIRE", "5500 BLOCK UPSHUR SQ", "Units: E311", "05/08/2024", "2024-05-08 18:35:00"),
    ]
    result_rows, threads = assign_threads(rows)
    assert len(result_rows) == 1
    assert len(threads) == 1
    assert threads[0]["post_count"] == 1


def test_escalation_thread_merges_across_event_change_and_disjoint_units():
    # Mirrors the real Saint Anthony's fire pattern: event reclassifies and
    # units are added without repeating the earlier roster.
    rows = [
        row("12:37 am", "COMMERCIAL FIRE ALARM", "100 BLOCK TEST RD", "Units: E61, E62", "08/30/2024", "2024-08-30 00:37:00"),
        row("12:44 am", "HOUSE FIRE", "100 BLOCK TEST RD", "Units: BC901, R6", "08/30/2024", "2024-08-30 00:44:00"),
        row("1:01 am", "HOUSE FIRE", "100 BLOCK TEST RD", "Units: TW6, K10", "08/30/2024", "2024-08-30 01:01:00"),
    ]
    result_rows, threads = assign_threads(rows)
    assert len(threads) == 1
    thread = threads[0]
    assert thread["post_count"] == 3
    assert thread["headline_event"] == "HOUSE FIRE"
    assert set(thread["unit_union"]) == {"E61", "E62", "BC901", "R6", "TW6", "K10"}
    assert all(r["ThreadID"] == thread["id"] for r in result_rows)


def test_same_timestamp_posts_thread_deterministically():
    rows = [
        row("12:08 am", "RESIDENTIAL FIRE ALARM", "100 BLOCK LOCUST CT", "Units: E72", "04/11/2025", "2025-04-11 00:08:00"),
        row("12:08 am", "HOUSE FIRE - ENTRAPMENT", "100 BLOCK LOCUST CT", "Units: E121, E82", "04/11/2025", "2025-04-11 00:08:00"),
    ]
    result_rows, threads = assign_threads(rows)
    assert len(threads) == 1
    assert threads[0]["post_count"] == 2
    assert threads[0]["headline_event"] == "HOUSE FIRE - ENTRAPMENT"


def test_incompatible_categories_do_not_merge():
    # A structure fire followed shortly by an unrelated helicopter-LZ post
    # at the same address should not be treated as one incident.
    rows = [
        row("2:00 pm", "BUILDING FIRE", "400 BLOCK W SEVENTH ST, FHH", "Units: E11", "01/01/2025", "2025-01-01 14:00:00"),
        row("2:10 pm", "FHH STANDBY FOR HELICOPTER LANDING", "400 BLOCK W SEVENTH ST, FHH", "Units: A1", "01/01/2025", "2025-01-01 14:10:00"),
    ]
    result_rows, threads = assign_threads(rows)
    assert len(threads) == 2


def test_station_transfers_never_thread():
    rows = [
        row("4:36 am", "UNIT TRANSFER TO OTHER STATION", "12000 BLOCK SOUTH ST, STATION 17", "Units: K7, A39", "09/26/2024", "2024-09-26 04:36:00"),
        row("4:37 am", "UNIT TRANSFER TO OTHER STATION", "12000 BLOCK SOUTH ST, STATION 17", "Units: E12, K7, A39", "09/26/2024", "2024-09-26 04:37:00"),
    ]
    result_rows, threads = assign_threads(rows)
    assert len(threads) == 2
    assert threads[0]["post_count"] == 1
    assert threads[1]["post_count"] == 1


def test_gap_over_60_minutes_does_not_merge():
    rows = [
        row("6:00 pm", "GAS LEAK INSIDE", "200 BLOCK TEST AVE", "Units: E11", "01/01/2025", "2025-01-01 18:00:00"),
        row("7:05 pm", "GAS LEAK INSIDE", "200 BLOCK TEST AVE", "Units: E12", "01/01/2025", "2025-01-01 19:05:00"),
    ]
    result_rows, threads = assign_threads(rows)
    assert len(threads) == 2


def test_span_cap_stops_slow_drift_chain():
    # Five posts 25 minutes apart (span 100m) should chain into one thread;
    # a sixth post another 25 minutes later pushes the span past the
    # 120-minute cap and must start a new thread even though the gap from
    # the previous post is still under 30 minutes.
    base = datetime(2025, 1, 1, 18, 0, 0)
    offsets = [0, 25, 50, 75, 100, 125]
    rows = [
        row(
            dt.strftime("%I:%M %p").lstrip("0"),
            "GAS LEAK INSIDE",
            "300 BLOCK TEST BLVD",
            f"Units: E{i}",
            "01/01/2025",
            dt.strftime("%Y-%m-%d %H:%M:%S"),
        )
        for i, dt in ((i, base + timedelta(minutes=m)) for i, m in enumerate(offsets))
    ]
    result_rows, threads = assign_threads(rows)
    assert len(threads) == 2
    assert threads[0]["post_count"] == 5
    assert threads[1]["post_count"] == 1


def run_all():
    tests = [obj for name, obj in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run_all()

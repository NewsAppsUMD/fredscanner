"""
Sample trend analysis scripts for enhanced incidents data.

This demonstrates the types of analysis now possible with the enhanced dataset.
"""

import csv
from collections import Counter, defaultdict
from datetime import datetime
import json


def load_enhanced_data(filename='incidents_enhanced.csv'):
    """Load the enhanced incidents data."""
    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        return list(reader)


def analyze_hourly_patterns(data):
    """Analyze incident patterns by hour of day."""
    print("\n" + "=" * 70)
    print("HOURLY INCIDENT PATTERNS")
    print("=" * 70)

    hourly_counts = Counter(int(row['hour']) for row in data)

    print("\nIncidents by Hour of Day:")
    for hour in range(24):
        count = hourly_counts[hour]
        bar = '█' * (count // 50)
        print(f"{hour:2d}:00 - {count:4d} {bar}")

    # Peak hours
    peak_hours = hourly_counts.most_common(5)
    print(f"\nPeak Hours:")
    for hour, count in peak_hours:
        print(f"  {hour:02d}:00 - {count:,} incidents")


def analyze_event_trends_by_month(data):
    """Analyze top event types by month."""
    print("\n" + "=" * 70)
    print("TOP EVENT TYPES BY MONTH (2024-2025)")
    print("=" * 70)

    # Group by year-month
    monthly_events = defaultdict(Counter)

    for row in data:
        year_month = f"{row['year']}-{int(row['month']):02d}"
        monthly_events[year_month][row['event']] += 1

    # Show top 5 events for each month
    sorted_months = sorted(monthly_events.keys())

    for month in sorted_months[-12:]:  # Last 12 months
        print(f"\n{month}:")
        top_events = monthly_events[month].most_common(5)
        total = sum(monthly_events[month].values())
        for event, count in top_events:
            pct = (count / total) * 100
            print(f"  {count:4d} ({pct:4.1f}%) - {event[:50]}")


def analyze_weekend_vs_weekday(data):
    """Compare weekend vs weekday incident patterns."""
    print("\n" + "=" * 70)
    print("WEEKEND vs WEEKDAY ANALYSIS")
    print("=" * 70)

    weekday_events = Counter(row['event'] for row in data if row['is_weekend'] == 'No')
    weekend_events = Counter(row['event'] for row in data if row['is_weekend'] == 'Yes')

    total_weekday = sum(weekday_events.values())
    total_weekend = sum(weekend_events.values())

    print(f"\nTotal weekday incidents: {total_weekday:,}")
    print(f"Total weekend incidents: {total_weekend:,}")
    print(f"Average per weekday: {total_weekday / 5:.0f}")
    print(f"Average per weekend day: {total_weekend / 2:.0f}")

    print("\nTop 10 Events - Weekday vs Weekend:")
    print(f"{'Event':<45} {'Weekday':>10} {'Weekend':>10} {'Diff':>8}")
    print("-" * 75)

    # Get top events overall
    all_events = Counter(row['event'] for row in data)
    for event, _ in all_events.most_common(10):
        weekday_count = weekday_events[event]
        weekend_count = weekend_events[event]
        # Normalize to per-day average
        weekday_avg = weekday_count / 5
        weekend_avg = weekend_count / 2
        diff_pct = ((weekend_avg - weekday_avg) / weekday_avg * 100) if weekday_avg > 0 else 0

        event_short = event[:44]
        print(f"{event_short:<45} {weekday_count:>10,} {weekend_count:>10,} {diff_pct:>7.1f}%")


def analyze_location_hotspots(data):
    """Identify locations with most incidents."""
    print("\n" + "=" * 70)
    print("LOCATION HOTSPOTS")
    print("=" * 70)

    # Count by street address
    locations = Counter(row['street_address'] for row in data if row['street_address'])

    print("\nTop 20 Locations by Incident Count:")
    for i, (location, count) in enumerate(locations.most_common(20), 1):
        print(f"{i:2d}. {count:4d} - {location}")


def analyze_seasonal_trends(data):
    """Analyze seasonal patterns."""
    print("\n" + "=" * 70)
    print("SEASONAL TRENDS")
    print("=" * 70)

    # Group by season and event type
    seasonal_events = defaultdict(Counter)

    for row in data:
        seasonal_events[row['season']][row['event']] += 1

    for season in ['Winter', 'Spring', 'Summer', 'Fall']:
        print(f"\n{season.upper()} - Top 5 Event Types:")
        total = sum(seasonal_events[season].values())
        print(f"Total incidents: {total:,}")

        for event, count in seasonal_events[season].most_common(5):
            pct = (count / total) * 100
            print(f"  {count:4d} ({pct:4.1f}%) - {event[:50]}")


def analyze_response_patterns(data):
    """Analyze emergency response patterns."""
    print("\n" + "=" * 70)
    print("RESPONSE PATTERNS")
    print("=" * 70)

    unit_counts = [int(row['unit_count']) for row in data]

    print(f"\nUnit Deployment Statistics:")
    print(f"  Average units per incident: {sum(unit_counts) / len(unit_counts):.2f}")
    print(f"  Minimum units: {min(unit_counts)}")
    print(f"  Maximum units: {max(unit_counts)}")

    # Find incidents with most units
    print(f"\nIncidents with Most Units Dispatched:")
    sorted_by_units = sorted(data, key=lambda x: int(x['unit_count']), reverse=True)

    for i, incident in enumerate(sorted_by_units[:10], 1):
        print(f"{i:2d}. {incident['unit_count']:2s} units - {incident['event'][:40]} - {incident['datetime'][:10]}")
        print(f"    Location: {incident['location'][:65]}")

    # Radio channel usage
    radio_channels = Counter(row['radio_channel'] for row in data if row['radio_channel'])
    print(f"\nTop 10 Radio Channels:")
    for channel, count in radio_channels.most_common(10):
        pct = (count / len(data)) * 100
        print(f"  {channel:12s} - {count:5,} ({pct:4.1f}%)")


def analyze_time_period_by_event(data):
    """Analyze which event types occur in which time periods."""
    print("\n" + "=" * 70)
    print("EVENT TYPES BY TIME PERIOD")
    print("=" * 70)

    # Get top 10 event types
    all_events = Counter(row['event'] for row in data)
    top_events = [event for event, _ in all_events.most_common(10)]

    # Count by time period
    time_periods = ['Morning', 'Afternoon', 'Evening', 'Night']

    print(f"\n{'Event':<45} {'Morn':>7} {'After':>7} {'Even':>7} {'Night':>7}")
    print("-" * 80)

    for event in top_events:
        event_data = [row for row in data if row['event'] == event]
        period_counts = Counter(row['time_period'] for row in event_data)

        event_short = event[:44]
        print(f"{event_short:<45} {period_counts['Morning']:>7} {period_counts['Afternoon']:>7} "
              f"{period_counts['Evening']:>7} {period_counts['Night']:>7}")


def generate_monthly_summary(data):
    """Generate month-by-month summary statistics."""
    print("\n" + "=" * 70)
    print("MONTHLY SUMMARY (for trend visualization)")
    print("=" * 70)

    monthly_stats = defaultdict(lambda: {'total': 0, 'events': Counter()})

    for row in data:
        year_month = f"{row['year']}-{int(row['month']):02d}"
        monthly_stats[year_month]['total'] += 1
        monthly_stats[year_month]['events'][row['event']] += 1

    print(f"\n{'Month':<10} {'Total':>8} {'Top Event':<45} {'Count':>7}")
    print("-" * 75)

    for month in sorted(monthly_stats.keys()):
        total = monthly_stats[month]['total']
        top_event, top_count = monthly_stats[month]['events'].most_common(1)[0]
        top_event_short = top_event[:44]
        print(f"{month:<10} {total:>8,} {top_event_short:<45} {top_count:>7,}")


def main():
    """Run all analyses."""
    print("ENHANCED INCIDENTS DATA - TREND ANALYSIS")
    print("=" * 70)

    data = load_enhanced_data()
    print(f"\nLoaded {len(data):,} incidents")
    print(f"Date range: {min(row['datetime'] for row in data)[:10]} to {max(row['datetime'] for row in data)[:10]}")

    # Run analyses
    analyze_hourly_patterns(data)
    analyze_time_period_by_event(data)
    analyze_weekend_vs_weekday(data)
    analyze_seasonal_trends(data)
    analyze_response_patterns(data)
    analyze_location_hotspots(data)
    generate_monthly_summary(data)
    analyze_event_trends_by_month(data)

    print("\n" + "=" * 70)
    print("Analysis complete!")
    print("=" * 70)


if __name__ == '__main__':
    main()

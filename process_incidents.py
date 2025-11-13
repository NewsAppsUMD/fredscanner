"""
Phase 1: Data Cleaning and Enhancement Script for incidents.csv

This script:
1. Removes duplicate incidents
2. Standardizes Units field format
3. Parses location data into structured fields
4. Adds temporal analysis fields
"""

import csv
import re
from datetime import datetime
from collections import defaultdict


def parse_units_field(units_str):
    """Parse the Units field to extract radio channel and unit list."""
    radio_channel = None
    units_list = units_str

    # Extract radio channel if present (e.g., "Radio: 9C Units: ...")
    radio_match = re.match(r'Radio:\s*(\S+)\s+Units:\s*(.+)', units_str)
    if radio_match:
        radio_channel = radio_match.group(1)
        units_list = radio_match.group(2)
    else:
        # Try just "Units: ..." pattern
        units_match = re.match(r'Units:\s*(.+)', units_str)
        if units_match:
            units_list = units_match.group(1)

    # Clean the units list
    units_list = units_list.strip()

    # Count units (separated by commas)
    units = [u.strip() for u in units_list.split(',')]
    unit_count = len(units)

    return {
        'radio_channel': radio_channel or '',
        'units_list': units_list,
        'unit_count': unit_count
    }


def parse_location(location_str):
    """Parse location into structured components."""
    result = {
        'location_type': '',
        'street_address': '',
        'cross_street': '',
        'apartment_unit': '',
        'building_name': '',
        'full_location': location_str
    }

    # Extract apartment/unit number if present
    apt_match = re.search(r',\s*Apt/Unit:([^,]+)', location_str)
    if apt_match:
        result['apartment_unit'] = apt_match.group(1).strip()
        location_str = re.sub(r',\s*Apt/Unit:[^,]+', '', location_str)

    # Split by commas to separate address from building name
    parts = [p.strip() for p in location_str.split(',')]

    # Check if it's an intersection (contains /)
    if '/' in parts[0]:
        result['location_type'] = 'INTERSECTION'
        streets = parts[0].split('/')
        result['street_address'] = streets[0].strip()
        if len(streets) > 1:
            result['cross_street'] = streets[1].strip()
    elif 'BLOCK' in parts[0].upper():
        result['location_type'] = 'BLOCK'
        result['street_address'] = parts[0].strip()
    else:
        result['location_type'] = 'ADDRESS'
        result['street_address'] = parts[0].strip()

    # Remaining parts are likely building/landmark names
    if len(parts) > 1:
        result['building_name'] = ', '.join(parts[1:])

    return result


def get_temporal_fields(datetime_obj):
    """Generate temporal analysis fields from datetime."""
    # Day of week (0=Monday, 6=Sunday)
    day_of_week_num = datetime_obj.weekday()
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    # Time period
    hour = datetime_obj.hour
    if 6 <= hour < 12:
        time_period = 'Morning'
    elif 12 <= hour < 17:
        time_period = 'Afternoon'
    elif 17 <= hour < 21:
        time_period = 'Evening'
    else:
        time_period = 'Night'

    # Season (meteorological seasons)
    month = datetime_obj.month
    if month in [12, 1, 2]:
        season = 'Winter'
    elif month in [3, 4, 5]:
        season = 'Spring'
    elif month in [6, 7, 8]:
        season = 'Summer'
    else:
        season = 'Fall'

    return {
        'year': datetime_obj.year,
        'month': datetime_obj.month,
        'day': datetime_obj.day,
        'day_of_week': day_names[day_of_week_num],
        'hour': hour,
        'time_period': time_period,
        'is_weekend': 'Yes' if day_of_week_num >= 5 else 'No',
        'season': season,
        'week_of_year': datetime_obj.isocalendar()[1]
    }


def process_incidents(input_file, output_file):
    """Main processing function."""

    print("Reading incidents.csv...")
    with open(input_file, 'r') as f:
        reader = csv.DictReader(f)
        incidents = list(reader)

    print(f"Total records read: {len(incidents)}")

    # Remove duplicates based on (Datetime, Event, Location)
    print("\nRemoving duplicates...")
    seen = set()
    unique_incidents = []
    duplicates_removed = 0

    for incident in incidents:
        # Create a unique key
        key = (incident['Datetime'], incident['Event'], incident['Location'])
        if key not in seen:
            seen.add(key)
            unique_incidents.append(incident)
        else:
            duplicates_removed += 1

    print(f"Duplicates removed: {duplicates_removed}")
    print(f"Unique records: {len(unique_incidents)}")

    # Process each incident
    print("\nProcessing and enhancing incidents...")
    enhanced_incidents = []

    for idx, incident in enumerate(unique_incidents):
        if idx % 1000 == 0:
            print(f"  Processed {idx}/{len(unique_incidents)} records...")

        # Parse datetime
        try:
            dt = datetime.strptime(incident['Datetime'], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            print(f"  Warning: Invalid datetime at index {idx}: {incident['Datetime']}")
            continue

        # Parse units
        units_data = parse_units_field(incident['Units'])

        # Parse location
        location_data = parse_location(incident['Location'])

        # Get temporal fields
        temporal_data = get_temporal_fields(dt)

        # Build enhanced record
        enhanced = {
            # Original fields
            'datetime': incident['Datetime'],
            'event': incident['Event'],
            'location': incident['Location'],
            'units': incident['Units'],

            # Units fields
            'radio_channel': units_data['radio_channel'],
            'units_list': units_data['units_list'],
            'unit_count': units_data['unit_count'],

            # Location fields
            'location_type': location_data['location_type'],
            'street_address': location_data['street_address'],
            'cross_street': location_data['cross_street'],
            'apartment_unit': location_data['apartment_unit'],
            'building_name': location_data['building_name'],

            # Temporal fields
            'year': temporal_data['year'],
            'month': temporal_data['month'],
            'day': temporal_data['day'],
            'day_of_week': temporal_data['day_of_week'],
            'hour': temporal_data['hour'],
            'time_period': temporal_data['time_period'],
            'is_weekend': temporal_data['is_weekend'],
            'season': temporal_data['season'],
            'week_of_year': temporal_data['week_of_year']
        }

        enhanced_incidents.append(enhanced)

    print(f"  Processed {len(enhanced_incidents)}/{len(unique_incidents)} records")

    # Write enhanced CSV
    print(f"\nWriting enhanced data to {output_file}...")
    fieldnames = [
        # Core fields
        'datetime', 'event', 'location', 'units',
        # Units analysis
        'radio_channel', 'units_list', 'unit_count',
        # Location analysis
        'location_type', 'street_address', 'cross_street', 'apartment_unit', 'building_name',
        # Temporal analysis
        'year', 'month', 'day', 'day_of_week', 'hour', 'time_period', 'is_weekend', 'season', 'week_of_year'
    ]

    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(enhanced_incidents)

    print(f"✓ Enhanced CSV written: {output_file}")

    return {
        'total_original': len(incidents),
        'duplicates_removed': duplicates_removed,
        'total_enhanced': len(enhanced_incidents)
    }


def generate_quality_report(stats, output_file):
    """Generate a data quality report."""

    print("\nReading enhanced data for quality report...")
    with open(output_file, 'r') as f:
        reader = csv.DictReader(f)
        data = list(reader)

    # Analyze data quality
    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("DATA QUALITY REPORT - Phase 1 Enhancement")
    report_lines.append("=" * 70)
    report_lines.append("")

    report_lines.append("PROCESSING SUMMARY")
    report_lines.append("-" * 70)
    report_lines.append(f"Original records:        {stats['total_original']:,}")
    report_lines.append(f"Duplicates removed:      {stats['duplicates_removed']:,}")
    report_lines.append(f"Enhanced records:        {stats['total_enhanced']:,}")
    report_lines.append("")

    # Date range
    dates = [datetime.strptime(row['datetime'], '%Y-%m-%d %H:%M:%S') for row in data]
    report_lines.append("DATE RANGE")
    report_lines.append("-" * 70)
    report_lines.append(f"First incident:          {min(dates).strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Last incident:           {max(dates).strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Total days covered:      {(max(dates) - min(dates)).days}")
    report_lines.append("")

    # Event types
    from collections import Counter
    events = Counter(row['event'] for row in data)
    report_lines.append("TOP 10 EVENT TYPES")
    report_lines.append("-" * 70)
    for event, count in events.most_common(10):
        pct = (count / len(data)) * 100
        report_lines.append(f"{count:5,} ({pct:5.1f}%) - {event}")
    report_lines.append("")

    # Location types
    location_types = Counter(row['location_type'] for row in data)
    report_lines.append("LOCATION TYPE DISTRIBUTION")
    report_lines.append("-" * 70)
    for loc_type, count in location_types.most_common():
        pct = (count / len(data)) * 100
        report_lines.append(f"{count:5,} ({pct:5.1f}%) - {loc_type}")
    report_lines.append("")

    # Radio channels
    radio_channels = Counter(row['radio_channel'] for row in data if row['radio_channel'])
    report_lines.append("RADIO CHANNEL DISTRIBUTION")
    report_lines.append("-" * 70)
    report_lines.append(f"With radio channel:      {sum(1 for r in data if r['radio_channel'])}")
    report_lines.append(f"Without radio channel:   {sum(1 for r in data if not r['radio_channel'])}")
    report_lines.append("\nTop radio channels:")
    for channel, count in radio_channels.most_common(10):
        report_lines.append(f"  {channel}: {count:,}")
    report_lines.append("")

    # Unit count statistics
    unit_counts = [int(row['unit_count']) for row in data]
    report_lines.append("UNIT COUNT STATISTICS")
    report_lines.append("-" * 70)
    report_lines.append(f"Average units per incident:  {sum(unit_counts) / len(unit_counts):.2f}")
    report_lines.append(f"Minimum units:               {min(unit_counts)}")
    report_lines.append(f"Maximum units:               {max(unit_counts)}")
    report_lines.append("")

    # Temporal analysis
    time_periods = Counter(row['time_period'] for row in data)
    report_lines.append("TIME PERIOD DISTRIBUTION")
    report_lines.append("-" * 70)
    for period in ['Morning', 'Afternoon', 'Evening', 'Night']:
        count = time_periods[period]
        pct = (count / len(data)) * 100
        report_lines.append(f"{count:5,} ({pct:5.1f}%) - {period}")
    report_lines.append("")

    # Day of week
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    days = Counter(row['day_of_week'] for row in data)
    report_lines.append("DAY OF WEEK DISTRIBUTION")
    report_lines.append("-" * 70)
    for day in day_order:
        count = days[day]
        pct = (count / len(data)) * 100
        report_lines.append(f"{count:5,} ({pct:5.1f}%) - {day}")
    report_lines.append("")

    # Weekend vs weekday
    weekend_count = sum(1 for r in data if r['is_weekend'] == 'Yes')
    weekday_count = len(data) - weekend_count
    report_lines.append("WEEKEND vs WEEKDAY")
    report_lines.append("-" * 70)
    report_lines.append(f"Weekday incidents:       {weekday_count:,} ({(weekday_count/len(data)*100):.1f}%)")
    report_lines.append(f"Weekend incidents:       {weekend_count:,} ({(weekend_count/len(data)*100):.1f}%)")
    report_lines.append("")

    # Season distribution
    seasons = Counter(row['season'] for row in data)
    report_lines.append("SEASONAL DISTRIBUTION")
    report_lines.append("-" * 70)
    for season in ['Winter', 'Spring', 'Summer', 'Fall']:
        count = seasons[season]
        pct = (count / len(data)) * 100
        report_lines.append(f"{count:5,} ({pct:5.1f}%) - {season}")
    report_lines.append("")

    report_lines.append("=" * 70)

    # Print to console
    report_text = '\n'.join(report_lines)
    print(report_text)

    # Save to file
    report_file = 'data_quality_report_phase1.txt'
    with open(report_file, 'w') as f:
        f.write(report_text)

    print(f"\n✓ Quality report saved to: {report_file}")

    return report_file


if __name__ == '__main__':
    input_file = 'incidents.csv'
    output_file = 'incidents_enhanced.csv'

    print("PHASE 1: Data Cleaning and Enhancement")
    print("=" * 70)

    # Process the data
    stats = process_incidents(input_file, output_file)

    # Generate quality report
    generate_quality_report(stats, output_file)

    print("\n✓ Phase 1 processing complete!")
    print(f"✓ Enhanced data: {output_file}")
    print(f"✓ Quality report: data_quality_report_phase1.txt")

import csv
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Function to parse time and date strings into a datetime object
def parse_datetime(time_str, date_str):
    # Parse time string to datetime object
    time = datetime.strptime(time_str, "%I:%M %p")
    # Parse date string to datetime object
    date = datetime.strptime(date_str, "%m/%d/%Y")
    # Combine date and time
    datetime_obj = datetime.combine(date.date(), time.time())
    return datetime_obj

# Function to read existing incidents from CSV file and return the maximum datetime
def read_existing_incidents(filename):
    max_datetime = None
    try:
        with open(filename, "r", newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                incident_datetime = datetime.strptime(row["Datetime"], "%Y-%m-%d %H:%M:%S")
                if max_datetime is None or incident_datetime > max_datetime:
                    max_datetime = incident_datetime
    except FileNotFoundError:
        pass  # File doesn't exist yet
    return max_datetime

url = "https://frederickscanner.com/fredscannerpro/tweets.html"

# Get the maximum datetime from existing incidents
max_datetime = read_existing_incidents("incidents.csv")

r = requests.get(url)

soup = BeautifulSoup(r.text, "html.parser")

# Find all <p> tags and extract their text
incident_texts = [p.get_text(strip=True) for p in soup.find_all("p")]

# Write the data to a CSV file with all fields quoted
with open("incidents.csv", "a", newline="") as csvfile:
    writer = csv.writer(csvfile)
    
    # Check if a header row exists
    file_empty = csvfile.tell() == 0
    
    # Write header row if the file is empty
    if file_empty:
        writer.writerow(["Time", "Event", "Location", "Units", "Date", "Datetime"])
    
    for text in incident_texts:
        parts = text.split(" | ")
        if len(parts) == 5:
            time = parts[0]
            event = parts[1]
            location = parts[2]
            units = parts[3]
            date = parts[4].split("(")[1][:-1].replace("posted ","")
            # Parse time and date strings into a datetime object
            datetime_obj = parse_datetime(time, date)
            # Check if the incident is new based on datetime
            if max_datetime is None or datetime_obj > max_datetime:
                # Write row to CSV with datetime value
                writer.writerow([time, event, location, units, date, datetime_obj])
        elif len(parts) == 6:
            time = parts[0]
            event = parts[1]
            location = parts[2]
            units = parts[3] + ' ' + parts[4]
            date = parts[5].split("(")[1][:-1].replace("posted ","")
            # Parse time and date strings into a datetime object
            datetime_obj = parse_datetime(time, date)
            # Check if the incident is new based on datetime
            if max_datetime is None or datetime_obj > max_datetime:
                # Write row to CSV with datetime value
                writer.writerow([time, event, location, units, date, datetime_obj])

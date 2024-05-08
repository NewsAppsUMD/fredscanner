import csv
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz

# Function to convert string time to datetime object
def convert_to_datetime(time_str, date_str):
    # Parse time string to datetime object
    time = datetime.strptime(time_str, "%I:%M %p")
    # Parse date string to datetime object
    date = datetime.strptime(date_str, "%m/%d/%Y")
    # Combine date and time
    datetime_obj = datetime.combine(date.date(), time.time())
    return datetime_obj

# Function to calculate elapsed time in EST
def calculate_elapsed_time(datetime_obj):
    # Get current time in EST
    est = pytz.timezone('US/Eastern')
    current_time = datetime.now(est)
    # Localize datetime object to EST
    datetime_obj_est = est.localize(datetime_obj)
    # Calculate elapsed time
    elapsed_time = current_time - datetime_obj_est
    return elapsed_time

url = "https://frederickscanner.com/fredscannerpro/tweets.html"

r = requests.get(url)

soup = BeautifulSoup(r.text, "html.parser")

# Find all <p> tags and extract their text
incident_texts = [p.get_text(strip=True) for p in soup.find_all("p")]

# Write the data to a CSV file with all fields quoted
with open("incidents.csv", "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    
    # Write header row
    writer.writerow(["Time", "Event", "Location", "Units", "Date", "Elapsed Time"])

    for text in incident_texts:
        parts = text.split(" | ")
        if len(parts) == 5:
            time = parts[0]
            event = parts[1]
            location = parts[2]
            units = parts[3]
            date = parts[4].split("(")[1][:-1].replace("posted ","")
            # Convert time string to datetime object
            datetime_obj = convert_to_datetime(time, date)
            # Calculate elapsed time
            elapsed_time = calculate_elapsed_time(datetime_obj)
            writer.writerow([time, event, location, units, date, elapsed_time])
        elif len(parts) == 6:
            time = parts[0]
            event = parts[1]
            location = parts[2]
            units = parts[3] + ' ' + parts[4]
            date = parts[5].split("(")[1][:-1].replace("posted ","")
            # Convert time string to datetime object
            datetime_obj = convert_to_datetime(time, date)
            # Calculate elapsed time
            elapsed_time = calculate_elapsed_time(datetime_obj)
            writer.writerow([time, event, location, units, date, elapsed_time])

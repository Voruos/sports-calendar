import requests
from icalendar import Calendar
from pathlib import Path

# Read the list of calendar URLs
with open("calendar-sources.txt") as f:
    urls = [line.strip() for line in f if line.strip()]

merged = Calendar()
merged.add("prodid", "-//Merged Sports Calendar//")
merged.add("version", "2.0")

for url in urls:
    try:
        r = requests.get(url)
        r.raise_for_status()
        cal = Calendar.from_ical(r.content)
        for component in cal.walk():
            if component.name == "VEVENT":
                merged.add_component(component)
    except Exception as e:
        print(f"Failed to fetch or parse {url}: {e}")

# Write the merged calendar to a file
output_path = Path("merged.ics")
with open(output_path, "wb") as f:
    f.write(merged.to_ical())

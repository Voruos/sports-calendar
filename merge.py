import requests
from icalendar import Calendar
from pathlib import Path

# 1) Read sources, skipping blank lines & comments
with open("calendar-sources.txt") as f:
    sources = [
        line.strip()
        for line in f
        if line.strip() and not line.strip().startswith("#")
    ]

merged = Calendar()
merged.add("prodid", "-//Merged Sports & Movies Calendar//")
merged.add("version", "2.0")

for src in sources:
    try:
        if src.lower().startswith("http"):
            # fetch remote ICS
            r = requests.get(src)
            r.raise_for_status()
            data = r.content
        else:
            # read local ICS file
            data = Path(src).read_bytes()

        cal = Calendar.from_ical(data)
        for component in cal.walk():
            if component.name == "VEVENT":
                merged.add_component(component)

    except Exception as e:
        print(f"Failed to fetch or parse {src}: {e}")

# 3) Write merged calendar back to docs/merged.ics
output_path = Path("docs/merged.ics")
output_path.parent.mkdir(parents=True, exist_ok=True)
with open(output_path, "wb") as f:
    f.write(merged.to_ical())

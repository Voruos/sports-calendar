import requests
from icalendar import Calendar
from pathlib import Path
from datetime import datetime, timedelta, timezone

# load calendar sources, skipping comments
with open("calendar-sources.txt") as f:
    sources = [
        line.strip() for line in f
        if line.strip() and not line.strip().startswith("#")
    ]

merged = Calendar()
merged.add("prodid", "-//Merged Sports & Movies Calendar//")
merged.add("version", "2.0")

# cutoff for movie events (30 days ago)
now = datetime.now(timezone.utc)
cutoff = now - timedelta(days=30)

for src in sources:
    try:
        if src.lower().startswith("http"):
            data = requests.get(src).content
        else:
            data = Path(src).read_bytes()

        cal = Calendar.from_ical(data)
        for comp in cal.walk():
            if comp.name != "VEVENT":
                continue

            summary = comp.get("SUMMARY", "")
            is_movie = summary.startswith("Now Streaming:")

            if is_movie:
                # parse DTSTART
                dt = comp.get("DTSTART").dt
                if isinstance(dt, datetime):
                    event_dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                else:
                    # date-only → midnight UTC
                    event_dt = datetime(
                        dt.year, dt.month, dt.day, tzinfo=timezone.utc
                    )
                if event_dt < cutoff:
                    continue  # skip old movie events

            merged.add_component(comp)

    except Exception as e:
        print(f"Failed to fetch or parse {src}: {e}")

# write merged calendar
out = Path("docs/merged.ics")
out.parent.mkdir(exist_ok=True)
with open(out, "wb") as f:
    f.write(merged.to_ical())

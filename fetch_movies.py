#!/usr/bin/env python3
import os
import requests
from datetime import datetime, timedelta, timezone
from icalendar import Calendar, Event
import pytz

# ─── CONFIG ───────────────────────────────────────────────────────────────────
API_KEY         = os.getenv("TMDB_API_KEY")
REGIONS         = ["IN", "BD"]  # India & Bangladesh
DISCOVER_URL    = "https://api.themoviedb.org/3/discover/movie"
WATCH_PROVIDERS = "https://api.themoviedb.org/3/movie/{id}/watch/providers"
VIDEO_URL       = "https://api.themoviedb.org/3/movie/{id}/videos"
OUTPUT_FILE     = "movies.ics"
TZ              = pytz.timezone("Asia/Dhaka")
# ────────────────────────────────────────────────────────────────────────────────

if not API_KEY:
    raise RuntimeError("TMDB_API_KEY environment variable not set")

# Compute date window
today      = datetime.now(TZ).date()
thirty_ago = today - timedelta(days=30)

# Discover all movies released between thirty_ago and today
movies = []
page = 1
while True:
    resp = requests.get(DISCOVER_URL, params={
        "api_key": API_KEY,
        "language": "en-US",
        "sort_by": "primary_release_date.desc",
        "primary_release_date.gte": thirty_ago.isoformat(),
        "primary_release_date.lte": today.isoformat(),
        "page": page,
        # Optionally: filter original_language here
    })
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", [])
    if not results:
        break
    movies.extend(results)
    if page >= data.get("total_pages", 1):
        break
    page += 1

# Build summary lines
items = []
for m in movies:
    mid = m["id"]
    # 1) check streaming providers
    wp = requests.get(WATCH_PROVIDERS.format(id=mid),
                      params={"api_key": API_KEY}).json().get("results", {})
    platforms = sorted({
        p["provider_name"]
        for r in REGIONS
        for p in wp.get(r, {}).get("flatrate", [])
    })
    if not platforms:
        continue

    # 2) fetch YouTube trailer
    vids = requests.get(VIDEO_URL.format(id=mid),
                        params={"api_key": API_KEY}).json().get("results", [])
    key = next(
        (v["key"] for v in vids
         if v["site"] == "YouTube" and v["type"] == "Trailer"),
        None
    )
    trailer = f"https://youtu.be/{key}" if key else ""

    # 3) build bullet line
    line = f"• {m['title']} ({', '.join(platforms)})"
    if trailer:
        line += f"\n  ▶ Trailer: {trailer}"
    items.append(line)

# Create the calendar and one summary event
cal = Calendar()
cal.add("prodid", "-//Streaming Summary (30d backfill)//")
cal.add("version", "2.0")

if items:
    evt = Event()
    evt.add("summary", f"Now Streaming (last 30d as of {today.isoformat()})")
    evt.add("description", "\n".join(items))
    # schedule at 09:00 UTC
    start = datetime.utcnow().replace(
        hour=9, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
    )
    end = start + timedelta(hours=1)
    evt.add("dtstart", start)
    evt.add("dtend", end)
    evt.add("dtstamp", datetime.utcnow().replace(tzinfo=timezone.utc))
    evt.add("uid", f"{today}-stream-summary@movies")
    cal.add_component(evt)

with open(OUTPUT_FILE, "wb") as f:
    f.write(cal.to_ical())

print(f"Wrote {OUTPUT_FILE}, backfilled {len(items)} movies from {thirty_ago} to {today}")

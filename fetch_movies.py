#!/usr/bin/env python3
import os
import requests
from datetime import datetime, timedelta, timezone
from collections import defaultdict
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

# 1) Discover all theatrically released movies in last 30 days
all_movies = []
page = 1
while True:
    resp = requests.get(DISCOVER_URL, params={
        "api_key": API_KEY,
        "language": "en-US",
        "sort_by": "primary_release_date.desc",
        "primary_release_date.gte": thirty_ago.isoformat(),
        "primary_release_date.lte": today.isoformat(),
        "page": page,
    })
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", [])
    if not results:
        break
    all_movies.extend(results)
    if page >= data.get("total_pages", 1):
        break
    page += 1

# 2) Check streaming and group by release date
by_date = defaultdict(list)

for m in all_movies:
    mid = m["id"]
    # providers
    wp = requests.get(
        WATCH_PROVIDERS.format(id=mid),
        params={"api_key": API_KEY}
    ).json().get("results", {})
    platforms = sorted({
        p["provider_name"]
        for r in REGIONS
        for p in wp.get(r, {}).get("flatrate", [])
    })
    if not platforms:
        continue

    # trailer key
    vids = requests.get(
        VIDEO_URL.format(id=mid),
        params={"api_key": API_KEY}
    ).json().get("results", [])
    key = next(
        (v["key"] for v in vids
         if v["site"] == "YouTube" and v["type"] == "Trailer"),
        None
    )
    trailer = f"\nTrailer: https://youtu.be/{key}" if key else ""

    # determine the date to group by (use theatrical release date if available)
    rel = m.get("release_date")
    try:
        rel_date = datetime.strptime(rel, "%Y-%m-%d").date()
    except Exception:
        rel_date = today

    if rel_date < thirty_ago or rel_date > today:
        continue

    title = m.get("title") or m.get("name") or "Unknown"
    line = f"- {title} ({', '.join(platforms)}){trailer}"
    by_date[rel_date].append(line)

# 3) Build the calendar with one event per date
cal = Calendar()
cal.add("prodid", "-//Daily Streaming Releases//")
cal.add("version", "2.0")

for rel_date, lines in sorted(by_date.items()):
    evt = Event()
    evt.add("summary", f"Now Streaming on {rel_date.isoformat()}")
    evt.add("description", "\n".join(lines))
    # place event at 09:00 UTC on that date
    start = datetime.combine(rel_date, datetime.min.time()).replace(
        hour=9, tzinfo=timezone.utc
    )
    end = start + timedelta(hours=1)
    evt.add("dtstart", start)
    evt.add("dtend", end)
    evt.add("dtstamp", datetime.now(timezone.utc))
    evt.add("uid", f"{rel_date.isoformat()}-stream@movies")
    cal.add_component(evt)

with open(OUTPUT_FILE, "wb") as f:
    f.write(cal.to_ical())

print(f"Wrote {OUTPUT_FILE}, created {len(by_date)} daily events")

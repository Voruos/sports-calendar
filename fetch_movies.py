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

# selective thresholds
HOLLYWOOD_POP_THRESH = 50.0
# ────────────────────────────────────────────────────────────────────────────────

if not API_KEY:
    raise RuntimeError("TMDB_API_KEY environment variable not set")

today      = datetime.now(TZ).date()
thirty_ago = today - timedelta(days=30)

# 1) Discover all theatrical releases in last 30 days
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

# 2) Filter, fetch streaming & metadata, then group by release date
by_date = defaultdict(list)

for m in all_movies:
    lang = m.get("original_language", "")
    pop  = m.get("popularity", 0.0)

    # apply Hollywood threshold
    if lang == "en" and pop < HOLLYWOOD_POP_THRESH:
        continue

    mid = m["id"]
    # check streaming providers
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

    # find YouTube trailer
    vids = requests.get(
        VIDEO_URL.format(id=mid),
        params={"api_key": API_KEY}
    ).json().get("results", [])
    key = next(
        (v["key"] for v in vids if v["site"] == "YouTube" and v["type"] == "Trailer"),
        None
    )
    trailer = f"\nTrailer: https://youtu.be/{key}" if key else ""

    # determine release date
    rel = m.get("release_date", "")
    try:
        rel_date = datetime.strptime(rel, "%Y-%m-%d").date()
    except Exception:
        rel_date = today
    if not (thirty_ago <= rel_date <= today):
        continue

    # store tuple for sorting
    title = m.get("title") or m.get("name") or "Unknown"
    line  = f"- {title} ({', '.join(platforms)}){trailer}"
    by_date[rel_date].append((pop, line))

# 3) Build the calendar: one event per date, sorted by popularity
cal = Calendar()
cal.add("prodid", "-//Daily Streaming Releases//")
cal.add("version", "2.0")

for rel_date in sorted(by_date):
    items = by_date[rel_date]
    # sort descending by pop
    items.sort(key=lambda x: x[0], reverse=True)
    lines = [line for _, line in items]

    evt = Event()
    evt.add("summary", f"Now Streaming: {' • '.join([l.split('(')[0].strip('- ') for l in lines])}")
    evt.add("description", "\n".join(lines))

    # schedule at 09:00 UTC on release date
    start = datetime.combine(rel_date, datetime.min.time()).replace(hour=9, tzinfo=timezone.utc)
    end   = start + timedelta(hours=1)
    evt.add("dtstart", start)
    evt.add("dtend", end)
    evt.add("dtstamp", datetime.now(timezone.utc))
    evt.add("uid", f"{rel_date.isoformat()}-stream@movies")
    cal.add_component(evt)

# write out
with open(OUTPUT_FILE, "wb") as f:
    f.write(cal.to_ical())

print(f"Wrote {OUTPUT_FILE} with {len(by_date)} daily events")

#!/usr/bin/env python3
import os
import requests
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from icalendar import Calendar, Event
import pytz

# ─── CONFIG ─────────────────────────────────────────────────────────────
API_KEY          = os.getenv("TMDB_API_KEY")
OUTPUT_FILE      = "movies.ics"
TZ               = pytz.timezone("Asia/Dhaka")
REGIONS          = ["IN", "BD"]
MOVIE_DISCOVER   = "https://api.themoviedb.org/3/discover/movie"
SERIES_DISCOVER  = "https://api.themoviedb.org/3/discover/tv"
WATCH_PROVIDERS  = "https://api.themoviedb.org/3/{type}/{id}/watch/providers"
VIDEO_URL        = "https://api.themoviedb.org/3/{type}/{id}/videos"
HOLLYWOOD_POP    = 50.0
ALLOWED_LANGS    = {"en", "hi", "bn"}
DOC_GENRE_ID     = 99
today       = datetime.now(TZ).date()
past_start  = today - timedelta(days=30)
future_end  = today + timedelta(days=30)
# ─────────────────────────────────────────────────────────────────────────

if not API_KEY:
    raise RuntimeError("TMDB_API_KEY environment variable not set")

def discover(endpoint, params):
    page, items = 1, []
    while True:
        r = requests.get(endpoint, {**params, "page": page})
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        if not results:
            break
        items.extend(results)
        if page >= data.get("total_pages", 1):
            break
        page += 1
    return items

by_date = defaultdict(list)

def process_item(item, kind):
    lang = item.get("original_language", "")
    pop  = item.get("popularity", 0.0)
    genres = item.get("genre_ids", [])

    # Language & documentary filter
    if lang not in ALLOWED_LANGS or DOC_GENRE_ID in genres:
        return
    # Hollywood popularity threshold applies to both movies & series
    if lang == "en" and pop < HOLLYWOOD_POP:
        return

    title = item.get("title") if kind == "movie" else item.get("name")
    mid   = item["id"]
    label = "Movie" if kind == "movie" else "Series"

    # Streaming providers
    wp = requests.get(
        WATCH_PROVIDERS.format(type=kind, id=mid),
        params={"api_key": API_KEY}
    ).json().get("results", {})
    platforms = sorted({
        p["provider_name"]
        for r in REGIONS
        for p in wp.get(r, {}).get("flatrate", [])
    })
    if not platforms:
        return

    # Optional trailer
    vids = requests.get(
        VIDEO_URL.format(type=kind, id=mid),
        params={"api_key": API_KEY}
    ).json().get("results", [])
    key = next((v["key"] for v in vids if v["site"]=="YouTube" and v["type"]=="Trailer"), None)
    trailer = f"\nTrailer: https://youtu.be/{key}" if key else ""

    # Determine event date
    date_field = "release_date" if kind == "movie" else "first_air_date"
    dstr = item.get(date_field) or today.isoformat()
    try:
        d = datetime.fromisoformat(dstr).date()
    except:
        d = today
    if not (past_start <= d <= future_end):
        return

    line = f"{title} ({', '.join(platforms)}){trailer} [{label}]"
    by_date[d].append((pop, line))

# Fetch and process content
movies_past   = discover(MOVIE_DISCOVER, {
    "api_key": API_KEY,
    "language": "en-US",
    "sort_by": "primary_release_date.desc",
    "primary_release_date.gte": past_start.isoformat(),
    "primary_release_date.lte": today.isoformat(),
})
movies_future = discover(MOVIE_DISCOVER, {
    "api_key": API_KEY,
    "language": "en-US",
    "sort_by": "primary_release_date.asc",
    "primary_release_date.gte": today.isoformat(),
    "primary_release_date.lte": future_end.isoformat(),
    "with_release_type": 4,
})
series_past   = discover(SERIES_DISCOVER, {
    "api_key": API_KEY,
    "language": "en-US",
    "sort_by": "first_air_date.desc",
    "first_air_date.gte": past_start.isoformat(),
    "first_air_date.lte": today.isoformat(),
})
series_future = discover(SERIES_DISCOVER, {
    "api_key": API_KEY,
    "language": "en-US",
    "sort_by": "first_air_date.asc",
    "first_air_date.gte": today.isoformat(),
    "first_air_date.lte": future_end.isoformat(),
})

for m in movies_past:    process_item(m, "movie")
for m in movies_future:  process_item(m, "movie")
for s in series_past:    process_item(s, "tv")
for s in series_future:  process_item(s, "tv")

# Build the calendar
cal = Calendar()
cal.add("prodid", "-//Movies & Series Calendar//")
cal.add("version", "2.0")

for d in sorted(by_date):
    items = by_date[d]
    items.sort(key=lambda x: x[0], reverse=True)
    titles = " • ".join([line.split(" (")[0] for _, line in items])
    evt = Event()
    evt.add("summary", f"Now Streaming: {titles}")
    evt.add("description", "\n".join([line for _, line in items]))

    start = datetime.combine(d, datetime.min.time()).replace(hour=9, tzinfo=timezone.utc)
    evt.add("dtstart", start)
    evt.add("dtend",   start + timedelta(hours=1))
    evt.add("dtstamp", datetime.now(timezone.utc))
    evt.add("uid",     f"{d.isoformat()}-stream@all")
    cal.add_component(evt)

with open(OUTPUT_FILE, "wb") as f:
    f.write(cal.to_ical())

print(f"Wrote {OUTPUT_FILE} with {len(by_date)} daily events")

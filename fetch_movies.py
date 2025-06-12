#!/usr/bin/env python3
import os
import requests
from datetime import datetime
from icalendar import Calendar, Event
import pytz

# ─── CONFIG ───────────────────────────────────────────────────────────────────
API_KEY        = os.getenv("TMDB_API_KEY")
REGIONS        = ["IN", "BD"]  # India & Bangladesh
NOW_PLAYING    = "https://api.themoviedb.org/3/movie/now_playing"
WATCH_PROVIDER = "https://api.themoviedb.org/3/movie/{id}/watch/providers"
OUTPUT_FILE    = "movies.ics"
TZ             = pytz.timezone("Asia/Dhaka")
# ────────────────────────────────────────────────────────────────────────────────

if not API_KEY:
    raise RuntimeError("TMDB_API_KEY environment variable not set")

cal = Calendar()
cal.add("prodid", "-//Streaming Releases//mx")
cal.add("version", "2.0")

seen = set()
for region in REGIONS:
    resp = requests.get(NOW_PLAYING, params={
        "api_key": API_KEY,
        "region": region,
        "language": "en-US",
        "page": 1
    })
    resp.raise_for_status()
    for m in resp.json().get("results", []):
        mid = m["id"]
        if mid in seen:
            continue
        seen.add(mid)

        wp = requests.get(WATCH_PROVIDER.format(id=mid),
                          params={"api_key": API_KEY}).json().get("results", {})
        providers = []
        for r in REGIONS:
            for p in wp.get(r, {}).get("flatrate", []):
                providers.append(p["provider_name"])
        if not providers:
            continue

        evt = Event()
        now = datetime.now(TZ)
        evt.add("summary", f"🎬 Now Streaming: {m['title']}")
        evt.add("dtstart", now.date())
        evt.add("dtstamp", now)
        evt.add("description", "Available on: " + ", ".join(sorted(set(providers))))
        evt.add("uid", f"{mid}-stream@movies")
        cal.add_component(evt)

with open(OUTPUT_FILE, "wb") as f:
    f.write(cal.to_ical())

print(f"Wrote {OUTPUT_FILE}, checked {len(seen)} titles")

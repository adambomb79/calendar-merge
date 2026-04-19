import os
import urllib.request
from datetime import datetime, timezone

OUTPUT_DIR = "docs"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "combined.ics")

CALENDARS = [
    ("ICAL_URL_GOPHERSFOOTBALL", "🏈"),
    ("ICAL_URL_NFLPRIMETIME", "🏈"),
    ("ICAL_URL_TIMBERWOLVES", "🏀"),
    ("ICAL_URL_TWINS", "⚾"),
    ("ICAL_URL_VIKINGS", "🏈"),
]


def prefix_summary(event_lines, emoji):
    updated = []
    changed = False

    for line in event_lines:
        if line.startswith("SUMMARY:"):
            summary = line[len("SUMMARY:"):].strip()
            if not summary.startswith(emoji):
                line = f"SUMMARY:{emoji} {summary}"
            changed = True
        updated.append(line)

    return updated, changed


calendar_sources = []
for secret_name, emoji in CALENDARS:
    url = os.getenv(secret_name)
    if url:
        calendar_sources.append((url.strip(), emoji, secret_name))

if not calendar_sources:
    raise RuntimeError("No calendar URLs found in GitHub Actions secrets.")

events = []
seen_uids = set()

for url, emoji, secret_name in calendar_sources:
    with urllib.request.urlopen(url) as response:
        text = response.read().decode("utf-8", errors="replace")

    lines = text.splitlines()
    in_event = False
    event_lines = []

    for line in lines:
        stripped = line.strip()

        if stripped == "BEGIN:VEVENT":
            in_event = True
            event_lines = [line]

        elif stripped == "END:VEVENT" and in_event:
            event_lines.append(line)
            in_event = False

            uid = None
            for ev_line in event_lines:
                if ev_line.startswith("UID:"):
                    uid = ev_line[4:].strip()
                    break

            if uid and uid in seen_uids:
                continue
            if uid:
                seen_uids.add(uid)

            event_lines, _ = prefix_summary(event_lines, emoji)
            events.append(event_lines)

        elif in_event:
            event_lines.append(line)

os.makedirs(OUTPUT_DIR, exist_ok=True)

timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

with open(OUTPUT_FILE, "w", encoding="utf-8", newline="\r\n") as f:
    f.write("BEGIN:VCALENDAR\r\n")
    f.write("VERSION:2.0\r\n")
    f.write("PRODID:-//Calendar Merge//EN\r\n")
    f.write("CALSCALE:GREGORIAN\r\n")
    f.write("X-WR-CALNAME:Merged Calendar\r\n")
    f.write("X-WR-TIMEZONE:UTC\r\n")
    f.write(f"LAST-MODIFIED:{timestamp}\r\n")

    for event in events:
        for line in event:
            f.write(line.rstrip("\r\n") + "\r\n")

    f.write("END:VCALENDAR\r\n")

print(f"Wrote {OUTPUT_FILE} with {len(events)} events from {len(calendar_sources)} source calendars.")

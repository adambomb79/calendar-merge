import os
import urllib.request
from datetime import datetime, timezone

OUTPUT_DIR = "docs"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "combined.ics")

calendar_urls = []
i = 1
while True:
    value = os.getenv(f"ICAL_URL_{i}")
    if not value:
        break
    calendar_urls.append(value.strip())
    i += 1

if not calendar_urls:
    raise RuntimeError("No calendar URLs found. Set ICAL_URL_1, ICAL_URL_2, etc.")

events = []
seen_uids = set()

for url in calendar_urls:
    with urllib.request.urlopen(url) as response:
        text = response.read().decode("utf-8", errors="replace")

    lines = text.splitlines()
    in_event = False
    event_lines = []

    for line in lines:
        if line.strip() == "BEGIN:VEVENT":
            in_event = True
            event_lines = [line]
        elif line.strip() == "END:VEVENT" and in_event:
            event_lines.append(line)
            in_event = False

            uid = None
            for ev_line in event_lines:
                if ev_line.startswith("UID:"):
                    uid = ev_line[4:].strip()
                    break

            if uid:
                if uid in seen_uids:
                    continue
                seen_uids.add(uid)

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
    f.write(f"X-WR-CALNAME:Merged Calendar\r\n")
    f.write(f"X-WR-TIMEZONE:UTC\r\n")
    f.write(f"LAST-MODIFIED:{timestamp}\r\n")

    for event in events:
        for line in event:
            f.write(line.rstrip("\r\n") + "\r\n")

    f.write("END:VCALENDAR\r\n")

print(f"Wrote {OUTPUT_FILE} with {len(events)} events from {len(calendar_urls)} source calendars.")

import os
import urllib.request
from datetime import datetime, timezone, timedelta

OUTPUT_DIR = "docs"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "combined.ics")

PAST_DAYS = 120
FUTURE_DAYS = 400

CALENDARS = [
    ("ICAL_URL_GOPHERSFOOTBALL", "🏈"),
    ("ICAL_URL_NFLPRIMETIME", "🏈"),
    ("ICAL_URL_TIMBERWOLVES", "🏀"),
    ("ICAL_URL_TWINS", "⚾"),
    ("ICAL_URL_VIKINGS", "🏈"),
]


def normalize_url(url):
    url = url.strip()
    if url.lower().startswith("webcal://"):
        return "https://" + url[len("webcal://"):]
    return url


def prefix_summary(event_lines, emoji):
    updated = []
    for line in event_lines:
        if line.startswith("SUMMARY:"):
            summary = line[len("SUMMARY:"):].strip()
            if not summary.startswith(emoji):
                line = f"SUMMARY:{emoji} {summary}"
        updated.append(line)
    return updated


def unfold_ics_lines(lines):
    unfolded = []
    for line in lines:
        if unfolded and (line.startswith(" ") or line.startswith("\t")):
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def get_prop_value(event_lines, prop_name):
    prefix = prop_name + ":"
    alt_prefix = prop_name + ";"
    for line in event_lines:
        if line.startswith(prefix):
            return line[len(prefix):].strip()
        if line.startswith(alt_prefix):
            parts = line.split(":", 1)
            if len(parts) == 2:
                return parts[1].strip()
    return None


def parse_dtstart(event_lines):
    value = get_prop_value(event_lines, "DTSTART")
    if not value:
        return None

    value = value.strip()

    # DATE only: 20260427
    if len(value) == 8 and value.isdigit():
        try:
            return datetime.strptime(value, "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    # UTC datetime: 20251005T010000Z
    if value.endswith("Z"):
        try:
            return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    # Floating/local datetime: 20251005T010000
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def in_date_window(event_lines, window_start, window_end):
    dtstart = parse_dtstart(event_lines)
    if dtstart is None:
        return True
    return window_start <= dtstart <= window_end


calendar_sources = []
for secret_name, emoji in CALENDARS:
    url = os.getenv(secret_name)
    if url:
        calendar_sources.append((normalize_url(url), emoji, secret_name))

if not calendar_sources:
    raise RuntimeError("No calendar URLs found in GitHub Actions secrets.")

now = datetime.now(timezone.utc)
window_start = now - timedelta(days=PAST_DAYS)
window_end = now + timedelta(days=FUTURE_DAYS)

events = []
seen_uids = set()
per_calendar_counts = {}
per_calendar_skipped_dupe = {}
per_calendar_skipped_window = {}
per_calendar_errors = {}

for url, emoji, secret_name in calendar_sources:
    per_calendar_counts[secret_name] = 0
    per_calendar_skipped_dupe[secret_name] = 0
    per_calendar_skipped_window[secret_name] = 0

    try:
        with urllib.request.urlopen(url) as response:
            text = response.read().decode("utf-8", errors="replace")
    except Exception as e:
        per_calendar_errors[secret_name] = str(e)
        print(f"[ERROR] {secret_name}: {e}")
        continue

    lines = unfold_ics_lines(text.splitlines())
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

            uid = get_prop_value(event_lines, "UID")
            if uid and uid in seen_uids:
                per_calendar_skipped_dupe[secret_name] += 1
                continue
            if uid:
                seen_uids.add(uid)

            if not in_date_window(event_lines, window_start, window_end):
                per_calendar_skipped_window[secret_name] += 1
                continue

            event_lines = prefix_summary(event_lines, emoji)
            events.append(event_lines)
            per_calendar_counts[secret_name] += 1

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

print("")
print("Calendar merge summary")
print("----------------------")
for secret_name, _emoji in CALENDARS:
    if secret_name in per_calendar_errors:
        print(f"{secret_name}: ERROR - {per_calendar_errors[secret_name]}")
    elif secret_name in per_calendar_counts:
        print(
            f"{secret_name}: kept={per_calendar_counts[secret_name]}, "
            f"dupe_skipped={per_calendar_skipped_dupe[secret_name]}, "
            f"window_skipped={per_calendar_skipped_window[secret_name]}"
        )

print("")
print(
    f"Wrote {OUTPUT_FILE} with {len(events)} total events "
    f"from {len(calendar_sources)} configured source calendars."
)
print(
    f"Date window: {window_start.strftime('%Y-%m-%d')} "
    f"to {window_end.strftime('%Y-%m-%d')}"
)

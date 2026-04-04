"""Calendar write tool — creates/updates ICS files on ubuntuserver calendar server."""
import subprocess
import os
import uuid
from datetime import datetime

CALENDAR_HOST = "root@10.34.43.11"
CALENDAR_DIR = "/srv/calendars"
SSH_KEY = "/home/sh1pwr3ck/.ssh/id_rsa"
SSH_OPTS = ["-o", "StrictHostKeyChecking=no", "-o", "IdentitiesOnly=yes", "-i", SSH_KEY]
CALENDAR_BASE_URL = "http://10.34.43.11:8088"


def create_calendar_event(
    calendar_name: str,
    summary: str,
    start_dt: str,
    end_dt: str,
    description: str = "",
    recurrence: str = ""
) -> str:
    """
    Add or update an event in a named ICS calendar on the calendar server.
    calendar_name: filename without .ics (e.g. 'workouts')
    start_dt / end_dt: 'YYYY-MM-DD HH:MM' in America/New_York
    recurrence: optional RRULE string e.g. 'FREQ=WEEKLY;BYDAY=MO,WE,FR'
    """
    try:
        start = datetime.strptime(start_dt, "%Y-%m-%d %H:%M")
        end = datetime.strptime(end_dt, "%Y-%m-%d %H:%M")
    except ValueError as e:
        return f"Date parse error: {e}. Use format: YYYY-MM-DD HH:MM"

    event_uid = str(uuid.uuid4())
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dtstart = start.strftime("%Y%m%dT%H%M%S")
    dtend = end.strftime("%Y%m%dT%H%M%S")
    desc_clean = description.replace("\n", "\\n").replace(",", "\\,")

    vevent = f"""BEGIN:VEVENT
UID:{event_uid}
DTSTAMP:{dtstamp}
DTSTART;TZID=America/New_York:{dtstart}
DTEND;TZID=America/New_York:{dtend}
SUMMARY:{summary}
DESCRIPTION:{desc_clean}
CATEGORIES:Workout
"""
    if recurrence:
        vevent += f"RRULE:{recurrence}\n"
    vevent += "END:VEVENT"

    remote_path = f"{CALENDAR_DIR}/{calendar_name}.ics"

    # Check if calendar file exists on server
    check = subprocess.run(
        ["ssh"] + SSH_OPTS + [CALENDAR_HOST, f"test -f {remote_path} && echo exists || echo new"],
        capture_output=True, text=True, timeout=10
    )
    file_exists = "exists" in check.stdout

    if file_exists:
        # Append event before END:VCALENDAR
        script = f"""python3 -c "
content = open('{remote_path}').read()
event = '''{vevent}'''
content = content.replace('END:VCALENDAR', event + '\\nEND:VCALENDAR')
open('{remote_path}', 'w').write(content)
print('appended')
" """
    else:
        # Create new calendar file
        cal_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//1st Mate Coach//NHN//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
X-WR-CALNAME:{calendar_name}
X-WR-TIMEZONE:America/New_York
{vevent}
END:VCALENDAR"""
        script = f"cat > {remote_path} << 'ICSEOF'\n{cal_content}\nICSEOF"

    result = subprocess.run(
        ["ssh"] + SSH_OPTS + [CALENDAR_HOST, script],
        capture_output=True, text=True, timeout=15
    )

    if result.returncode != 0:
        return f"Calendar write error: {result.stderr}"

    url = f"{CALENDAR_BASE_URL}/{calendar_name}.ics"
    return f"Event added to {calendar_name} calendar.\nSubscribe URL: {url}\nEvent: {summary} on {start_dt}"

"""Replace a full ICS calendar file on the calendar server."""
import subprocess
import tempfile
import os

CALENDAR_HOST = "root@10.34.43.11"
CALENDAR_DIR = "/srv/calendars"
SSH_KEY = "/home/sh1pwr3ck/.ssh/id_rsa"
SSH_OPTS = ["-o", "StrictHostKeyChecking=no", "-o", "IdentitiesOnly=yes", "-i", SSH_KEY]
CALENDAR_BASE_URL = "http://10.34.43.11:8088"


def replace_calendar(calendar_name: str, ics_content: str) -> str:
    """Completely replace a calendar ICS file on the server."""
    tmp = tempfile.mktemp(suffix='.ics')
    try:
        with open(tmp, 'w') as f:
            f.write(ics_content)
        result = subprocess.run(
            ["scp"] + SSH_OPTS + [tmp, f"{CALENDAR_HOST}:{CALENDAR_DIR}/{calendar_name}.ics"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return f"Calendar replace error: {result.stderr}"
        return f"Calendar '{calendar_name}' updated.\nSubscribe URL: {CALENDAR_BASE_URL}/{calendar_name}.ics"
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

"""Calendar tool — reads Thunderbird SQLite calendar."""
import sqlite3
import os
import shutil
import tempfile
from datetime import datetime, timedelta

CALENDAR_DB = '/home/sh1pwr3ck/.thunderbird/mczprqan.SH!PWR#CK/calendar-data/local.sqlite'


def get_calendar_events(days_ahead: int = 7) -> str:
    if not os.path.exists(CALENDAR_DB):
        return f"Calendar database not found at {CALENDAR_DB}"
    try:
        # Copy to temp file to avoid Thunderbird's lock
        tmp = tempfile.mktemp(suffix='.sqlite')
        shutil.copy2(CALENDAR_DB, tmp)
        conn = sqlite3.connect(tmp)
        cursor = conn.cursor()
        now = datetime.now()
        future = now + timedelta(days=days_ahead)
        now_us = int(now.timestamp() * 1000000)
        future_us = int(future.timestamp() * 1000000)
        cursor.execute("""
            SELECT title, event_start, event_end
            FROM cal_events
            WHERE event_start >= ? AND event_start <= ?
            ORDER BY event_start
        """, (now_us, future_us))
        events = cursor.fetchall()
        conn.close()
        os.unlink(tmp)
        if not events:
            return f"No events in the next {days_ahead} days."
        lines = []
        for title, start, end in events:
            dt = datetime.fromtimestamp(start / 1000000)
            lines.append(f"{dt.strftime('%a %b %d %I:%M %p')} — {title}")
        return '\n'.join(lines)
    except Exception as e:
        return f"Calendar error: {e}"

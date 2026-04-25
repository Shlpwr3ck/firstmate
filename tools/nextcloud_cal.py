"""iCloud CalDAV calendar tool — read and write events via iCloud CalDAV."""
import os
import uuid
from datetime import datetime, timedelta, timezone
import requests
from xml.etree import ElementTree as ET

ICLOUD_USER = os.getenv("ICLOUD_USER", "")
ICLOUD_PASS = os.getenv("ICLOUD_PASS", "")
ICLOUD_CAL  = os.getenv("ICLOUD_CALENDAR", "Jax")

CALDAV_BASE = "https://caldav.icloud.com"
_NS = {"D": "DAV:", "C": "urn:ietf:params:xml:ns:caldav"}


def _auth():
    return (ICLOUD_USER, ICLOUD_PASS)


def _propfind(url: str, body: str, depth: str = "0") -> ET.Element | None:
    try:
        resp = requests.request(
            "PROPFIND", url,
            auth=_auth(),
            headers={"Content-Type": "application/xml; charset=utf-8", "Depth": depth},
            data=body.encode("utf-8"),
            timeout=15,
            allow_redirects=True,
        )
        if resp.status_code not in (200, 207):
            return None
        return ET.fromstring(resp.text)
    except Exception:
        return None


def _discover_home_url() -> str | None:
    """Return the calendar home-set URL for the iCloud account."""
    root = _propfind(
        CALDAV_BASE + "/",
        '<?xml version="1.0" encoding="utf-8"?>'
        '<D:propfind xmlns:D="DAV:"><D:prop>'
        '<D:current-user-principal/>'
        '</D:prop></D:propfind>',
    )
    if root is None:
        return None
    principal = root.find(".//D:current-user-principal/D:href", _NS)
    if principal is None:
        return None
    principal_url = (CALDAV_BASE + principal.text) if principal.text.startswith("/") else principal.text

    root = _propfind(
        principal_url,
        '<?xml version="1.0" encoding="utf-8"?>'
        '<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav"><D:prop>'
        '<C:calendar-home-set/>'
        '</D:prop></D:propfind>',
    )
    if root is None:
        return None
    home = root.find(".//C:calendar-home-set/D:href", _NS)
    if home is None:
        return None
    return (CALDAV_BASE + home.text) if home.text.startswith("/") else home.text


def _discover_calendar_url() -> str | None:
    """Return the URL for ICLOUD_CAL, or the home URL if not found by name."""
    home_url = _discover_home_url()
    if not home_url:
        return None

    root = _propfind(
        home_url.rstrip("/") + "/",
        '<?xml version="1.0" encoding="utf-8"?>'
        '<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav"><D:prop>'
        '<D:displayname/><D:resourcetype/>'
        '</D:prop></D:propfind>',
        depth="1",
    )
    if root is None:
        return home_url

    for response in root.findall(".//D:response", _NS):
        if response.find(".//C:calendar", _NS) is None:
            continue
        href = response.find("D:href", _NS)
        name = response.find(".//D:displayname", _NS)
        if href is not None and name is not None:
            if ICLOUD_CAL.lower() in (name.text or "").lower():
                url = href.text
                return (CALDAV_BASE + url) if url.startswith("/") else url

    return home_url


def _list_calendar_urls(home_url: str) -> list[str]:
    """Return individual calendar collection URLs under the home set."""
    root = _propfind(
        home_url.rstrip("/") + "/",
        '<?xml version="1.0" encoding="utf-8"?>'
        '<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav"><D:prop>'
        '<D:resourcetype/>'
        '</D:prop></D:propfind>',
        depth="1",
    )
    if root is None:
        return [home_url]
    urls = []
    base = home_url.split("/", 3)[:3]  # https://p124-caldav.icloud.com
    server_base = "/".join(base)
    for response in root.findall(".//D:response", _NS):
        if response.find(".//C:calendar", _NS) is None:
            continue
        href = response.find("D:href", _NS)
        if href is not None:
            url = href.text
            urls.append((server_base + url) if url.startswith("/") else url)
    return urls or [home_url]


def get_calendar_events(days_ahead: int = 7) -> str:
    """Fetch upcoming events across all iCloud calendars via CalDAV REPORT."""
    home_url = _discover_home_url()
    if not home_url:
        return "iCloud CalDAV: authentication failed or could not discover calendar URL. Check ICLOUD_USER and ICLOUD_PASS."

    cal_urls = _list_calendar_urls(home_url)

    now     = datetime.now(timezone.utc)
    end     = now + timedelta(days=days_ahead)
    dtstart = now.strftime("%Y%m%dT%H%M%SZ")
    dtend   = end.strftime("%Y%m%dT%H%M%SZ")

    body = f"""<?xml version="1.0" encoding="utf-8"?>
<C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:prop><C:calendar-data/></D:prop>
  <C:filter>
    <C:comp-filter name="VCALENDAR">
      <C:comp-filter name="VEVENT">
        <C:time-range start="{dtstart}" end="{dtend}"/>
      </C:comp-filter>
    </C:comp-filter>
  </C:filter>
</C:calendar-query>"""

    all_events = []
    errors = []
    for cal_url in cal_urls:
        try:
            resp = requests.request(
                "REPORT", cal_url.rstrip("/") + "/",
                auth=_auth(),
                headers={"Content-Type": "application/xml; charset=utf-8", "Depth": "1"},
                data=body.encode("utf-8"),
                timeout=20,
            )
            if resp.status_code in (200, 207):
                all_events.extend(_extract_events(resp.text))
            else:
                errors.append(f"{cal_url.split('/')[-2]}: {resp.status_code}")
        except Exception as e:
            errors.append(str(e))

    if not all_events:
        msg = f"No events in the next {days_ahead} days."
        if errors:
            msg += f" (errors: {'; '.join(errors)})"
        return msg

    all_events.sort(key=lambda e: e.get("start_raw", ""))
    lines = []
    for e in all_events:
        lines.append(f"{e['start']} — {e['summary']}")
        if e.get("location"):
            lines.append(f"   @ {e['location']}")
        if e.get("description"):
            lines.append(f"   {e['description'][:120]}")
    return "\n".join(lines)


def _extract_events(xml_text: str) -> list:
    """Parse CalDAV REPORT XML and return a list of event dicts."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    events = []
    for response in root.findall(".//D:response", _NS):
        cal_data = response.find(".//C:calendar-data", _NS)
        if cal_data is None or not cal_data.text:
            continue
        event = _parse_vevent(cal_data.text)
        if event:
            events.append(event)
    return events


def _parse_vevent(ical: str) -> dict | None:
    in_event = False
    event: dict = {}
    for raw_line in ical.splitlines():
        line = raw_line.strip()
        if line == "BEGIN:VEVENT":
            in_event = True
            event = {}
            continue
        if line == "END:VEVENT":
            break
        if not in_event or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.split(";")[0].upper()
        if key == "SUMMARY":
            event["summary"] = val
        elif key == "DTSTART":
            event["start_raw"] = val
            event["start"] = _fmt_dt(val)
        elif key == "LOCATION":
            event["location"] = val
        elif key == "DESCRIPTION":
            event["description"] = val.replace("\\n", " ").replace("\\,", ",")
    return event if event.get("summary") else None


def _fmt_dt(raw: str) -> str:
    clean = raw.replace("Z", "").replace("-", "").replace(":", "")
    try:
        if "T" in clean:
            return datetime.strptime(clean, "%Y%m%dT%H%M%S").strftime("%a %b %d %I:%M %p")
        return datetime.strptime(clean, "%Y%m%d").strftime("%a %b %d (all day)")
    except Exception:
        return raw


def delete_calendar_event(summary: str) -> str:
    """Delete iCloud calendar events whose summary contains the search string."""
    home_url = _discover_home_url()
    if not home_url:
        return "iCloud CalDAV: authentication failed."

    cal_urls = _list_calendar_urls(home_url)

    now     = datetime.now(timezone.utc)
    dtstart = (now - timedelta(days=7)).strftime("%Y%m%dT%H%M%SZ")
    dtend   = (now + timedelta(days=365)).strftime("%Y%m%dT%H%M%SZ")

    body = f"""<?xml version="1.0" encoding="utf-8"?>
<C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:prop><D:getetag/><C:calendar-data/></D:prop>
  <C:filter>
    <C:comp-filter name="VCALENDAR">
      <C:comp-filter name="VEVENT">
        <C:time-range start="{dtstart}" end="{dtend}"/>
      </C:comp-filter>
    </C:comp-filter>
  </C:filter>
</C:calendar-query>"""

    deleted = []
    errors  = []

    for cal_url in cal_urls:
        try:
            resp = requests.request(
                "REPORT", cal_url.rstrip("/") + "/",
                auth=_auth(),
                headers={"Content-Type": "application/xml; charset=utf-8", "Depth": "1"},
                data=body.encode("utf-8"),
                timeout=20,
            )
            if resp.status_code not in (200, 207):
                continue
            root = ET.fromstring(resp.text)
            server_base = "/".join(cal_url.split("/", 3)[:3])
            for response in root.findall(".//D:response", _NS):
                cal_data = response.find(".//C:calendar-data", _NS)
                href_el  = response.find("D:href", _NS)
                if cal_data is None or not cal_data.text or href_el is None:
                    continue
                event = _parse_vevent(cal_data.text)
                if not event:
                    continue
                if summary.lower() in event.get("summary", "").lower():
                    event_url = href_el.text
                    if event_url.startswith("/"):
                        event_url = server_base + event_url
                    del_resp = requests.delete(event_url, auth=_auth(), timeout=15)
                    if del_resp.status_code in (200, 204):
                        deleted.append(event.get("summary", summary))
                    else:
                        errors.append(f"DELETE {del_resp.status_code}")
        except Exception as e:
            errors.append(str(e))

    if deleted:
        return f"Deleted {len(deleted)} event(s): {', '.join(deleted)}"
    if errors:
        return f"Delete failed: {'; '.join(errors)}"
    return f"No events found matching '{summary}'"


def create_calendar_event(
    summary: str,
    start_dt: str,
    end_dt: str,
    description: str = "",
    location: str = "",
) -> str:
    """Create an event in iCloud Calendar via CalDAV PUT. start/end: 'YYYY-MM-DD HH:MM' Eastern."""
    cal_url = _discover_calendar_url()
    if not cal_url:
        return "iCloud CalDAV: could not discover calendar URL. Check ICLOUD_USER and ICLOUD_PASS."

    try:
        start_naive = datetime.strptime(start_dt, "%Y-%m-%d %H:%M")
        end_naive   = datetime.strptime(end_dt,   "%Y-%m-%d %H:%M")
    except ValueError as e:
        return f"Date parse error: {e}. Use YYYY-MM-DD HH:MM"

    # Convert Eastern → UTC (EDT=UTC-4, EST=UTC-5); use zoneinfo if available
    try:
        from zoneinfo import ZoneInfo
        eastern = ZoneInfo("America/New_York")
        utc     = ZoneInfo("UTC")
        start_utc = start_naive.replace(tzinfo=eastern).astimezone(utc)
        end_utc   = end_naive.replace(tzinfo=eastern).astimezone(utc)
    except Exception:
        # Fallback: assume EDT (UTC-4)
        from datetime import timedelta
        start_utc = start_naive + timedelta(hours=4)
        end_utc   = end_naive   + timedelta(hours=4)

    uid     = str(uuid.uuid4())
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    ics = "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//1st Mate//NHN//EN",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{start_utc.strftime('%Y%m%dT%H%M%SZ')}",
        f"DTEND:{end_utc.strftime('%Y%m%dT%H%M%SZ')}",
        f"SUMMARY:{summary}",
        f"DESCRIPTION:{description.replace(chr(10), chr(92) + 'n')}",
        f"LOCATION:{location}",
        "END:VEVENT",
        "END:VCALENDAR",
    ])

    try:
        resp = requests.put(
            cal_url.rstrip("/") + f"/{uid}.ics",
            auth=_auth(),
            headers={"Content-Type": "text/calendar; charset=utf-8"},
            data=ics.encode("utf-8"),
            timeout=15,
        )
        if resp.status_code in (200, 201, 204):
            return f"Event created in iCloud '{ICLOUD_CAL}' calendar: '{summary}' on {start_dt}"
        return f"CalDAV PUT error {resp.status_code}: {resp.text[:300]}"
    except Exception as e:
        return f"iCloud calendar write error: {e}"

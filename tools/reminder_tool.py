"""Reminder tool — set timed reminders delivered via Signal."""
import json
from datetime import datetime
from pathlib import Path

REMINDER_FILE = Path(__file__).parent.parent / "memory" / "reminders.json"

# Set by main.py before each tool dispatch so reminders know who to notify
_current_sender: str = ""


def set_current_sender(sender: str):
    global _current_sender
    _current_sender = sender


def _load() -> list:
    if REMINDER_FILE.exists():
        try:
            return json.loads(REMINDER_FILE.read_text())
        except Exception:
            pass
    return []


def _save(reminders: list):
    REMINDER_FILE.write_text(json.dumps(reminders, indent=2))


def set_reminder(message: str, remind_at: str) -> str:
    """Set a reminder. remind_at: 'YYYY-MM-DD HH:MM' Eastern."""
    try:
        dt = datetime.strptime(remind_at, "%Y-%m-%d %H:%M")
    except ValueError:
        return "Date format error — use YYYY-MM-DD HH:MM"
    reminders = _load()
    reminders.append({
        "sender":    _current_sender,
        "message":   message,
        "remind_at": dt.isoformat(),
        "sent":      False,
    })
    _save(reminders)
    return f"Reminder set for {remind_at}: {message}"


def list_reminders() -> str:
    """List pending reminders for the current sender."""
    pending = [r for r in _load() if r.get("sender") == _current_sender and not r["sent"]]
    if not pending:
        return "No pending reminders."
    lines = [f"• {r['remind_at'][:16]} — {r['message']}" for r in pending]
    return "\n".join(lines)


def cancel_reminder(keyword: str) -> str:
    """Cancel a pending reminder matching keyword."""
    reminders = _load()
    cancelled = []
    for r in reminders:
        if r.get("sender") == _current_sender and keyword.lower() in r["message"].lower() and not r["sent"]:
            r["sent"] = True
            cancelled.append(r["message"])
    _save(reminders)
    if cancelled:
        return f"Cancelled: {', '.join(cancelled)}"
    return f"No pending reminders matching '{keyword}'"


def check_due_reminders() -> list[dict]:
    """Return due reminders and mark them sent. Called from main poll loop."""
    now = datetime.now()
    reminders = _load()
    due = []
    changed = False
    for r in reminders:
        if not r["sent"] and datetime.fromisoformat(r["remind_at"]) <= now:
            r["sent"] = True
            due.append(r)
            changed = True
    if changed:
        _save(reminders)
    return due

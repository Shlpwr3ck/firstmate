"""Persistent memory — survives container restarts."""
import json
import os
from datetime import datetime

MEMORY_FILE = '/home/sh1pwr3ck/firstmate/memory/memory.json'


def _load():
    if not os.path.exists(MEMORY_FILE):
        return {}
    with open(MEMORY_FILE, 'r') as f:
        return json.load(f)


def _save(data):
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def save_memory(key: str, value: str) -> str:
    data = _load()
    data[key] = {'value': value, 'updated': datetime.now().isoformat()}
    _save(data)
    return f"Saved: {key}"


def get_memory(key: str) -> str:
    data = _load()
    if key not in data:
        return f"No memory found for: {key}"
    e = data[key]
    return f"{e['value']}  (saved {e['updated'][:10]})"


def list_memories() -> str:
    data = _load()
    if not data:
        return "No memories saved yet."
    lines = [f"• {k}: {str(v['value'])[:80]}" for k, v in sorted(data.items())]
    return '\n'.join(lines)


def delete_memory(key: str) -> str:
    data = _load()
    if key not in data:
        return f"Key not found: {key}"
    del data[key]
    _save(data)
    return f"Deleted: {key}"

"""SSH tool — reach any machine on the home network."""
import subprocess
import os

import json

def _load_hosts() -> dict:
    """Load hosts from HOSTS_CONFIG env var (JSON) or fall back to empty."""
    raw = os.getenv("HOSTS_CONFIG", "")
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    return {}

HOSTS = _load_hosts()

SSH_OPTS = [
    '-o', 'StrictHostKeyChecking=no',
    '-o', 'ConnectTimeout=10',
    '-o', 'BatchMode=yes',
    '-i', '/home/sh1pwr3ck/.ssh/id_rsa',
]


def ssh_command(host: str, command: str, timeout: int = 30) -> str:
    if host not in HOSTS:
        return f"Unknown host '{host}'. Available: {', '.join(HOSTS.keys())}"
    user, ip = HOSTS[host]
    try:
        result = subprocess.run(
            ['ssh'] + SSH_OPTS + [f'{user}@{ip}', command],
            capture_output=True, text=True, timeout=timeout
        )
        out = (result.stdout + result.stderr).strip()
        if len(out) > 3000:
            out = out[:3000] + '\n[...truncated]'
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return f"SSH timed out after {timeout}s"
    except Exception as e:
        return f"SSH error: {e}"

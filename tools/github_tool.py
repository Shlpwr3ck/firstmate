"""GitHub tool — manage repos and profile via gh CLI."""
import subprocess
import os


def github(command: str) -> str:
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        return "GITHUB_TOKEN not set in environment."
    env = {**os.environ, "GH_TOKEN": token, "GIT_SSH_COMMAND": "ssh -i /home/sh1pwr3ck/.ssh/id_rsa"}
    try:
        result = subprocess.run(
            ["gh"] + command.split(),
            capture_output=True, text=True, timeout=30, env=env
        )
        out = (result.stdout + result.stderr).strip()
        if len(out) > 3000:
            out = out[:3000] + "\n[...truncated]"
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return "gh command timed out"
    except Exception as e:
        return f"GitHub error: {e}"

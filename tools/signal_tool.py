"""Signal attachment sending tool."""
import os
import base64
import mimetypes
import requests

SIGNAL_API_URL = os.getenv("SIGNAL_API_URL", "http://localhost:8080")
SIGNAL_NUMBER  = os.getenv("SIGNAL_NUMBER")
ALLOWED_NUMBER = os.getenv("ALLOWED_NUMBER")


def send_signal_file(path: str, caption: str = "") -> str:
    """Send a file from the local filesystem as a Signal attachment to the authorized user."""
    if not os.path.exists(path):
        return f"File not found: {path}"

    size = os.path.getsize(path)
    if size > 100 * 1024 * 1024:
        return f"File too large ({size // (1024 * 1024)}MB) — Signal limit is 100MB."

    mime_type, _ = mimetypes.guess_type(path)
    mime_type = mime_type or "application/octet-stream"

    with open(path, "rb") as f:
        b64_data = base64.standard_b64encode(f.read()).decode("utf-8")

    data_uri = f"data:{mime_type};base64,{b64_data}"

    try:
        resp = requests.post(
            f"{SIGNAL_API_URL}/v2/send",
            json={
                "message": caption,
                "number": SIGNAL_NUMBER,
                "recipients": [ALLOWED_NUMBER],
                "base64_attachments": [data_uri]
            },
            timeout=30
        )
        if resp.status_code in (200, 201):
            return f"Sent {os.path.basename(path)} ({size:,} bytes)"
        return f"Signal send failed {resp.status_code}: {resp.text}"
    except Exception as e:
        return f"Error sending attachment: {e}"

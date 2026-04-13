"""Frigate NVR snapshot tool — fetches camera images and sends via Signal."""
import os
import base64
import requests

FRIGATE_HOST   = os.getenv("FRIGATE_HOST", "http://10.34.43.31:5000")
SIGNAL_API_URL = os.getenv("SIGNAL_API_URL", "http://localhost:8080")
SIGNAL_NUMBER  = os.getenv("SIGNAL_NUMBER")
ALLOWED_NUMBER = os.getenv("ALLOWED_NUMBER")

# Friendly name → Frigate camera ID
CAMERA_ALIASES = {
    "front":      "front",
    "front door": "front",
    "door":       "front",
    "doorbell":   "front",
    "garage":     "garage",
    "office":     "office",
    "kitchen":    "kitchen",
    "safe":       "safe",
    "backdoor":   "backdoor",
    "back door":  "backdoor",
    "back":       "backdoor",
}


def frigate_snapshot(camera: str) -> str:
    """Fetch the latest snapshot from a Frigate camera and send it via Signal."""
    cam_name = CAMERA_ALIASES.get(camera.lower().strip(), camera.lower().strip())
    url = f"{FRIGATE_HOST}/api/{cam_name}/latest.jpg"

    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 404:
            return (
                f"Camera '{cam_name}' not found in Frigate. "
                f"Available: front, garage, office, kitchen, safe, backdoor"
            )
        if resp.status_code != 200:
            return f"Frigate returned {resp.status_code} for camera '{cam_name}'."

        img_b64  = base64.standard_b64encode(resp.content).decode("utf-8")
        data_uri = f"data:image/jpeg;base64,{img_b64}"

        send_resp = requests.post(
            f"{SIGNAL_API_URL}/v2/send",
            json={
                "message": f"{cam_name} — now",
                "number": SIGNAL_NUMBER,
                "recipients": [ALLOWED_NUMBER],
                "base64_attachments": [data_uri],
            },
            timeout=15,
        )
        if send_resp.status_code in (200, 201):
            return f"Snapshot sent — {cam_name} ({len(resp.content):,} bytes)"
        return f"Snapshot fetched but Signal send failed {send_resp.status_code}: {send_resp.text}"

    except requests.exceptions.ConnectionError:
        return f"Cannot reach Frigate at {FRIGATE_HOST}. Check that Frigate NVR is up."
    except Exception as e:
        return f"Frigate snapshot error: {e}"

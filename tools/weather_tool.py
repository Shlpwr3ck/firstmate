"""Weather tool — current conditions via wttr.in (no API key required)."""
import os
import requests

DEFAULT_LOCATION = os.getenv("WEATHER_LOCATION", "Dunnellon, FL")


def get_weather(location: str = "") -> str:
    """Fetch current weather. Defaults to Dunnellon FL."""
    loc = (location.strip() or DEFAULT_LOCATION).replace(" ", "+")
    try:
        resp = requests.get(f"https://wttr.in/{loc}?format=4", timeout=10)
        if resp.status_code == 200:
            return resp.text.strip()
        # Fallback to shorter format
        resp2 = requests.get(f"https://wttr.in/{loc}?format=3", timeout=10)
        return resp2.text.strip() if resp2.status_code == 200 else f"Weather unavailable ({resp.status_code})"
    except Exception as e:
        return f"Weather error: {e}"

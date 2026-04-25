"""Pi-hole stats tool — queries Pi-hole API on UbuntuServer."""
import os
import json
import requests
import hashlib

PIHOLE_HOST = os.getenv("PIHOLE_HOST", "10.34.43.11")
PIHOLE_PASS = os.getenv("PIHOLE_PASS", "")


def _get_auth_token() -> str:
    """Pi-hole v5 uses double SHA-256 of the password as the API token."""
    h1 = hashlib.sha256(PIHOLE_PASS.encode()).hexdigest()
    return hashlib.sha256(h1.encode()).hexdigest()


def get_pihole_stats() -> str:
    """Fetch Pi-hole summary stats: queries today, blocked, block%, top blocked domains."""
    token = _get_auth_token()
    base = f"http://{PIHOLE_HOST}/admin/api.php"
    try:
        resp = requests.get(f"{base}?summaryRaw&auth={token}", timeout=10)
        if resp.status_code != 200:
            return f"Pi-hole API error {resp.status_code}"
        data = resp.json()

        queries   = data.get("dns_queries_today", "?")
        blocked   = data.get("ads_blocked_today", "?")
        pct       = data.get("ads_percentage_today", 0)
        domains   = data.get("domains_being_blocked", "?")
        clients   = data.get("unique_clients", "?")
        status    = data.get("status", "?")

        lines = [
            f"Pi-hole — {status.upper()}",
            f"Queries today:  {queries:,}" if isinstance(queries, int) else f"Queries today:  {queries}",
            f"Blocked today:  {blocked:,} ({pct:.1f}%)" if isinstance(blocked, int) else f"Blocked today:  {blocked}",
            f"Block list:     {domains:,} domains" if isinstance(domains, int) else f"Block list:     {domains} domains",
            f"Clients seen:   {clients}",
        ]

        # Top blocked domains (optional)
        try:
            resp2 = requests.get(f"{base}?topAds&auth={token}", timeout=10)
            if resp2.status_code == 200:
                top = resp2.json().get("top_ads", {})
                if top:
                    lines.append("\nTop blocked:")
                    for domain, count in list(top.items())[:5]:
                        lines.append(f"  {count:>5}x  {domain}")
        except Exception:
            pass

        return "\n".join(lines)

    except Exception as e:
        return f"Pi-hole stats error: {e}"

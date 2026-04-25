"""Invoice Ninja tool — query and create invoices via self-hosted IN API."""
import os
import requests

IN_URL   = os.getenv("INVOICENINJA_URL", "https://invoice.nobletechnologiesllc.com")
IN_TOKEN = os.getenv("INVOICENINJA_TOKEN", "")

_HEADERS = lambda: {
    "X-API-TOKEN": IN_TOKEN,
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/json",
}


def _check_token() -> str | None:
    if not IN_TOKEN:
        return "INVOICENINJA_TOKEN not set in .env — add it to enable Invoice Ninja."
    return None


def get_invoices(status: str = "unpaid") -> str:
    """List invoices. status: unpaid | paid | overdue | all"""
    err = _check_token()
    if err:
        return err
    status_map = {"unpaid": "2", "paid": "4", "overdue": "5", "all": ""}
    params = {"per_page": "20", "sort": "created_at|desc"}
    if status_map.get(status):
        params["status"] = status_map[status]
    try:
        resp = requests.get(f"{IN_URL}/api/v1/invoices", headers=_HEADERS(), params=params, timeout=15, verify=False)
        if resp.status_code != 200:
            return f"Invoice Ninja error {resp.status_code}: {resp.text[:200]}"
        data = resp.json().get("data", [])
        if not data:
            return f"No {status} invoices found."
        lines = [f"{'#':<8} {'Client':<25} {'Amount':>10} {'Due':<12} Status"]
        lines.append("-" * 65)
        for inv in data:
            num    = inv.get("number", "?")
            client = (inv.get("client", {}) or {}).get("display_name", "?")[:24]
            amount = f"${float(inv.get('amount', 0)):,.2f}"
            due    = (inv.get("due_date") or "")[:10]
            stat   = inv.get("status_id", "?")
            stat_label = {"1": "Draft", "2": "Sent", "3": "Partial", "4": "Paid", "5": "Overdue"}.get(str(stat), stat)
            lines.append(f"{num:<8} {client:<25} {amount:>10} {due:<12} {stat_label}")
        return "\n".join(lines)
    except Exception as e:
        return f"Invoice Ninja error: {e}"


def get_invoice_summary() -> str:
    """Get outstanding balance summary."""
    err = _check_token()
    if err:
        return err
    try:
        resp = requests.get(f"{IN_URL}/api/v1/invoices", headers=_HEADERS(),
                            params={"status": "2", "per_page": "100"}, timeout=15, verify=False)
        if resp.status_code != 200:
            return f"Invoice Ninja error {resp.status_code}"
        data = resp.json().get("data", [])
        total = sum(float(i.get("balance", 0)) for i in data)
        count = len(data)
        return f"Outstanding: ${total:,.2f} across {count} invoice(s)"
    except Exception as e:
        return f"Invoice Ninja error: {e}"

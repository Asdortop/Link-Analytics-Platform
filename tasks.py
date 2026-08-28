from datetime import datetime
from database import SessionLocal
import models
import requests

PRIVATE_IP_PREFIXES = ("127.", "10.", "192.168.", "172.", "::1", "localhost")

def get_country_from_ip(ip: str) -> str:
    """Resolve IP to ISO country code via ip-api.com (free, no key needed)."""
    if any(ip.startswith(prefix) for prefix in PRIVATE_IP_PREFIXES):
        return "Local"
    try:
        resp = requests.get(
            f"http://ip-api.com/json/{ip}",
            params={"fields": "countryCode"},
            timeout=3
        )
        if resp.status_code == 200:
            return resp.json().get("countryCode", "Unknown")
    except Exception:
        pass
    return "Unknown"

def save_click(data):
    db = SessionLocal()

    try:
        # Resolve IP to country in the background (keeps redirect fast)
        country = get_country_from_ip(data["ip"])

        # Save click record
        click = models.Click(
            short_code=data["short_code"],
            clicked_at=datetime.now(),
            ip=data.get("ip"),
            country=country,
            device=data["device"],
            browser=data["browser"],
        )
        db.add(click)

        # Increment denormalized click counter on URL
        url_entry = db.query(models.URL).filter(
            models.URL.short_code == data["short_code"]
        ).first()
        if url_entry:
            url_entry.clicks += 1

        db.commit()

    except Exception as e:
        db.rollback()
        raise e

    finally:
        db.close()

        
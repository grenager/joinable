from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx

from joinable_core.schemas import CitySparkConfig, RawScrapedEvent

if TYPE_CHECKING:
    from joinable_core.models import Source

_API_URL = "https://portal.cityspark.com/api/events/GetEventsByDay/{portal_slug}"
_PORTAL_SCRIPT_RE = re.compile(
    r"portal\.cityspark\.com/PortalScripts/([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)
_USER_AGENT = "JoinableBot/0.1 (+https://joinable.dev)"


def detect_cityspark(html: str) -> CitySparkConfig | None:
    """Return CitySparkConfig if the page embeds a CitySpark portal script."""
    match = _PORTAL_SCRIPT_RE.search(html)
    if match is None:
        return None
    # Latitude/longitude must be supplied manually in admin; default to 0,0 until set.
    return CitySparkConfig(
        portal_slug=match.group(1),
        latitude=0.0,
        longitude=0.0,
    )


def _price_text(event: dict[str, Any]) -> str | None:
    if event.get("Free") is True:
        return "Free"
    low = event.get("Price")
    high = event.get("PriceHigh")
    if low is None and high is None:
        return None
    if low is not None and high is not None and low != high:
        return f"${low} - ${high}"
    amount = low if low is not None else high
    return f"${amount}" if amount is not None else None


def _external_url(event: dict[str, Any]) -> str | None:
    links = event.get("Links")
    if not isinstance(links, list):
        return None
    for link in links:
        if isinstance(link, dict) and isinstance(link.get("url"), str):
            return link["url"]
    return None


def _image_url(event: dict[str, Any]) -> str | None:
    for key in ("LargeImg", "MediumImg", "SmallImg"):
        value = event.get(key)
        if isinstance(value, str) and value:
            return value
    images = event.get("Images")
    if isinstance(images, list):
        for image in images:
            if isinstance(image, dict) and isinstance(image.get("url"), str):
                return image["url"]
    return None


def _city_from_city_state(city_state: str | None) -> str | None:
    if not city_state or ", " not in city_state:
        return city_state
    return city_state.rsplit(", ", 1)[0]


def _is_valid_start(start_raw: str | None) -> bool:
    if not start_raw:
        return False
    return not start_raw.startswith("0001-")


def _to_raw_event(event: dict[str, Any], day_date: str | None = None) -> RawScrapedEvent | None:
    title = event.get("Name")
    start_raw = event.get("DateStart") or event.get("Date") or day_date
    if not title or not _is_valid_start(str(start_raw) if start_raw else None):
        if title and day_date:
            start_raw = day_date
        else:
            return None

    latitude = event.get("latitude")
    longitude = event.get("longitude")
    city_state = event.get("CityState") if isinstance(event.get("CityState"), str) else None

    return RawScrapedEvent(
        title=str(title),
        start_raw=str(start_raw),
        end_raw=str(event["DateEnd"]) if event.get("DateEnd") else None,
        venue_name=str(event["Venue"]) if event.get("Venue") else None,
        external_url=_external_url(event),
        image_url=_image_url(event),
        price_text=_price_text(event),
        description=event.get("Description") or event.get("Short"),
        latitude=float(latitude) if latitude is not None else None,
        longitude=float(longitude) if longitude is not None else None,
        address=str(event["Address"]) if event.get("Address") else None,
        city=_city_from_city_state(city_state),
        category=None,
    )


class CitySparkAdapter:
    """Fetch events from the CitySpark portal API (used by many US newspapers)."""

    source_type = "cityspark"

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        validated = CitySparkConfig.model_validate(config)
        if validated.latitude == 0.0 and validated.longitude == 0.0:
            raise ValueError("CitySpark requires latitude and longitude in config")
        return validated.model_dump()

    def scrape(self, source: Source) -> list[RawScrapedEvent]:
        cfg = CitySparkConfig.model_validate(source.config)
        url = _API_URL.format(portal_slug=cfg.portal_slug)
        today = datetime.now(tz=UTC).date()
        body: dict[str, str | int | float] = {
            "start": today.isoformat(),
            "daysToLoad": cfg.days_ahead,
            "eventsPerDay": cfg.events_per_day,
            "lat": cfg.latitude,
            "lng": cfg.longitude,
            "distance": cfg.distance_miles,
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        }
        with httpx.Client(timeout=60.0, headers=headers) as client:
            response = client.post(url, json=body)
            response.raise_for_status()
            data = response.json()

        raw_events: list[RawScrapedEvent] = []
        seen: set[str] = set()
        for day_bucket in data.get("Value", []) or []:
            if not isinstance(day_bucket, dict):
                continue
            day_date = day_bucket.get("Date")
            day_date_str = str(day_date) if day_date else None
            for event in day_bucket.get("Events", []) or []:
                if not isinstance(event, dict):
                    continue
                event_id = str(event.get("Id") or event.get("PId") or "")
                if event_id and event_id in seen:
                    continue
                if event_id:
                    seen.add(event_id)
                raw = _to_raw_event(event, day_date_str)
                if raw is not None:
                    raw_events.append(raw)
        return raw_events

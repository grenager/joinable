from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import httpx

from joinable_core.schemas import LocalistConfig, RawScrapedEvent

if TYPE_CHECKING:
    from joinable_core.models import Source

_LOCALIST_MARKER_RE = re.compile(r"localist|/api/2/events", re.IGNORECASE)
_USER_AGENT = "JoinableBot/0.1 (+https://joinable.dev)"


def _normalize_calendar_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid calendar URL: {url!r}")
    return f"{parsed.scheme}://{parsed.netloc}"


def detect_localist(html: str, page_url: str) -> LocalistConfig | None:
    """Return LocalistConfig if the page references a Localist calendar."""
    if _LOCALIST_MARKER_RE.search(html) is None:
        return None
    return LocalistConfig(calendar_url=_normalize_calendar_url(page_url))


def probe_localist_api(page_url: str) -> LocalistConfig | None:
    """Probe a URL for the Localist public events API."""
    calendar_url = _normalize_calendar_url(page_url)
    probe_url = f"{calendar_url}/api/2/events"
    headers = {"Accept": "application/json", "User-Agent": _USER_AGENT}
    try:
        with httpx.Client(timeout=15.0, headers=headers) as client:
            response = client.get(probe_url, params={"pp": 1, "days": 7})
            if response.status_code != 200:
                return None
            data = response.json()
            if isinstance(data, dict) and isinstance(data.get("events"), list):
                return LocalistConfig(calendar_url=calendar_url)
    except httpx.HTTPError:
        return None
    return None


def _start_raw(event: dict[str, Any], wrapper: dict[str, Any]) -> str | None:
    instances = wrapper.get("event_instances")
    if isinstance(instances, list) and instances:
        first = instances[0]
        if isinstance(first, dict):
            for key in ("start", "event_start", "start_time"):
                value = first.get(key)
                if isinstance(value, str) and value:
                    return value
    for key in ("first_date", "start_time", "start"):
        value = event.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _end_raw(event: dict[str, Any], wrapper: dict[str, Any]) -> str | None:
    instances = wrapper.get("event_instances")
    if isinstance(instances, list) and instances:
        first = instances[0]
        if isinstance(first, dict):
            for key in ("end", "event_end", "end_time"):
                value = first.get(key)
                if isinstance(value, str) and value:
                    return value
    for key in ("last_date", "end_time", "end"):
        value = event.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _to_raw_event(wrapper: dict[str, Any]) -> RawScrapedEvent | None:
    event = wrapper.get("event")
    if not isinstance(event, dict):
        return None

    title = event.get("title")
    start_raw = _start_raw(event, wrapper)
    if not title or not start_raw:
        return None

    geo = event.get("geo") if isinstance(event.get("geo"), dict) else {}
    latitude = geo.get("latitude")
    longitude = geo.get("longitude")

    price_text: str | None = None
    if event.get("free") is True:
        price_text = "Free"
    elif event.get("ticket_cost"):
        price_text = str(event["ticket_cost"])

    return RawScrapedEvent(
        title=str(title),
        start_raw=start_raw,
        end_raw=_end_raw(event, wrapper),
        venue_name=str(event["location_name"]) if event.get("location_name") else event.get("location"),
        external_url=str(event["url"]) if event.get("url") else None,
        image_url=str(event["photo_url"]) if event.get("photo_url") else None,
        price_text=price_text,
        description=event.get("description"),
        latitude=float(latitude) if latitude is not None else None,
        longitude=float(longitude) if longitude is not None else None,
        address=str(event["address"]) if event.get("address") else None,
        city=str(geo["city"]) if geo.get("city") else None,
        category=None,
    )


class LocalistAdapter:
    """Fetch events from a Localist calendar public API."""

    source_type = "localist"

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        return LocalistConfig.model_validate(config).model_dump()

    def scrape(self, source: Source) -> list[RawScrapedEvent]:
        cfg = LocalistConfig.model_validate(source.config)
        calendar_url = _normalize_calendar_url(cfg.calendar_url)
        api_url = f"{calendar_url}/api/2/events"
        headers = {"Accept": "application/json", "User-Agent": _USER_AGENT}

        raw_events: list[RawScrapedEvent] = []
        seen: set[int] = set()
        page = 1

        with httpx.Client(timeout=60.0, headers=headers) as client:
            while True:
                response = client.get(
                    api_url,
                    params={"days": cfg.days, "pp": cfg.pp, "page": page},
                )
                response.raise_for_status()
                data = response.json()
                events = data.get("events")
                if not isinstance(events, list) or not events:
                    break

                for wrapper in events:
                    if not isinstance(wrapper, dict):
                        continue
                    event = wrapper.get("event")
                    event_id = event.get("id") if isinstance(event, dict) else None
                    if isinstance(event_id, int):
                        if event_id in seen:
                            continue
                        seen.add(event_id)
                    raw = _to_raw_event(wrapper)
                    if raw is not None:
                        raw_events.append(raw)

                page_info = data.get("page")
                total_pages: int | None = None
                if isinstance(page_info, dict):
                    total_pages = page_info.get("total")
                if total_pages is not None and page >= int(total_pages):
                    break
                if len(events) < cfg.pp:
                    break
                page += 1

        return raw_events

from __future__ import annotations

import html as html_module
import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import httpx

from joinable_core.schemas import RawScrapedEvent, TribeConfig

if TYPE_CHECKING:
    from joinable_core.models import Source

_EVENTS_PATH = "/wp-json/tribe/events/v1/events"
_TRIBE_MARKER_RE = re.compile(
    r"/wp-json/tribe/events/v1|the-events-calendar|tribe-events",
    re.IGNORECASE,
)
_USER_AGENT = "JoinableBot/0.1 (+https://joinable.dev)"


def _normalize_base_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid base URL: {url!r}")
    return f"{parsed.scheme}://{parsed.netloc}"


def detect_tribe(html: str, page_url: str) -> TribeConfig | None:
    """Return TribeConfig if the page references The Events Calendar."""
    if _TRIBE_MARKER_RE.search(html) is None:
        return None
    return TribeConfig(base_url=_normalize_base_url(page_url))


def probe_tribe_api(page_url: str) -> TribeConfig | None:
    """Probe a site for the Tribe Events REST API."""
    base_url = _normalize_base_url(page_url)
    probe_url = f"{base_url}{_EVENTS_PATH}"
    headers = {"Accept": "application/json", "User-Agent": _USER_AGENT}
    try:
        with httpx.Client(timeout=15.0, headers=headers) as client:
            response = client.get(probe_url, params={"per_page": 1})
            if response.status_code != 200:
                return None
            data = response.json()
            if isinstance(data, dict) and isinstance(data.get("events"), list):
                return TribeConfig(base_url=base_url)
    except httpx.HTTPError:
        return None
    return None


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", " ", value)
    return html_module.unescape(re.sub(r"\s+", " ", text)).strip() or None


def _price_text(cost: str | None) -> str | None:
    if not cost:
        return None
    return _strip_html(cost)


def _category_tags(categories: list[dict[str, Any]] | None) -> list[str]:
    if not categories:
        return []
    tags: list[str] = []
    for item in categories:
        if not isinstance(item, dict):
            continue
        for key in ("name", "slug"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                tags.append(value.strip())
    return tags


def _to_raw_event(event: dict[str, Any]) -> RawScrapedEvent | None:
    title = event.get("title")
    start_raw = event.get("start_date") or event.get("utc_start_date")
    if not title or not start_raw:
        return None

    venue = event.get("venue") if isinstance(event.get("venue"), dict) else {}
    image = event.get("image") if isinstance(event.get("image"), dict) else {}

    return RawScrapedEvent(
        title=str(title),
        start_raw=str(start_raw),
        end_raw=str(event["end_date"]) if event.get("end_date") else None,
        venue_name=str(venue["venue"]) if venue.get("venue") else None,
        external_url=str(event["url"]) if event.get("url") else None,
        image_url=str(image["url"]) if image.get("url") else None,
        price_text=_price_text(event.get("cost") if isinstance(event.get("cost"), str) else None),
        description=_strip_html(event.get("description") if isinstance(event.get("description"), str) else None),
        latitude=float(venue["geo_lat"]) if venue.get("geo_lat") is not None else None,
        longitude=float(venue["geo_lng"]) if venue.get("geo_lng") is not None else None,
        address=str(venue["address"]) if venue.get("address") else None,
        city=str(venue["city"]) if venue.get("city") else None,
        source_tags=_category_tags(event.get("categories")),
    )


class TribeAdapter:
    """Fetch events from The Events Calendar WordPress REST API."""

    source_type = "tribe"

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        return TribeConfig.model_validate(config).model_dump()

    def scrape(self, source: Source) -> list[RawScrapedEvent]:
        cfg = TribeConfig.model_validate(source.config)
        base_url = _normalize_base_url(cfg.base_url)
        api_url = f"{base_url}{_EVENTS_PATH}"

        today = datetime.now(tz=UTC).date()
        end = today + timedelta(days=cfg.days_ahead)
        params: dict[str, str | int] = {
            "start_date": today.isoformat(),
            "end_date": end.isoformat(),
            "per_page": cfg.per_page,
            "page": 1,
        }
        headers = {"Accept": "application/json", "User-Agent": _USER_AGENT}

        raw_events: list[RawScrapedEvent] = []
        seen: set[int] = set()

        with httpx.Client(timeout=60.0, headers=headers) as client:
            next_url: str | None = api_url
            query_params: dict[str, str | int] | None = params

            while next_url:
                response = client.get(next_url, params=query_params)
                response.raise_for_status()
                data = response.json()
                query_params = None

                for event in data.get("events", []) or []:
                    if not isinstance(event, dict):
                        continue
                    event_id = event.get("id")
                    if isinstance(event_id, int):
                        if event_id in seen:
                            continue
                        seen.add(event_id)
                    raw = _to_raw_event(event)
                    if raw is not None:
                        raw_events.append(raw)

                next_url = data.get("next_rest_url")
                if not isinstance(next_url, str) or not next_url:
                    break

        return raw_events

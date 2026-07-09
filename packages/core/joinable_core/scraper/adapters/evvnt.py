from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import httpx

from joinable_core.schemas import EvvntConfig, RawScrapedEvent

if TYPE_CHECKING:
    from joinable_core.models import Source

_API_URL = "https://discovery.evvnt.com/api/publisher/{publisher_id}/home_page_events"
_PUBLISHER_ID_RE = re.compile(r"publisher_id\s*:\s*(\d+)")
_PLUGIN_MARKER = "evvnt_discovery_plugin"


def detect_evvnt(html: str) -> EvvntConfig | None:
    """Return an EvvntConfig if the page embeds the evvnt discovery plugin."""
    if _PLUGIN_MARKER not in html and "evvnt-calendar" not in html:
        return None
    match = _PUBLISHER_ID_RE.search(html)
    if match is None:
        return None
    return EvvntConfig(publisher_id=int(match.group(1)))


def _first_image_url(images: list[dict[str, Any]] | None) -> str | None:
    if not images:
        return None
    first = images[0]
    for key in ("original", "featured", "thumb"):
        variant = first.get(key)
        if isinstance(variant, dict) and isinstance(variant.get("url"), str):
            return variant["url"]
    return None


def _price_text(prices: dict[str, str] | None) -> str | None:
    if not prices:
        return None
    amounts: list[float] = []
    for value in prices.values():
        try:
            amounts.append(float(str(value).split()[-1]))
        except (ValueError, IndexError):
            continue
    if not amounts or all(a == 0 for a in amounts):
        return "Free" if ("Free" in prices or amounts) else None
    low, high = min(amounts), max(amounts)
    return f"${low:.2f}" if low == high else f"${low:.2f} - ${high:.2f}"


def _external_url(event: dict[str, Any]) -> str | None:
    links = event.get("links") or {}
    if isinstance(links, dict):
        for key in ("Tickets", "Website", "More Info"):
            if isinstance(links.get(key), str):
                return links[key]
    return None


def _to_raw_event(event: dict[str, Any]) -> RawScrapedEvent | None:
    title = event.get("title")
    start_raw = event.get("start_time") or event.get("start_date")
    if not title or not start_raw:
        return None

    venue = event.get("venue") if isinstance(event.get("venue"), dict) else {}
    geo = event.get("_geoloc") if isinstance(event.get("_geoloc"), dict) else {}

    latitude = geo.get("lat") if isinstance(geo, dict) else None
    longitude = geo.get("lng") if isinstance(geo, dict) else None
    if latitude is None and isinstance(venue, dict):
        latitude = venue.get("latitude")
        longitude = venue.get("longitude")

    address_parts = [venue.get("address_1"), venue.get("address_2")] if venue else []
    address = ", ".join(p for p in address_parts if p) or None

    category = event.get("category_name")
    if isinstance(category, str):
        category = category[:64]
    else:
        category = None

    return RawScrapedEvent(
        title=str(title),
        start_raw=str(start_raw),
        end_raw=event.get("end_time"),
        venue_name=venue.get("name") if venue else None,
        external_url=_external_url(event),
        image_url=_first_image_url(event.get("images")),
        price_text=_price_text(event.get("prices")),
        description=event.get("description") or event.get("summary"),
        latitude=float(latitude) if latitude is not None else None,
        longitude=float(longitude) if longitude is not None else None,
        address=address,
        city=venue.get("town") if venue else None,
        category=category,
    )


class EvvntAdapter:
    """Fetch events from the evvnt discovery API (used by many news publishers)."""

    source_type = "evvnt"

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        return EvvntConfig.model_validate(config).model_dump()

    def scrape(self, source: Source) -> list[RawScrapedEvent]:
        cfg = EvvntConfig.model_validate(source.config)
        params = {
            "hitsPerPage": str(cfg.hits_per_page),
            "multipleEventInstances": "true",
            "page": "0",
            "publisher_id": str(cfg.publisher_id),
        }
        headers = {
            "Accept": "application/json",
            "User-Agent": "JoinableBot/0.1 (+https://joinable.dev)",
        }
        url = _API_URL.format(publisher_id=cfg.publisher_id)
        with httpx.Client(timeout=30.0, headers=headers) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        events: list[RawScrapedEvent] = []
        seen: set[str] = set()
        for bucket in ("rawFeaturedEvents", "rawEvents"):
            for event in data.get(bucket, []) or []:
                object_id = str(event.get("objectID") or "")
                if object_id and object_id in seen:
                    continue
                if object_id:
                    seen.add(object_id)
                raw = _to_raw_event(event)
                if raw is not None:
                    events.append(raw)
        return events

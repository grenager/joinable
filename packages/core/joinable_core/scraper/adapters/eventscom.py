from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import httpx

from joinable_core.schemas import EventsComConfig, RawScrapedEvent

if TYPE_CHECKING:
    from joinable_core.models import Source

_INIT_URL = "https://cal-pro.evensi.com/services/calendar/init.php"
_EVENT_LIST_URL = "https://cal-pro.evensi.com/services/event/eventList.php"
_EDC_TOKEN_RE = re.compile(
    r'<edc-calendar[^>]*\btoken=["\']([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})["\']',
    re.IGNORECASE,
)
_USER_AGENT = "JoinableBot/0.1 (+https://joinable.dev)"


def detect_eventscom(html: str) -> EventsComConfig | None:
    """Return EventsComConfig if the page embeds an Events.com calendar widget."""
    if "cw.events.com" not in html and "edc-calendar" not in html:
        return None
    match = _EDC_TOKEN_RE.search(html)
    if match is None:
        return None
    return EventsComConfig(calendar_token=match.group(1))


def _date_str(value: date) -> str:
    return value.isoformat()


def _init_calendar(client: httpx.Client, token: str) -> dict[str, Any]:
    response = client.get(_INIT_URL, params={"token": token})
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise ValueError(f"Events.com init failed: {payload}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("Events.com init response missing data")
    return data


def _start_raw(event: dict[str, Any]) -> str | None:
    if isinstance(event.get("startDateTime"), str):
        return event["startDateTime"]
    start = event.get("startDate")
    if isinstance(start, dict) and isinstance(start.get("date"), str):
        return start["date"].split(".")[0]
    return None


def _end_raw(event: dict[str, Any]) -> str | None:
    if isinstance(event.get("finishDateTime"), str):
        return event["finishDateTime"]
    end = event.get("endDate")
    if isinstance(end, dict) and isinstance(end.get("date"), str):
        return end["date"].split(".")[0]
    return None


def _external_url(event: dict[str, Any]) -> str | None:
    url = event.get("url")
    if isinstance(url, str) and url:
        return url
    for key in ("eventUrl", "event_url", "link"):
        value = event.get(key)
        if isinstance(value, str) and value:
            return value
    event_id = event.get("id")
    if event_id is not None:
        return f"https://discover.events.com/e/{event_id}"
    return None


def _to_raw_event(event: dict[str, Any]) -> RawScrapedEvent | None:
    title = event.get("name")
    start_raw = _start_raw(event)
    if not title or not start_raw:
        return None

    latitude = event.get("latitude")
    longitude = event.get("longitude")

    return RawScrapedEvent(
        title=str(title),
        start_raw=start_raw,
        end_raw=_end_raw(event),
        venue_name=str(event["location"]) if event.get("location") else None,
        external_url=_external_url(event),
        image_url=str(event["pic"]) if event.get("pic") else None,
        price_text=str(event["price"]) if event.get("price") else None,
        description=event.get("description"),
        latitude=float(latitude) if latitude is not None else None,
        longitude=float(longitude) if longitude is not None else None,
        address=str(event["street"]) if event.get("street") else None,
        city=str(event["city"]) if event.get("city") else None,
        category=None,
    )


class EventsComAdapter:
    """Fetch events from Events.com / Evensi embedded calendars."""

    source_type = "eventscom"

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        return EventsComConfig.model_validate(config).model_dump()

    def scrape(self, source: Source) -> list[RawScrapedEvent]:
        cfg = EventsComConfig.model_validate(source.config)
        headers = {
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        }
        today = datetime.now(tz=UTC).date()
        end = today + timedelta(days=cfg.days_ahead)

        with httpx.Client(timeout=60.0, headers=headers) as client:
            init_data = _init_calendar(client, cfg.calendar_token)
            calendar = init_data.get("calendar")
            if not isinstance(calendar, dict):
                raise ValueError("Events.com init response missing calendar")
            jwt = init_data.get("token")
            if not isinstance(jwt, str) or not jwt:
                raise ValueError("Events.com init response missing JWT token")

            latitude = calendar.get("default_latitude")
            longitude = calendar.get("default_longitude")
            radius = calendar.get("default_radius") or cfg.radius_miles
            radius_unit = calendar.get("default_radius_unit") or "mi"

            base_params: dict[str, str | int] = {
                "start_date": _date_str(today),
                "end_date": _date_str(end),
                "latitude": str(latitude),
                "longitude": str(longitude),
                "radius": str(radius),
                "radius_unit": str(radius_unit),
            }

            raw_events: list[RawScrapedEvent] = []
            seen: set[int] = set()
            offset = 0
            total_events: int | None = None

            while True:
                params = {**base_params, "offset": offset}
                response = client.get(
                    f"{_EVENT_LIST_URL}?{urlencode(params)}",
                    headers={"Authorization": f"Bearer {jwt}"},
                )
                if response.status_code == 204:
                    break
                response.raise_for_status()
                payload = response.json()
                if not payload.get("success"):
                    break
                data = payload.get("data")
                if not isinstance(data, dict):
                    break

                total_events = int(data.get("totalEvents") or 0)
                by_day = data.get("events")
                if not isinstance(by_day, dict) or not by_day:
                    break

                for day_events in by_day.values():
                    if not isinstance(day_events, list):
                        continue
                    for event in day_events:
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

                new_offset = data.get("newOffset")
                if not isinstance(new_offset, int) or new_offset <= offset:
                    break
                if total_events and new_offset >= total_events:
                    break
                offset = new_offset

        return raw_events

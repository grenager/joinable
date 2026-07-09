from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urljoin

from dateutil import parser as date_parser
from dateutil.tz import gettz

if TYPE_CHECKING:
    pass


def parse_event_datetime(raw: str, timezone: str, date_format: str | None = None) -> datetime | None:
    raw = raw.strip()
    if not raw:
        return None

    tz = gettz(timezone)
    if tz is None:
        raise ValueError(f"Unknown timezone: {timezone}")

    if date_format:
        dt = datetime.strptime(raw, date_format)
        return dt.replace(tzinfo=tz)

    parsed = date_parser.parse(raw, fuzzy=True)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def resolve_url(base_url: str, href: str | None) -> str | None:
    if not href:
        return None
    href = href.strip()
    if href.startswith(("http://", "https://")):
        return href
    return urljoin(base_url, href)


def extract_text(element, selector: str | None) -> str | None:
    """Return the combined, whitespace-normalized text of all matched elements.

    Many real-world calendars split a single logical value (e.g. a date or a
    co-headliner list) across multiple sibling elements sharing one class, so we
    join every match rather than only the first.
    """
    if not selector or element is None:
        return None
    parts: list[str] = []
    for found in element.select(selector):
        text = " ".join(found.get_text(separator=" ", strip=True).split())
        if text:
            parts.append(text)
    if not parts:
        return None
    return " ".join(parts)


def extract_attr(element, selector: str | None, attr: str) -> str | None:
    if not selector or element is None:
        return None
    found = element.select_one(selector)
    if found is None:
        return None
    value = found.get(attr)
    if isinstance(value, str):
        return value.strip() or None
    return None

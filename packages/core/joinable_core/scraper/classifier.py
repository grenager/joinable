from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

import httpx

from joinable_core.categories import CATEGORY_IDS, DEFAULT_CATEGORY_ID
from joinable_core.settings import get_settings

if TYPE_CHECKING:
    from joinable_core.schemas import RawScrapedEvent

logger = logging.getLogger(__name__)

_OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

# Source tag / platform category strings -> ontology id
_TAG_ALIASES: dict[str, str] = {
    "music": "music",
    "live music": "music",
    "live-music": "music",
    "live-music-event": "music",
    "live music event": "music",
    "comedy": "comedy",
    "comedy-event-types-event": "comedy",
    "comedy event": "comedy",
    "theater": "theater",
    "theater-performance": "theater",
    "theater & performance": "theater",
    "theater and performance": "theater",
    "performance": "theater",
    "dance": "dance",
    "film": "film",
    "movies": "film",
    "movie": "film",
    "food": "food_drink",
    "food & drink": "food_drink",
    "food and drink": "food_drink",
    "eating-drinking": "food_drink",
    "eating drinking": "food_drink",
    "cheap-drinks-eating-drinking": "food_drink",
    "nightlife": "nightlife",
    "club-dj": "nightlife",
    "club dj": "nightlife",
    "sports": "sports",
    "sports-fitness": "sports",
    "sports & fitness": "sports",
    "arts": "arts",
    "art-museums": "arts",
    "art museums": "arts",
    "arts & culture": "arts",
    "arts and culture": "arts",
    "family": "family",
    "kids-families": "family",
    "kids & families": "family",
    "kids and families": "family",
    "festival": "festival",
    "fairs-festivals": "festival",
    "fairs & festivals": "festival",
    "fair": "festival",
    "block-party": "festival",
    "night-market": "market",
    "market": "market",
    "workshop": "workshop",
    "lectures-workshops": "workshop",
    "lectures & workshops": "workshop",
    "literature": "workshop",
    "community": "community",
    "charity-volunteering": "community",
    "charity & volunteering": "community",
    "lgbtq": "community",
    "pride-holidays": "festival",
    "other": "other",
}

# Checked in order — more specific categories first.
_KEYWORD_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("comedy", ("stand-up", "standup", " stand up", "comedy show", "comedy night", "open mic")),
    ("theater", ("broadway", "musical", "playwright", "stage play", "improv show")),
    ("dance", ("ballet", "5rhythms", " dance ", "dance party", "salsa night")),
    ("film", (" film ", "screening", "documentary", "double feature", "movie night")),
    ("family", ("kids'", "kid's", "children's", "family friendly", "story time", " puppet ")),
    ("festival", ("festival", "street fair", "block party", "parade")),
    ("market", ("night market", "farmers market", " flea market")),
    ("workshop", ("workshop", "class ", " seminar ", " lecture ", "talk ", "poem jam")),
    ("food_drink", ("wine tasting", "beer ", "brewery", "food truck", "dinner", "brunch", "tasting")),
    ("nightlife", (" dj ", "club night", "after dark", "late night party")),
    ("sports", ("marathon", "5k", "10k", "pickup game", "yoga", "fitness", "soccer", "basketball")),
    ("arts", ("gallery", "museum", "exhibit", "art walk", "sculpture")),
    ("music", (
        "concert",
        "live music",
        "orchestra",
        "symphony",
        " dj ",
        "band ",
        " singer ",
        "jazz",
        "mariachi",
    )),
    ("community", ("volunteer", "cleanup", "fundraiser", "meetup", "networking")),
)

_IGNORE_TAG_PREFIXES: frozenset[str] = frozenset(
    {
        "top-pick",
        "select-one-location",
        "in-person",
        "sponsored",
        "internal-priority",
        "region-",
        "fc_",
        "fc-",
        "source-",
        "promo-code",
        "early-bird",
        "funcheap-presents",
        "annual-event",
        "uncategorized",
        "location",
        "downtown-",
    }
)


def _normalize_tag(value: str) -> str:
    cleaned = value.strip().lower()
    cleaned = cleaned.removeprefix("category-")
    cleaned = re.sub(r"[_]+", "-", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _map_tag_to_category(tag: str) -> str | None:
    normalized = _normalize_tag(tag)
    if not normalized:
        return None
    if any(normalized.startswith(prefix) for prefix in _IGNORE_TAG_PREFIXES):
        return None
    if normalized in _TAG_ALIASES:
        return _TAG_ALIASES[normalized]
    if normalized in CATEGORY_IDS:
        return normalized
    for key, category_id in _TAG_ALIASES.items():
        if key in normalized or normalized in key:
            return category_id
    return None


def classify_by_tags(tags: list[str]) -> str | None:
    for tag in tags:
        category_id = _map_tag_to_category(tag)
        if category_id is not None:
            return category_id
    return None


def classify_by_keywords(title: str, description: str | None) -> str | None:
    haystack = f"{title} {description or ''}".lower()
    for category_id, keywords in _KEYWORD_RULES:
        if any(keyword in haystack for keyword in keywords):
            return category_id
    return None


def classify_tier12(
    *,
    title: str,
    description: str | None,
    source_tags: list[str],
    raw_category: str | None,
) -> str | None:
    if raw_category:
        mapped = _map_tag_to_category(raw_category)
        if mapped is not None:
            return mapped
    by_tags = classify_by_tags(source_tags)
    if by_tags is not None:
        return by_tags
    return classify_by_keywords(title, description)


def tags_from_html_classes(element: object) -> list[str]:
    class_attr = getattr(element, "get", lambda _k, _d=None: None)("class", None)
    if not class_attr:
        return []
    if isinstance(class_attr, str):
        classes = class_attr.split()
    else:
        classes = list(class_attr)
    tags: list[str] = []
    for cls in classes:
        if not isinstance(cls, str) or not cls:
            continue
        tags.append(cls)
        if cls.startswith("category-"):
            tags.append(cls.removeprefix("category-"))
    return tags


def _llm_classify_batch(items: list[tuple[str, str | None]]) -> list[str]:
    settings = get_settings()
    if not settings.openai_api_key:
        return [DEFAULT_CATEGORY_ID] * len(items)

    category_list = ", ".join(sorted(CATEGORY_IDS))
    lines: list[str] = []
    for index, (title, description) in enumerate(items, start=1):
        desc = (description or "").strip()
        if len(desc) > 240:
            desc = desc[:240] + "…"
        lines.append(f'{index}. title: {title}\n   description: {desc or "(none)"}')

    prompt = (
        "Classify each event into exactly one category id from this list:\n"
        f"{category_list}\n\n"
        "Return JSON only: {\"categories\": [\"id\", ...]} with one category per event, same order.\n\n"
        + "\n".join(lines)
    )

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                _OPENAI_CHAT_URL,
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.openai_model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {
                            "role": "system",
                            "content": "You classify local events into a fixed category taxonomy.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            categories = parsed.get("categories", [])
            if not isinstance(categories, list) or len(categories) != len(items):
                raise ValueError("Unexpected LLM category response shape")
            return [
                cat if isinstance(cat, str) and cat in CATEGORY_IDS else DEFAULT_CATEGORY_ID
                for cat in categories
            ]
    except Exception:
        logger.exception("LLM category classification failed")
        return [DEFAULT_CATEGORY_ID] * len(items)


def assign_categories(events: list[RawScrapedEvent]) -> None:
    """Assign ontology category ids to scraped events (tiers 1–3)."""
    pending_indices: list[int] = []
    pending_items: list[tuple[str, str | None]] = []

    for index, event in enumerate(events):
        category_id = classify_tier12(
            title=event.title,
            description=event.description,
            source_tags=event.source_tags,
            raw_category=event.category,
        )
        if category_id is not None:
            event.category = category_id
            continue
        pending_indices.append(index)
        pending_items.append((event.title, event.description))

    settings = get_settings()
    batch_size = settings.category_llm_batch_size
    for start in range(0, len(pending_items), batch_size):
        batch_items = pending_items[start : start + batch_size]
        batch_indices = pending_indices[start : start + batch_size]
        batch_categories = _llm_classify_batch(batch_items)
        for idx, category_id in zip(batch_indices, batch_categories, strict=True):
            events[idx].category = category_id

    for event in events:
        if not event.category or event.category not in CATEGORY_IDS:
            event.category = DEFAULT_CATEGORY_ID

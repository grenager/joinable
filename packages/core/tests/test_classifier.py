from __future__ import annotations

from joinable_core.schemas import RawScrapedEvent
from joinable_core.scraper.classifier import (
    assign_categories,
    classify_by_keywords,
    classify_by_tags,
    classify_tier12,
)


def test_classify_funcheap_comedy_tag() -> None:
    assert classify_by_tags(["category-comedy-event-types-event"]) == "comedy"


def test_classify_funcheap_live_music_tag() -> None:
    assert classify_by_tags(["category-live-music-event"]) == "music"


def test_classify_evvnt_live_music_label() -> None:
    assert classify_by_tags(["Live Music"]) == "music"


def test_classify_keywords_from_title() -> None:
    assert classify_by_keywords("Standup Comedy Night", None) == "comedy"
    assert classify_by_keywords("Symphony in the Park", None) == "music"


def test_classify_tier12_prefers_tags_over_keywords() -> None:
    category = classify_tier12(
        title="Random words symphony",
        description=None,
        source_tags=["category-comedy-event-types-event"],
        raw_category=None,
    )
    assert category == "comedy"


def test_assign_categories_without_llm() -> None:
    events = [
        RawScrapedEvent(
            title="Symphony concert",
            start_raw="2026-07-09 19:30",
            source_tags=["category-live-music-event"],
        ),
        RawScrapedEvent(
            title="Obscure happening",
            start_raw="2026-07-09 20:00",
        ),
    ]
    assign_categories(events)
    assert events[0].category == "music"
    assert events[1].category == "other"

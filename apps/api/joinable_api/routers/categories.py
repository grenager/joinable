from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/categories", tags=["categories"])

CATEGORIES: list[dict[str, str]] = [
    {"id": "music", "label": "Live Music"},
    {"id": "comedy", "label": "Comedy"},
    {"id": "theater", "label": "Theater"},
    {"id": "food", "label": "Food & Drink"},
    {"id": "sports", "label": "Sports"},
    {"id": "arts", "label": "Arts & Culture"},
    {"id": "community", "label": "Community"},
    {"id": "other", "label": "Other"},
]


@router.get("")
async def list_categories() -> list[dict[str, str]]:
    return CATEGORIES

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CategoryDefinition:
    id: str
    label: str


ONTOLOGY: tuple[CategoryDefinition, ...] = (
    CategoryDefinition("music", "Live Music"),
    CategoryDefinition("comedy", "Comedy"),
    CategoryDefinition("theater", "Theater & Performance"),
    CategoryDefinition("dance", "Dance"),
    CategoryDefinition("film", "Film & Media"),
    CategoryDefinition("food_drink", "Food & Drink"),
    CategoryDefinition("nightlife", "Nightlife & Clubs"),
    CategoryDefinition("sports", "Sports & Fitness"),
    CategoryDefinition("arts", "Arts & Museums"),
    CategoryDefinition("family", "Kids & Family"),
    CategoryDefinition("festival", "Festivals & Fairs"),
    CategoryDefinition("market", "Markets & Shopping"),
    CategoryDefinition("workshop", "Classes & Workshops"),
    CategoryDefinition("community", "Community"),
    CategoryDefinition("other", "Other"),
)

CATEGORY_IDS: frozenset[str] = frozenset(cat.id for cat in ONTOLOGY)

DEFAULT_CATEGORY_ID: str = "other"


def list_categories() -> list[dict[str, str]]:
    return [{"id": cat.id, "label": cat.label} for cat in ONTOLOGY]


def is_valid_category_id(value: str) -> bool:
    return value in CATEGORY_IDS

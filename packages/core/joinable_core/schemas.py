from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class SourceSelectors(BaseModel):
    """CSS selectors for scraping a calendar page."""

    container: str = Field(description="CSS selector for each event container element")
    title: str
    start: str
    end: str | None = None
    venue: str | None = None
    url: str | None = None
    image: str | None = None
    price: str | None = None
    description: str | None = None
    date_format: str | None = Field(
        default=None,
        description="Optional strptime format for date parsing",
    )
    url_attribute: str = Field(default="href", description="Attribute to read for url selector")


class SourceCreate(BaseModel):
    name: str
    url: HttpUrl | str
    region: str = "SF Bay Area"
    timezone: str = "America/Los_Angeles"
    enabled: bool = True
    scrape_frequency_minutes: int = 360
    selectors: SourceSelectors
    default_category: str = "music"


class SourceUpdate(BaseModel):
    name: str | None = None
    url: HttpUrl | str | None = None
    region: str | None = None
    timezone: str | None = None
    enabled: bool | None = None
    scrape_frequency_minutes: int | None = None
    selectors: SourceSelectors | None = None
    default_category: str | None = None


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    url: str
    region: str
    timezone: str
    enabled: bool
    scrape_frequency_minutes: int
    selectors: dict[str, Any]
    default_category: str
    last_scraped_at: datetime | None
    created_at: datetime
    updated_at: datetime


class VenueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    address: str | None
    city: str | None
    region: str | None
    lat: float | None = None
    lng: float | None = None


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    start_time: datetime
    end_time: datetime | None
    category: str
    external_url: str | None
    image_url: str | None
    price_text: str | None
    venue: VenueResponse | None = None
    distance_km: float | None = None


class EventListResponse(BaseModel):
    items: list[EventResponse]
    total: int
    limit: int
    offset: int


class BookmarkCreate(BaseModel):
    event_id: UUID


class BookmarkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    created_at: datetime
    event: EventResponse | None = None


class ScrapeTestResponse(BaseModel):
    events_found: int
    sample: list[dict[str, str | None]]


class ScrapeJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    events_found: int
    error: str | None


class RawScrapedEvent(BaseModel):
    title: str
    start_raw: str
    end_raw: str | None = None
    venue_name: str | None = None
    external_url: str | None = None
    image_url: str | None = None
    price_text: str | None = None
    description: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"

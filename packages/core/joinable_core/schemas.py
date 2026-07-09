from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

SourceType = Literal["html_css", "evvnt"]


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


class EvvntConfig(BaseModel):
    """Config for sources served by the evvnt discovery API."""

    publisher_id: int
    hits_per_page: int = Field(default=50, ge=1, le=100)


class SourceCreate(BaseModel):
    name: str
    url: HttpUrl | str
    source_type: SourceType = "html_css"
    region: str = "SF Bay Area"
    timezone: str = "America/Los_Angeles"
    enabled: bool = True
    scrape_frequency_minutes: int = 1440
    config: dict[str, Any] = Field(default_factory=dict)
    default_category: str = "music"
    render_js: bool = False


class SourceUpdate(BaseModel):
    name: str | None = None
    url: HttpUrl | str | None = None
    source_type: SourceType | None = None
    region: str | None = None
    timezone: str | None = None
    enabled: bool | None = None
    scrape_frequency_minutes: int | None = None
    config: dict[str, Any] | None = None
    default_category: str | None = None
    render_js: bool | None = None


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    url: str
    source_type: str
    region: str
    timezone: str
    enabled: bool
    scrape_frequency_minutes: int
    config: dict[str, Any]
    default_category: str
    render_js: bool
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


class ScrapeTestRequest(BaseModel):
    """Dry-run scrape of an arbitrary URL + config (without saving a source)."""

    url: HttpUrl | str
    source_type: SourceType = "html_css"
    config: dict[str, Any] = Field(default_factory=dict)
    render_js: bool = False


class SourceDetectRequest(BaseModel):
    url: HttpUrl | str


class SourceDetectResponse(BaseModel):
    source_type: SourceType
    config: dict[str, Any]
    render_js: bool = False
    detail: str


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
    # Optional structured fields adapters may provide (e.g. JSON APIs like evvnt),
    # letting the pipeline skip geocoding when coordinates are already known.
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    city: str | None = None
    category: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"

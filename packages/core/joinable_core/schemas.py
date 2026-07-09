from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

SourceType = Literal["html_css", "evvnt", "cityspark", "eventscom", "tribe", "localist"]


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
    start_attribute: str | None = Field(
        default=None,
        description="If set, read start from this attribute instead of text content",
    )
    end_attribute: str | None = Field(
        default=None,
        description="If set, read end from this attribute instead of text content",
    )


class FieldSpec(BaseModel):
    """Extract a single value from the container or surrounding document context."""

    selector: str
    scope: Literal["container", "preceding", "ancestor"] = "container"
    attribute: str | None = None
    match: str | None = Field(
        default=None,
        description="When set, ignore matches whose text does not contain this substring",
    )


class CombineFieldSpec(BaseModel):
    """Join multiple field parts into one string (e.g. day header + row time)."""

    template: str = Field(description='Format template, e.g. "{day} {time}"')
    parts: dict[str, FieldSpec]

    @model_validator(mode="before")
    @classmethod
    def accept_combine_alias(cls, data: Any) -> Any:
        if isinstance(data, dict) and "combine" in data and "template" not in data:
            return {**data, "template": data["combine"]}
        return data


FieldValue = str | FieldSpec | CombineFieldSpec


def coerce_field_value(value: Any) -> FieldValue:
    if isinstance(value, str):
        return value
    if isinstance(value, FieldSpec):
        return value
    if isinstance(value, CombineFieldSpec):
        return value
    if isinstance(value, dict):
        if "parts" in value:
            return CombineFieldSpec.model_validate(value)
        if "selector" in value:
            return FieldSpec.model_validate(value)
    raise ValueError(f"Invalid field spec: {value!r}")


class SourceProfile(BaseModel):
    """One container/selector pass over a calendar page."""

    container: str = Field(description="CSS selector for each event container element")
    title: str | FieldSpec | CombineFieldSpec
    start: str | FieldSpec | CombineFieldSpec
    end: str | FieldSpec | CombineFieldSpec | None = None
    venue: str | FieldSpec | CombineFieldSpec | None = None
    url: str | FieldSpec | CombineFieldSpec | None = None
    image: str | FieldSpec | CombineFieldSpec | None = None
    price: str | FieldSpec | CombineFieldSpec | None = None
    description: str | FieldSpec | CombineFieldSpec | None = None
    date_format: str | None = Field(
        default=None,
        description="Optional strptime format for date parsing",
    )
    url_attribute: str = Field(default="href", description="Attribute to read for url selector")
    start_attribute: str | None = Field(
        default=None,
        description="When start is a selector string, read this attribute instead of text",
    )
    end_attribute: str | None = Field(
        default=None,
        description="When end is a selector string, read this attribute instead of text",
    )

    @model_validator(mode="before")
    @classmethod
    def coerce_field_specs(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        field_keys = (
            "title",
            "start",
            "end",
            "venue",
            "url",
            "image",
            "price",
            "description",
        )
        coerced = dict(data)
        for key in field_keys:
            if key in coerced and coerced[key] is not None:
                coerced[key] = coerce_field_value(coerced[key])
        return coerced


class PaginationConfig(BaseModel):
    """Follow next-page links when scraping list pages."""

    next: str = Field(description="CSS selector for the next page link")
    max_pages: int = Field(default=10, ge=1, le=100)
    url_attribute: str = Field(default="href")


class HtmlCssConfig(BaseModel):
    """Full html_css source config: one or more profiles plus optional pagination."""

    profiles: list[SourceProfile] = Field(min_length=1)
    pagination: PaginationConfig | None = None

    @classmethod
    def from_raw(cls, config: dict[str, Any]) -> HtmlCssConfig:
        if "profiles" in config:
            return cls.model_validate(config)
        if "container" not in config:
            raise ValueError("html_css config requires 'container' or 'profiles'")
        pagination_raw = config.get("pagination")
        profile_data = {k: v for k, v in config.items() if k != "pagination"}
        pagination = (
            PaginationConfig.model_validate(pagination_raw) if pagination_raw is not None else None
        )
        return cls(profiles=[SourceProfile.model_validate(profile_data)], pagination=pagination)


class EvvntConfig(BaseModel):
    """Config for sources served by the evvnt discovery API."""

    publisher_id: int
    hits_per_page: int = Field(default=50, ge=1, le=100)


class CitySparkConfig(BaseModel):
    """Config for CitySpark portal calendars (used by many US newspapers)."""

    portal_slug: str = Field(min_length=1, max_length=128)
    latitude: float = Field(description="Portal center latitude for geo-filtered fetches")
    longitude: float = Field(description="Portal center longitude for geo-filtered fetches")
    distance_miles: int = Field(default=25, ge=1, le=500)
    days_ahead: int = Field(default=30, ge=1, le=90)
    events_per_day: int = Field(default=50, ge=1, le=100)


class EventsComConfig(BaseModel):
    """Config for Events.com / Evensi embedded calendars."""

    calendar_token: str = Field(min_length=36, max_length=36)
    days_ahead: int = Field(default=30, ge=1, le=370)
    radius_miles: int = Field(default=25, ge=1, le=500)


class TribeConfig(BaseModel):
    """Config for The Events Calendar WordPress REST API."""

    base_url: HttpUrl | str
    days_ahead: int = Field(default=90, ge=1, le=365)
    per_page: int = Field(default=100, ge=1, le=100)


class LocalistConfig(BaseModel):
    """Config for Localist public calendar APIs."""

    calendar_url: HttpUrl | str
    days: int = Field(default=90, ge=1, le=370)
    pp: int = Field(default=100, ge=1, le=100)


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
    last_scrape_events_found: int | None = None
    last_scrape_events_new: int | None = None
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
    events_new: int = 0
    error: str | None = None


class RawScrapedEvent(BaseModel):
    title: str
    start_raw: str
    end_raw: str | None = None
    venue_name: str | None = None
    external_url: str | None = None
    image_url: str | None = None
    price_text: str | None = None
    description: str | None = None
    date_format: str | None = None
    source_tags: list[str] = Field(default_factory=list)
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

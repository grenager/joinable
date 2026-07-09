from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from geoalchemy2 import WKTElement
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from joinable_core.categories import DEFAULT_CATEGORY_ID, is_valid_category_id
from joinable_core.models import Event, ScrapeJob, ScrapeJobStatus, Source, Venue
from joinable_core.schemas import RawScrapedEvent
from joinable_core.scraper.adapters import get_adapter
from joinable_core.scraper.classifier import assign_categories
from joinable_core.scraper.dedupe import compute_dedupe_hash
from joinable_core.scraper.geocode import Geocoder
from joinable_core.scraper.normalize import parse_event_datetime

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _get_or_create_venue(
    session: Session,
    geocoder: Geocoder,
    raw: RawScrapedEvent,
    region: str,
) -> Venue | None:
    venue_name = raw.venue_name
    if not venue_name:
        return None

    existing = session.execute(
        select(Venue).where(Venue.name == venue_name, Venue.region == region)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    lat = raw.latitude
    lng = raw.longitude
    # Only geocode when the adapter did not already supply coordinates.
    if lat is None or lng is None:
        coords = geocoder.geocode(venue_name, region=region)
        if coords is not None:
            lat, lng = coords

    location = None
    if lat is not None and lng is not None:
        location = WKTElement(f"POINT({lng} {lat})", srid=4326)

    venue = Venue(
        name=venue_name,
        region=region,
        city=raw.city or region,
        address=raw.address,
        location=location,
    )
    session.add(venue)
    session.flush()
    return venue


def _upsert_event(
    session: Session,
    source: Source,
    raw: RawScrapedEvent,
    venue: Venue | None,
) -> tuple[bool, bool]:
    """Return (saved, is_new). saved is False when date parsing fails."""
    date_format = raw.date_format or source.config.get("date_format")
    start_time = parse_event_datetime(raw.start_raw, source.timezone, date_format)
    if start_time is None:
        return False, False

    end_time = None
    if raw.end_raw:
        end_time = parse_event_datetime(raw.end_raw, source.timezone, date_format)

    dedupe_hash = compute_dedupe_hash(raw.title, start_time.isoformat(), raw.venue_name)
    is_new = (
        session.execute(select(Event.id).where(Event.dedupe_hash == dedupe_hash)).scalar_one_or_none()
        is None
    )
    now = datetime.now(tz=UTC)
    category = (
        raw.category
        if raw.category is not None and is_valid_category_id(raw.category)
        else DEFAULT_CATEGORY_ID
    )

    stmt = insert(Event).values(
        source_id=source.id,
        venue_id=venue.id if venue else None,
        dedupe_hash=dedupe_hash,
        title=raw.title,
        description=raw.description,
        start_time=start_time,
        end_time=end_time,
        category=category,
        external_url=raw.external_url,
        image_url=raw.image_url,
        price_text=raw.price_text[:128] if raw.price_text else None,
        created_at=now,
        updated_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["dedupe_hash"],
        set_={
            "title": stmt.excluded.title,
            "description": stmt.excluded.description,
            "start_time": stmt.excluded.start_time,
            "end_time": stmt.excluded.end_time,
            "category": stmt.excluded.category,
            "external_url": stmt.excluded.external_url,
            "image_url": stmt.excluded.image_url,
            "price_text": stmt.excluded.price_text,
            "venue_id": stmt.excluded.venue_id,
            "updated_at": now,
        },
    )
    session.execute(stmt)
    return True, is_new


def run_scrape_for_source(session: Session, source_id: UUID) -> ScrapeJob:
    source = session.get(Source, source_id)
    if source is None:
        raise ValueError(f"Source not found: {source_id}")

    job = ScrapeJob(
        source_id=source.id,
        status=ScrapeJobStatus.RUNNING,
        started_at=datetime.now(tz=UTC),
    )
    session.add(job)
    session.flush()

    adapter = get_adapter(source.source_type)
    geocoder = Geocoder()
    events_found = 0
    events_new = 0

    try:
        raw_events = adapter.scrape(source)
        assign_categories(raw_events)
        for raw in raw_events:
            venue = _get_or_create_venue(session, geocoder, raw, source.region)
            saved, is_new = _upsert_event(session, source, raw, venue)
            if saved:
                events_found += 1
                if is_new:
                    events_new += 1

        source.last_scraped_at = datetime.now(tz=UTC)
        job.status = ScrapeJobStatus.SUCCESS
        job.events_found = events_found
        job.events_new = events_new
        job.finished_at = datetime.now(tz=UTC)
    except Exception as exc:
        logger.exception("Scrape failed for source %s", source_id)
        session.rollback()
        job = ScrapeJob(
            source_id=source.id,
            status=ScrapeJobStatus.FAILED,
            started_at=datetime.now(tz=UTC),
            finished_at=datetime.now(tz=UTC),
            events_found=events_found,
            events_new=events_new,
            error=str(exc),
        )
        session.add(job)

    session.commit()
    session.refresh(job)
    return job

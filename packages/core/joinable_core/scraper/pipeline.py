from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from geoalchemy2 import WKTElement
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from joinable_core.models import Event, ScrapeJob, ScrapeJobStatus, Source, Venue
from joinable_core.schemas import RawScrapedEvent, SourceSelectors
from joinable_core.scraper.dedupe import compute_dedupe_hash
from joinable_core.scraper.engine import ScrapeEngine
from joinable_core.scraper.geocode import Geocoder
from joinable_core.scraper.normalize import parse_event_datetime

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _get_or_create_venue(
    session: Session,
    geocoder: Geocoder,
    venue_name: str | None,
    region: str,
) -> Venue | None:
    if not venue_name:
        return None

    existing = session.execute(
        select(Venue).where(Venue.name == venue_name, Venue.region == region)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    coords = geocoder.geocode(venue_name, region=region)
    location = None
    city = region
    if coords is not None:
        lat, lng = coords
        location = WKTElement(f"POINT({lng} {lat})", srid=4326)

    venue = Venue(name=venue_name, region=region, city=city, location=location)
    session.add(venue)
    session.flush()
    return venue


def _upsert_event(
    session: Session,
    source: Source,
    raw: RawScrapedEvent,
    venue: Venue | None,
) -> bool:
    selectors = SourceSelectors.model_validate(source.selectors)
    start_time = parse_event_datetime(raw.start_raw, source.timezone, selectors.date_format)
    if start_time is None:
        return False

    end_time = None
    if raw.end_raw:
        end_time = parse_event_datetime(raw.end_raw, source.timezone, selectors.date_format)

    dedupe_hash = compute_dedupe_hash(raw.title, start_time.isoformat(), raw.venue_name)
    now = datetime.now(tz=UTC)

    stmt = insert(Event).values(
        source_id=source.id,
        venue_id=venue.id if venue else None,
        dedupe_hash=dedupe_hash,
        title=raw.title,
        description=raw.description,
        start_time=start_time,
        end_time=end_time,
        category=source.default_category,
        external_url=raw.external_url,
        image_url=raw.image_url,
        price_text=raw.price_text,
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
            "external_url": stmt.excluded.external_url,
            "image_url": stmt.excluded.image_url,
            "price_text": stmt.excluded.price_text,
            "venue_id": stmt.excluded.venue_id,
            "updated_at": now,
        },
    )
    session.execute(stmt)
    return True


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

    engine = ScrapeEngine()
    geocoder = Geocoder()
    selectors = SourceSelectors.model_validate(source.selectors)
    events_found = 0

    try:
        raw_events = engine.scrape(source.url, selectors)
        for raw in raw_events:
            venue = _get_or_create_venue(session, geocoder, raw.venue_name, source.region)
            if _upsert_event(session, source, raw, venue):
                events_found += 1

        source.last_scraped_at = datetime.now(tz=UTC)
        job.status = ScrapeJobStatus.SUCCESS
        job.events_found = events_found
        job.finished_at = datetime.now(tz=UTC)
    except Exception as exc:
        logger.exception("Scrape failed for source %s", source_id)
        job.status = ScrapeJobStatus.FAILED
        job.error = str(exc)
        job.finished_at = datetime.now(tz=UTC)

    session.commit()
    session.refresh(job)
    return job

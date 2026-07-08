from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from geoalchemy2 import WKTElement
from joinable_core.db import get_sync_engine
from joinable_core.models import Event, Source, Venue
from sqlalchemy import select
from sqlalchemy.orm import Session

SF_BAY_SOURCES: list[dict] = [
    {
        "name": "The Independent SF",
        "url": "https://www.theindependentsf.com/calendar/",
        "region": "SF Bay Area",
        "timezone": "America/Los_Angeles",
        "selectors": {
            "container": ".event-item, .calendar-event, article.event",
            "title": "h2, h3, .event-title, .title",
            "start": ".event-date, .date, time",
            "venue": ".venue, .location",
            "url": "a",
            "url_attribute": "href",
            "description": ".description, .summary",
            "price": ".price, .ticket-price",
        },
    },
    {
        "name": "Bottom of the Hill",
        "url": "https://www.bottomofthehill.com/calendar.html",
        "region": "SF Bay Area",
        "timezone": "America/Los_Angeles",
        "selectors": {
            "container": "tr, .show",
            "title": "td:nth-child(2), .band, .title",
            "start": "td:first-child, .date",
            "venue": None,
            "url": "a",
            "url_attribute": "href",
        },
    },
    {
        "name": "Rickshaw Stop",
        "url": "https://rickshawstop.com/calendar/",
        "region": "SF Bay Area",
        "timezone": "America/Los_Angeles",
        "selectors": {
            "container": ".event, .show, article",
            "title": "h2, h3, .event-title",
            "start": ".date, time, .event-date",
            "venue": ".venue",
            "url": "a",
            "url_attribute": "href",
        },
    },
    {
        "name": "The Chapel SF",
        "url": "https://thechapelsf.com/calendar/",
        "region": "SF Bay Area",
        "timezone": "America/Los_Angeles",
        "selectors": {
            "container": ".event, .show-item, article",
            "title": "h2, h3, .title",
            "start": ".date, time",
            "url": "a",
            "url_attribute": "href",
        },
    },
    {
        "name": "Slim's SF",
        "url": "https://slims-sf.com/calendar/",
        "region": "SF Bay Area",
        "timezone": "America/Los_Angeles",
        "selectors": {
            "container": ".event, .show, article",
            "title": "h2, h3, .event-title",
            "start": ".date, time",
            "url": "a",
            "url_attribute": "href",
        },
    },
]

# Demo events for local dev when scraping is unavailable
DEMO_VENUES: list[dict] = [
    {"name": "The Independent", "city": "San Francisco", "region": "SF Bay Area", "lat": 37.7694, "lng": -122.4481},
    {"name": "Bottom of the Hill", "city": "San Francisco", "region": "SF Bay Area", "lat": 37.7599, "lng": -122.4194},
    {"name": "Rickshaw Stop", "city": "San Francisco", "region": "SF Bay Area", "lat": 37.7761, "lng": -122.4223},
    {"name": "The Chapel", "city": "San Francisco", "region": "SF Bay Area", "lat": 37.7595, "lng": -122.4190},
    {"name": "Slim's", "city": "San Francisco", "region": "SF Bay Area", "lat": 37.7715, "lng": -122.4158},
]

DEMO_EVENTS: list[dict] = [
    {"title": "Indie Rock Night", "venue": "The Independent", "days_from_now": 0, "hour": 20, "image": "photo-1470229722913-7c0e2dbbafd3"},
    {"title": "Local Band Showcase", "venue": "Bottom of the Hill", "days_from_now": 1, "hour": 21, "image": "photo-1501386761578-eac5c94b800a"},
    {"title": "Electronic Live Set", "venue": "Rickshaw Stop", "days_from_now": 2, "hour": 21, "image": "photo-1571019614242-c5c5dee9f50b"},
    {"title": "Jazz Fusion Quartet", "venue": "The Chapel", "days_from_now": 3, "hour": 19, "image": "photo-1415201364774-f6f0bb35f28f"},
    {"title": "Punk Rock Matinee", "venue": "Slim's", "days_from_now": 4, "hour": 15, "image": "photo-1524368535928-5b5e00ddc76b"},
    {"title": "Singer-Songwriter Open Mic", "venue": "The Independent", "days_from_now": 5, "hour": 20, "image": "photo-1516280440614-37939bbacd81"},
    {"title": "Garage Rock Revival", "venue": "Bottom of the Hill", "days_from_now": 6, "hour": 21, "image": "photo-1459749411175-04bf5292ceea"},
]


def _image_url(photo_id: str) -> str:
    return f"https://images.unsplash.com/{photo_id}?w=640&h=360&fit=crop&auto=format&q=70"


def seed_sources(session: Session) -> None:
    for src_data in SF_BAY_SOURCES:
        existing = session.execute(
            select(Source).where(Source.name == src_data["name"])
        ).scalar_one_or_none()
        if existing:
            continue
        source = Source(
            id=uuid.uuid4(),
            name=src_data["name"],
            url=src_data["url"],
            region=src_data["region"],
            timezone=src_data["timezone"],
            enabled=True,
            scrape_frequency_minutes=360,
            selectors=src_data["selectors"],
            default_category="music",
        )
        session.add(source)


def seed_demo_events(session: Session) -> None:
    """Seed demo events for development/testing without live scraping."""
    from joinable_core.scraper.dedupe import compute_dedupe_hash

    venue_map: dict[str, Venue] = {}
    for v in DEMO_VENUES:
        existing = session.execute(
            select(Venue).where(Venue.name == v["name"], Venue.city == v["city"])
        ).scalar_one_or_none()
        if existing:
            venue_map[v["name"]] = existing
            continue
        venue = Venue(
            id=uuid.uuid4(),
            name=v["name"],
            city=v["city"],
            region=v["region"],
            location=WKTElement(f"POINT({v['lng']} {v['lat']})", srid=4326),
        )
        session.add(venue)
        venue_map[v["name"]] = venue

    session.flush()

    source = session.execute(select(Source).limit(1)).scalar_one_or_none()
    if source is None:
        source = Source(
            id=uuid.uuid4(),
            name="Demo Source",
            url="https://joinable.dev/demo",
            region="SF Bay Area",
            timezone="America/Los_Angeles",
            enabled=False,
            selectors={"container": "div", "title": "h1", "start": "time"},
            default_category="music",
        )
        session.add(source)
        session.flush()

    now = datetime.now(tz=UTC)
    for ev in DEMO_EVENTS:
        venue = venue_map[ev["venue"]]
        start = (now + timedelta(days=ev["days_from_now"])).replace(
            hour=ev["hour"], minute=0, second=0, microsecond=0
        )
        dedupe = compute_dedupe_hash(ev["title"], start.isoformat(), venue.name)
        image_url = _image_url(ev["image"])
        existing = session.execute(
            select(Event).where(Event.dedupe_hash == dedupe)
        ).scalar_one_or_none()
        if existing:
            existing.image_url = image_url
            continue
        event = Event(
            id=uuid.uuid4(),
            source_id=source.id,
            venue_id=venue.id,
            dedupe_hash=dedupe,
            title=ev["title"],
            description=f"Live music at {venue.name}",
            start_time=start,
            category="music",
            price_text="$15-25",
            image_url=image_url,
        )
        session.add(event)


def main() -> None:
    engine = get_sync_engine()
    with Session(engine) as session:
        seed_sources(session)
        seed_demo_events(session)
        session.commit()
    print("Seed complete: sources and demo events loaded.")


if __name__ == "__main__":
    main()

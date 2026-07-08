from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from geoalchemy2.functions import ST_Distance, ST_DWithin, ST_MakePoint, ST_SetSRID
from joinable_core.db import get_db_session
from joinable_core.models import Event, Venue
from joinable_core.schemas import EventListResponse, EventResponse, VenueResponse
from joinable_core.settings import get_settings
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from joinable_api.auth import AuthUser, get_optional_user
from joinable_api.rate_limit import limiter

router = APIRouter(prefix="/events", tags=["events"])


def _rate_limit() -> str:
    return get_settings().rate_limit_anonymous


def _parse_start_param(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().lower()
    now = datetime.now(tz=UTC)
    if normalized in {"today", "tonight"}:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if normalized == "tomorrow":
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
    if normalized == "this_week":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _venue_to_response(venue: Venue | None, distance_km: float | None = None) -> VenueResponse | None:
    if venue is None:
        return None
    lat: float | None = None
    lng: float | None = None
    if venue.location is not None:
        # WKBElement - extract via ST_X/ST_Y in query when needed; fallback None here
        pass
    return VenueResponse(
        id=venue.id,
        name=venue.name,
        address=venue.address,
        city=venue.city,
        region=venue.region,
        lat=lat,
        lng=lng,
    )


def _event_to_response(event: Event, distance_km: float | None = None) -> EventResponse:
    venue_resp = _venue_to_response(event.venue, distance_km)
    return EventResponse(
        id=event.id,
        title=event.title,
        description=event.description,
        start_time=event.start_time,
        end_time=event.end_time,
        category=event.category,
        external_url=event.external_url,
        image_url=event.image_url,
        price_text=event.price_text,
        venue=venue_resp,
        distance_km=distance_km,
    )


@router.get("", response_model=EventListResponse)
@limiter.limit(_rate_limit)
async def list_events(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[AuthUser | None, Depends(get_optional_user)] = None,
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
    radius_km: Annotated[float, Query(gt=0, le=500)] = 40.0,
    start: Annotated[str | None, Query(description="ISO date or today/tonight/this_week")] = None,
    end: Annotated[str | None, Query(description="ISO date")] = None,
    category: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    sort: SortOption = "start_time",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EventListResponse:
    start_dt = _parse_start_param(start) or datetime.now(tz=UTC)
    end_dt: datetime | None = None
    if end:
        end_dt = _parse_start_param(end)
    elif start and start.strip().lower() == "this_week":
        end_dt = start_dt + timedelta(days=7)
    elif start and start.strip().lower() in {"today", "tonight"}:
        end_dt = start_dt + timedelta(days=1)

    distance_expr = None
    user_point = None
    if lat is not None and lng is not None:
        user_point = ST_SetSRID(ST_MakePoint(lng, lat), 4326)
        distance_expr = ST_Distance(Venue.location, user_point).label("distance_m")

    base = (
        select(Event, distance_expr if distance_expr is not None else text("NULL AS distance_m"))
        .outerjoin(Venue, Event.venue_id == Venue.id)
        .where(Event.start_time >= start_dt)
        .options(selectinload(Event.venue))
    )

    if end_dt is not None:
        base = base.where(Event.start_time < end_dt)
    if category:
        base = base.where(Event.category == category)
    if q:
        ts_query = func.plainto_tsquery("english", q)
        base = base.where(
            or_(
                Event.search_vector.op("@@")(ts_query),
                Event.title.ilike(f"%{q}%"),
            )
        )
    if user_point is not None:
        base = base.where(
            Venue.location.isnot(None),
            ST_DWithin(Venue.location, user_point, radius_km * 1000),
        )

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    if sort == "distance" and user_point is not None:
        base = base.order_by(text("distance_m ASC NULLS LAST"))
    else:
        base = base.order_by(Event.start_time.asc())

    base = base.limit(limit).offset(offset)
    rows = (await session.execute(base)).all()

    items: list[EventResponse] = []
    for row in rows:
        event = row[0]
        distance_m = row[1]
        distance_km_val = float(distance_m) / 1000.0 if distance_m is not None else None
        items.append(_event_to_response(event, distance_km_val))

    return EventListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EventResponse:
    result = await session.execute(
        select(Event).where(Event.id == event_id).options(selectinload(Event.venue))
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return _event_to_response(event)

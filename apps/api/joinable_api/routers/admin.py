from __future__ import annotations

from typing import Annotated
from uuid import UUID

from celery import Celery
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from joinable_core.db import get_db_session
from joinable_core.models import Source
from joinable_core.schemas import (
    RawScrapedEvent,
    ScrapeTestRequest,
    ScrapeTestResponse,
    SourceCreate,
    SourceDetectRequest,
    SourceDetectResponse,
    SourceResponse,
    SourceUpdate,
)
from joinable_core.scraper.adapters import get_adapter
from joinable_core.scraper.adapters.cityspark import detect_cityspark
from joinable_core.scraper.adapters.eventscom import detect_eventscom
from joinable_core.scraper.adapters.evvnt import detect_evvnt
from joinable_core.scraper.adapters.localist import detect_localist, probe_localist_api
from joinable_core.scraper.adapters.tribe import detect_tribe, probe_tribe_api
from joinable_core.scraper.engine import ScrapeEngine
from joinable_core.settings import get_settings
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from joinable_api.auth import AuthUser, get_admin_user

router = APIRouter(prefix="/admin/sources", tags=["admin"])


class QueuedScrapeResponse(BaseModel):
    source_id: UUID
    status: str = "queued"
    message: str = "Scrape job enqueued"


def _get_celery() -> Celery:
    settings = get_settings()
    return Celery("joinable", broker=settings.redis_url, backend=settings.redis_url)


def _validate_config(source_type: str, config: dict) -> dict:
    try:
        return get_adapter(source_type).validate_config(config)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid config for source_type '{source_type}': {exc}",
        ) from exc


def _scrape_source_like(source: Source) -> list[RawScrapedEvent]:
    return get_adapter(source.source_type).scrape(source)


def _build_test_response(events: list[RawScrapedEvent]) -> ScrapeTestResponse:
    sample: list[dict[str, str | None]] = [
        {
            "title": e.title,
            "start": e.start_raw,
            "venue": e.venue_name,
            "url": e.external_url,
            "image": e.image_url,
        }
        for e in events[:50]
    ]
    return ScrapeTestResponse(events_found=len(events), sample=sample)


@router.get("", response_model=list[SourceResponse])
async def list_sources(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[AuthUser, Depends(get_admin_user)],
) -> list[SourceResponse]:
    result = await session.execute(select(Source).order_by(Source.name))
    return [SourceResponse.model_validate(s) for s in result.scalars().all()]


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    body: SourceCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[AuthUser, Depends(get_admin_user)],
) -> SourceResponse:
    config = _validate_config(body.source_type, body.config)
    source = Source(
        name=body.name,
        url=str(body.url),
        source_type=body.source_type,
        region=body.region,
        timezone=body.timezone,
        enabled=body.enabled,
        scrape_frequency_minutes=body.scrape_frequency_minutes,
        config=config,
        default_category=body.default_category,
        render_js=body.render_js,
    )
    session.add(source)
    await session.flush()
    await session.refresh(source)
    return SourceResponse.model_validate(source)


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[AuthUser, Depends(get_admin_user)],
) -> SourceResponse:
    source = await session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return SourceResponse.model_validate(source)


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: UUID,
    body: SourceUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[AuthUser, Depends(get_admin_user)],
) -> SourceResponse:
    source = await session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    update_data = body.model_dump(exclude_unset=True)
    if update_data.get("url") is not None:
        update_data["url"] = str(update_data["url"])
    if update_data.get("config") is not None:
        source_type = update_data.get("source_type", source.source_type)
        update_data["config"] = _validate_config(source_type, update_data["config"])

    for key, value in update_data.items():
        setattr(source, key, value)

    await session.flush()
    await session.refresh(source)
    return SourceResponse.model_validate(source)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[AuthUser, Depends(get_admin_user)],
) -> None:
    source = await session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    await session.delete(source)


@router.post("/detect", response_model=SourceDetectResponse)
async def detect_source(
    body: SourceDetectRequest,
    _: Annotated[AuthUser, Depends(get_admin_user)],
) -> SourceDetectResponse:
    """Fetch a URL and guess its platform (e.g. evvnt) + config."""
    try:
        html = await run_in_threadpool(ScrapeEngine().fetch_html, str(body.url))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not fetch URL: {exc}",
        ) from exc

    page_url = str(body.url)

    evvnt = detect_evvnt(html)
    if evvnt is not None:
        return SourceDetectResponse(
            source_type="evvnt",
            config=evvnt.model_dump(),
            detail=f"Detected evvnt discovery API (publisher_id={evvnt.publisher_id}).",
        )

    cityspark = detect_cityspark(html)
    if cityspark is not None:
        return SourceDetectResponse(
            source_type="cityspark",
            config=cityspark.model_dump(),
            detail=f"Detected CitySpark portal (slug={cityspark.portal_slug}).",
        )

    eventscom = detect_eventscom(html)
    if eventscom is not None:
        return SourceDetectResponse(
            source_type="eventscom",
            config=eventscom.model_dump(),
            detail="Detected Events.com calendar widget.",
        )

    tribe = detect_tribe(html, page_url)
    if tribe is None:
        tribe = await run_in_threadpool(probe_tribe_api, page_url)
    if tribe is not None:
        return SourceDetectResponse(
            source_type="tribe",
            config=tribe.model_dump(),
            detail=f"Detected The Events Calendar REST API ({tribe.base_url}).",
        )

    localist = detect_localist(html, page_url)
    if localist is None:
        localist = await run_in_threadpool(probe_localist_api, page_url)
    if localist is not None:
        return SourceDetectResponse(
            source_type="localist",
            config=localist.model_dump(),
            detail=f"Detected Localist calendar API ({localist.calendar_url}).",
        )

    return SourceDetectResponse(
        source_type="html_css",
        config={},
        render_js=True,
        detail="No known platform detected. Using generic HTML+CSS; add selectors manually.",
    )


@router.post("/test", response_model=ScrapeTestResponse)
async def test_config(
    body: ScrapeTestRequest,
    _: Annotated[AuthUser, Depends(get_admin_user)],
) -> ScrapeTestResponse:
    """Dry-run a URL + config without saving, to validate an adapter setup."""
    config = _validate_config(body.source_type, body.config)
    transient = Source(
        url=str(body.url),
        source_type=body.source_type,
        config=config,
        render_js=body.render_js,
    )
    try:
        events = await run_in_threadpool(_scrape_source_like, transient)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Scrape test failed: {exc}",
        ) from exc
    return _build_test_response(events)


@router.post("/{source_id}/test", response_model=ScrapeTestResponse)
async def test_source(
    source_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[AuthUser, Depends(get_admin_user)],
) -> ScrapeTestResponse:
    source = await session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    transient = Source(
        url=source.url,
        source_type=source.source_type,
        config=source.config,
        render_js=source.render_js,
    )
    try:
        events = await run_in_threadpool(_scrape_source_like, transient)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Scrape test failed: {exc}",
        ) from exc
    return _build_test_response(events)


@router.post("/{source_id}/scrape", response_model=QueuedScrapeResponse)
async def trigger_scrape(
    source_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[AuthUser, Depends(get_admin_user)],
) -> QueuedScrapeResponse:
    source = await session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    celery_app = _get_celery()
    celery_app.send_task("joinable_worker.tasks.scrape_source", args=[str(source_id)])

    return QueuedScrapeResponse(source_id=source_id)

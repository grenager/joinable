from __future__ import annotations

from typing import Annotated
from uuid import UUID

from celery import Celery
from fastapi import APIRouter, Depends, HTTPException, status
from joinable_core.db import get_db_session
from joinable_core.models import Source
from joinable_core.schemas import (
    ScrapeTestResponse,
    SourceCreate,
    SourceResponse,
    SourceSelectors,
    SourceUpdate,
)
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
    source = Source(
        name=body.name,
        url=str(body.url),
        region=body.region,
        timezone=body.timezone,
        enabled=body.enabled,
        scrape_frequency_minutes=body.scrape_frequency_minutes,
        selectors=body.selectors.model_dump(),
        default_category=body.default_category,
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
    if "selectors" in update_data and update_data["selectors"] is not None:
        update_data["selectors"] = body.selectors.model_dump() if body.selectors else {}
    if "url" in update_data and update_data["url"] is not None:
        update_data["url"] = str(update_data["url"])

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


@router.post("/{source_id}/test", response_model=ScrapeTestResponse)
async def test_source(
    source_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[AuthUser, Depends(get_admin_user)],
) -> ScrapeTestResponse:
    source = await session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    engine = ScrapeEngine()
    selectors = SourceSelectors.model_validate(source.selectors)
    try:
        events = engine.scrape(source.url, selectors)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Scrape test failed: {exc}",
        ) from exc

    sample = [
        {
            "title": e.title,
            "start": e.start_raw,
            "venue": e.venue_name,
            "url": e.external_url,
        }
        for e in events[:5]
    ]
    return ScrapeTestResponse(events_found=len(events), sample=sample)


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

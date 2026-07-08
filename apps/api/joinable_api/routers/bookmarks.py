from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from joinable_core.db import get_db_session
from joinable_core.models import Bookmark, Event
from joinable_core.schemas import BookmarkCreate, BookmarkResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from joinable_api.auth import AuthUser, get_required_user
from joinable_api.routers.events import _event_to_response

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


@router.get("", response_model=list[BookmarkResponse])
async def list_bookmarks(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[AuthUser, Depends(get_required_user)],
) -> list[BookmarkResponse]:
    result = await session.execute(
        select(Bookmark)
        .where(Bookmark.user_id == user.id)
        .options(selectinload(Bookmark.event).selectinload(Event.venue))
        .order_by(Bookmark.created_at.desc())
    )
    bookmarks = result.scalars().all()
    return [
        BookmarkResponse(
            id=b.id,
            event_id=b.event_id,
            created_at=b.created_at,
            event=_event_to_response(b.event) if b.event else None,
        )
        for b in bookmarks
    ]


@router.post("", response_model=BookmarkResponse, status_code=status.HTTP_201_CREATED)
async def create_bookmark(
    body: BookmarkCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[AuthUser, Depends(get_required_user)],
) -> BookmarkResponse:
    event = await session.get(Event, body.event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    existing = await session.execute(
        select(Bookmark).where(
            Bookmark.user_id == user.id,
            Bookmark.event_id == body.event_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already bookmarked")

    bookmark = Bookmark(user_id=user.id, event_id=body.event_id)
    session.add(bookmark)
    await session.flush()
    await session.refresh(bookmark, attribute_names=["event"])

    return BookmarkResponse(
        id=bookmark.id,
        event_id=bookmark.event_id,
        created_at=bookmark.created_at,
        event=_event_to_response(event),
    )


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bookmark(
    event_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[AuthUser, Depends(get_required_user)],
) -> None:
    result = await session.execute(
        select(Bookmark).where(Bookmark.user_id == user.id, Bookmark.event_id == event_id)
    )
    bookmark = result.scalar_one_or_none()
    if bookmark is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found")
    await session.delete(bookmark)

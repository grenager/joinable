from __future__ import annotations

from joinable_core.categories import list_categories

from fastapi import APIRouter

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("")
async def get_categories() -> list[dict[str, str]]:
    return list_categories()

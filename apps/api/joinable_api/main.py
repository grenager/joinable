from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from joinable_core.schemas import HealthResponse
from joinable_core.settings import get_settings
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from joinable_api.rate_limit import limiter
from joinable_api.routers import admin, bookmarks, categories, events


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Joinable API",
        description="Global live events aggregation and search",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    app.include_router(events.router, prefix="/v1")
    app.include_router(categories.router, prefix="/v1")
    app.include_router(bookmarks.router, prefix="/v1")
    app.include_router(admin.router, prefix="/v1")

    return app


app = create_app()

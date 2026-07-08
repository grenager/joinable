from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import httpx
import redis

from joinable_core.settings import get_settings

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_GEOCODE_CACHE_PREFIX = "geocode:"
_GEOCODE_CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days


class Geocoder:
    def __init__(self, redis_url: str | None = None) -> None:
        settings = get_settings()
        self._user_agent = settings.geocoder_user_agent
        self._redis: redis.Redis | None = None
        if redis_url or settings.redis_url:
            try:
                self._redis = redis.from_url(redis_url or settings.redis_url, decode_responses=True)
            except Exception as exc:
                logger.warning("Redis unavailable for geocoding cache: %s", exc)

    def _cache_key(self, query: str) -> str:
        return f"{_GEOCODE_CACHE_PREFIX}{query.strip().lower()}"

    def _cache_get(self, cache_key: str) -> tuple[float, float] | None:
        if self._redis is None:
            return None
        try:
            cached = self._redis.get(cache_key)
        except redis.RedisError as exc:
            logger.warning("Redis get failed (cache disabled): %s", exc)
            self._redis = None
            return None
        if not cached:
            return None
        try:
            data = json.loads(cached)
            return float(data["lat"]), float(data["lng"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None

    def _cache_set(self, cache_key: str, lat: float, lng: float) -> None:
        if self._redis is None:
            return
        try:
            self._redis.setex(
                cache_key, _GEOCODE_CACHE_TTL_SECONDS, json.dumps({"lat": lat, "lng": lng})
            )
        except redis.RedisError as exc:
            logger.warning("Redis set failed (cache disabled): %s", exc)
            self._redis = None

    def geocode(self, query: str, region: str | None = None) -> tuple[float, float] | None:
        full_query = f"{query}, {region}" if region and region not in query else query
        cache_key = self._cache_key(full_query)

        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        params: dict[str, str] = {"q": full_query, "format": "json", "limit": "1"}
        headers = {"User-Agent": self._user_agent}

        try:
            with httpx.Client(timeout=10.0, headers=headers) as client:
                response = client.get("https://nominatim.openstreetmap.org/search", params=params)
                response.raise_for_status()
                results = response.json()
        except Exception as exc:
            logger.warning("Geocoding failed for %r: %s", full_query, exc)
            return None

        if not results:
            return None

        lat = float(results[0]["lat"])
        lng = float(results[0]["lon"])

        self._cache_set(cache_key, lat, lng)

        return lat, lng

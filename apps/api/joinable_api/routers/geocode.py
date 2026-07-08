from __future__ import annotations

from typing import Annotated

import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel

from joinable_core.settings import get_settings

router = APIRouter(prefix="/geocode", tags=["geocode"])

_PLACES_AUTOCOMPLETE_URL = "https://places.googleapis.com/v1/places:autocomplete"
_PLACES_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


class GeocodeResult(BaseModel):
    lat: float
    lng: float
    display_name: str


class PlaceSuggestion(BaseModel):
    place_id: str
    description: str


class SuggestResponse(BaseModel):
    provider: str
    suggestions: list[PlaceSuggestion]


@router.get("", response_model=GeocodeResult | None)
async def geocode(
    q: Annotated[str, Query(min_length=1, max_length=200, description="Address, city, or place")],
) -> GeocodeResult | None:
    """Free-text geocode via Nominatim (no key required)."""
    settings = get_settings()
    params = {"q": q, "format": "json", "limit": "1"}
    headers = {"User-Agent": settings.geocoder_user_agent}
    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        response = await client.get(_NOMINATIM_URL, params=params)
        response.raise_for_status()
        results = response.json()
    if not results:
        return None
    top = results[0]
    return GeocodeResult(
        lat=float(top["lat"]),
        lng=float(top["lon"]),
        display_name=str(top["display_name"]),
    )


@router.get("/suggest", response_model=SuggestResponse)
async def suggest(
    q: Annotated[str, Query(min_length=1, max_length=200)],
    session_token: Annotated[str | None, Query(description="Autocomplete session token")] = None,
) -> SuggestResponse:
    """Location autocomplete. Uses Google Places (New) when a key is configured."""
    settings = get_settings()
    if not settings.google_maps_api_key:
        return SuggestResponse(provider="none", suggestions=[])

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.google_maps_api_key,
        "X-Goog-FieldMask": "suggestions.placePrediction.placeId,suggestions.placePrediction.text.text",
    }
    body: dict[str, str] = {"input": q}
    if session_token:
        body["sessionToken"] = session_token

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(_PLACES_AUTOCOMPLETE_URL, json=body, headers=headers)
        response.raise_for_status()
        data = response.json()

    suggestions: list[PlaceSuggestion] = []
    for item in data.get("suggestions", []):
        prediction = item.get("placePrediction")
        if not prediction:
            continue
        place_id = prediction.get("placeId")
        text = prediction.get("text", {}).get("text")
        if place_id and text:
            suggestions.append(PlaceSuggestion(place_id=place_id, description=text))

    return SuggestResponse(provider="google", suggestions=suggestions)


@router.get("/place", response_model=GeocodeResult | None)
async def place_details(
    place_id: Annotated[str, Query(min_length=1)],
    session_token: Annotated[str | None, Query()] = None,
) -> GeocodeResult | None:
    """Resolve a Google place_id to coordinates (completes the autocomplete session)."""
    settings = get_settings()
    if not settings.google_maps_api_key:
        return None

    headers = {
        "X-Goog-Api-Key": settings.google_maps_api_key,
        "X-Goog-FieldMask": "location,formattedAddress,displayName",
    }
    params: dict[str, str] = {}
    if session_token:
        params["sessionToken"] = session_token

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            _PLACES_DETAILS_URL.format(place_id=place_id), params=params, headers=headers
        )
        response.raise_for_status()
        data = response.json()

    location = data.get("location")
    if not location:
        return None

    display = data.get("formattedAddress") or data.get("displayName", {}).get("text", "")
    return GeocodeResult(
        lat=float(location["latitude"]),
        lng=float(location["longitude"]),
        display_name=str(display),
    )

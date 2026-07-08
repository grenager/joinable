# Joinable Agent Skill

Joinable is a global live events aggregation and search platform. Use this API to find upcoming events near any location.

## Base URL

- Production: `https://api.joinable.dev` (set via deployment)
- Local: `http://localhost:8000`

## OpenAPI

Interactive docs: `{BASE_URL}/docs`  
OpenAPI spec: `{BASE_URL}/openapi.json`

## Authentication

- **Public search** (`GET /v1/events`): No auth required. Rate-limited by IP (default 60/minute).
- **Bookmarks** (`/v1/bookmarks`): Requires Supabase JWT in `Authorization: Bearer <token>`.
- **Admin** (`/v1/admin/*`): Requires admin JWT (email in `ADMIN_EMAILS` env var).
- **Future API keys**: Pass `X-API-Key` header for higher rate limits (not yet enforced).

## Primary endpoint: Search events

```
GET /v1/events
```

### Query parameters

| Parameter   | Type   | Required | Description |
|------------|--------|----------|-------------|
| `lat`      | float  | no       | Latitude (-90 to 90) |
| `lng`      | float  | no       | Longitude (-180 to 180) |
| `radius_km`| float  | no       | Search radius in km (default 40, max 500) |
| `start`    | string | no       | `today`, `tonight`, `this_week`, or ISO datetime |
| `end`      | string | no       | ISO datetime |
| `category` | string | no       | e.g. `music`, `comedy`, `theater` |
| `q`        | string | no       | Full-text search query |
| `sort`     | string | no       | `start_time` (default) or `distance` |
| `limit`    | int    | no       | 1-100, default 20 |
| `offset`   | int    | no       | Pagination offset |

### Example: Live music in SF Bay Area tonight

```bash
curl "https://api.joinable.dev/v1/events?category=music&lat=37.77&lng=-122.42&radius_km=40&start=tonight"
```

### Example response

```json
{
  "items": [
    {
      "id": "uuid",
      "title": "Indie Rock Night",
      "description": "Live music at The Independent",
      "start_time": "2026-07-08T20:00:00-07:00",
      "end_time": null,
      "category": "music",
      "external_url": "https://example.com/tickets",
      "image_url": null,
      "price_text": "$15-25",
      "venue": {
        "id": "uuid",
        "name": "The Independent",
        "address": null,
        "city": "San Francisco",
        "region": "SF Bay Area",
        "lat": null,
        "lng": null
      },
      "distance_km": 3.2
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

## Other endpoints

- `GET /v1/events/{id}` — Event detail
- `GET /v1/categories` — List event categories
- `GET /health` — Health check

## Categories

`music`, `comedy`, `theater`, `food`, `sports`, `arts`, `community`, `other`

## Rate limits

- Anonymous: 60 requests/minute per IP
- Authenticated: 300 requests/minute (future)
- Paid API tiers: coming soon

## Notes for agents

1. Always pass `lat`/`lng`/`radius_km` for location-based results.
2. Use `category=music` and `start=tonight` or `start=this_week` for live music discovery.
3. Default fallback location for SF Bay Area: `lat=37.7749&lng=-122.4194&radius_km=40`.
4. The web app at joinable.dev uses this same API — no special agent endpoints.

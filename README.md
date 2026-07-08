# Joinable

Global live events aggregation and search platform — find live music, comedy, and more near you.

## Architecture

Monorepo with:
- **apps/web** — React + Vite frontend (Railway)
- **apps/api** — FastAPI backend (Railway)
- **apps/worker** — Celery scraper workers + beat scheduler (Railway)
- **packages/core** — Shared Python library (models, scraper, geocoder)
- **db/migrations** — Alembic migrations (PostGIS + FTS)
- **skill.md** — Agent-friendly API documentation

External services: Supabase (Postgres + Auth), Redis (queue + cache).

## Quick start (local)

### Prerequisites

- Python 3.12+, [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- PostgreSQL with PostGIS (or Supabase)
- Redis

### Setup

```bash
cp .env.example .env
# Edit .env with your Supabase and Redis URLs

uv sync
cd apps/web && npm install && cd ../..

# Run migrations
uv run alembic -c db/migrations/alembic.ini upgrade head

# Seed SF Bay Area sources + demo events
uv run python db/seed.py
```

### Run services

```bash
# Terminal 1: API
cd apps/api && uv run uvicorn joinable_api.main:app --reload --port 8000

# Terminal 2: Worker
cd apps/worker && uv run celery -A joinable_worker.celery_app:celery_app worker --beat --loglevel=info

# Terminal 3: Web
cd apps/web && npm run dev
```

Open http://localhost:5173 — defaults to SF Bay Area live music.

### Test API

```bash
curl "http://localhost:8000/v1/events?category=music&lat=37.77&lng=-122.42&radius_km=40&start=tonight"
```

## Run locally without Docker

Docker is only used for Postgres+PostGIS and Redis. Neither is required for local testing:

- **Database**: Use a hosted Supabase project (PostGIS is pre-installed) — just set `DATABASE_URL` in `.env`. No local install needed. (Alternatively `brew install postgresql postgis`.)
- **Redis**: Not required. The API rate limiter falls back to in-memory storage, and the geocoder skips caching when Redis is unavailable.
- **Worker/Celery**: Skip it. Run scrapes synchronously instead.

Minimal flow:

```bash
cp .env.example .env
# Set DATABASE_URL to your Supabase connection string (use the +asyncpg driver form)

uv sync --all-packages
uv run alembic -c db/migrations/alembic.ini upgrade head
uv run python db/seed.py                 # sources + demo events

# Start the API (no Redis needed)
cd apps/api && uv run uvicorn joinable_api.main:app --reload --port 8000

# In another terminal, start the web app
cd apps/web && npm run dev
```

Run a real scrape synchronously (no Celery/Redis):

```bash
uv run python scripts/run_scrape.py                # all enabled sources
uv run python scripts/run_scrape.py <source_id>    # one source
```

## Railway deployment

Deploy 4 services from this repo:

1. **Redis** — Railway Redis plugin
2. **api** — Root: repo root, Dockerfile: `infra/railway/api/Dockerfile`
3. **worker** — Root: repo root, Dockerfile: `infra/railway/worker/Dockerfile`
4. **web** — Root: repo root, Dockerfile: `infra/railway/web/Dockerfile`

Set env vars from `.env.example` on each service. Enable PostGIS in Supabase SQL editor:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

## Admin: adding scrape sources

Authenticated admin users can register calendar sources via API:

```bash
curl -X POST http://localhost:8000/v1/admin/sources \
  -H "Authorization: Bearer $ADMIN_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Venue Calendar",
    "url": "https://example.com/events",
    "region": "SF Bay Area",
    "selectors": {
      "container": ".event",
      "title": "h2",
      "start": ".date",
      "venue": ".venue",
      "url": "a"
    }
  }'
```

Test selectors: `POST /v1/admin/sources/{id}/test`  
Trigger scrape: `POST /v1/admin/sources/{id}/scrape`

## License

MIT

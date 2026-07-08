#!/usr/bin/env bash
set -euo pipefail

# End-to-end verification script (requires docker compose up)
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://postgres:postgres@localhost:5432/joinable}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

echo "==> Running migrations..."
uv run alembic -c db/migrations/alembic.ini upgrade head

echo "==> Seeding SF Bay Area sources and demo events..."
uv run python db/seed.py

echo "==> Testing API search endpoint..."
curl -sf "http://localhost:8000/v1/events?category=music&lat=37.77&lng=-122.42&radius_km=40&start=tonight" | head -c 500
echo ""
echo "==> Verification complete."

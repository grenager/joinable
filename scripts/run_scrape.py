"""Run a scrape synchronously without Celery/Redis (for local testing).

Usage:
    uv run python scripts/run_scrape.py                # scrape all enabled sources
    uv run python scripts/run_scrape.py <source_id>    # scrape a single source
"""

from __future__ import annotations

import sys
from uuid import UUID

from joinable_core.db import get_sync_engine
from joinable_core.models import Source
from joinable_core.scraper.pipeline import run_scrape_for_source
from sqlalchemy import select
from sqlalchemy.orm import Session


def main() -> None:
    engine = get_sync_engine()
    with Session(engine) as session:
        if len(sys.argv) > 1:
            source_ids = [UUID(sys.argv[1])]
        else:
            source_ids = [
                s.id
                for s in session.execute(
                    select(Source).where(Source.enabled.is_(True))
                ).scalars()
            ]

    if not source_ids:
        print("No enabled sources found. Run `uv run python db/seed.py` first.")
        return

    for source_id in source_ids:
        with Session(engine) as session:
            job = run_scrape_for_source(session, source_id)
            print(
                f"[{job.status.value}] source={source_id} "
                f"events_found={job.events_found} events_new={job.events_new} error={job.error or '-'}"
            )


if __name__ == "__main__":
    main()

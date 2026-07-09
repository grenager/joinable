from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from joinable_core.db import get_sync_engine
from joinable_core.models import Source
from joinable_core.scraper.pipeline import run_scrape_for_source
from sqlalchemy import select
from sqlalchemy.orm import Session

from joinable_worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="joinable_worker.tasks.scrape_source", bind=True, max_retries=2)
def scrape_source(self, source_id: str) -> dict[str, str | int]:
    engine = get_sync_engine()
    with Session(engine) as session:
        try:
            job = run_scrape_for_source(session, UUID(source_id))
            return {
                "job_id": str(job.id),
                "status": job.status.value,
                "events_found": job.events_found,
                "events_new": job.events_new,
                "error": job.error or "",
            }
        except Exception as exc:
            logger.exception("Task failed for source %s", source_id)
            raise self.retry(exc=exc, countdown=60) from exc


@celery_app.task(name="joinable_worker.tasks.enqueue_due_scrapes")
def enqueue_due_scrapes() -> dict[str, int]:
    engine = get_sync_engine()
    now = datetime.now(tz=UTC)
    enqueued = 0

    with Session(engine) as session:
        sources = session.execute(select(Source).where(Source.enabled.is_(True))).scalars().all()
        for source in sources:
            due = source.last_scraped_at is None or (
                source.last_scraped_at + timedelta(minutes=source.scrape_frequency_minutes) <= now
            )
            if due:
                scrape_source.delay(str(source.id))
                enqueued += 1

    logger.info("Enqueued %d scrape jobs", enqueued)
    return {"enqueued": enqueued}

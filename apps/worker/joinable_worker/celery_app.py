from __future__ import annotations

from celery import Celery
from celery.schedules import crontab
from joinable_core.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "joinable_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["joinable_worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "enqueue-due-scrapes": {
            "task": "joinable_worker.tasks.enqueue_due_scrapes",
            "schedule": crontab(minute="*/15"),
        },
    },
)

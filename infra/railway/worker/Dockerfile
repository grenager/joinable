FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock* ./
COPY packages/core packages/core
COPY apps/worker apps/worker

WORKDIR /app/apps/worker
RUN uv sync --no-dev

ENV PYTHONPATH=/app/apps/worker:/app/packages/core

CMD ["uv", "run", "celery", "-A", "joinable_worker.celery_app:celery_app", "worker", "--beat", "--loglevel=info"]

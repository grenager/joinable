FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock* ./
COPY packages/core packages/core
COPY apps/api apps/api

WORKDIR /app/apps/api
RUN uv sync --no-dev

COPY apps/api/joinable_api joinable_api

ENV PYTHONPATH=/app/apps/api:/app/packages/core

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "joinable_api.main:app", "--host", "0.0.0.0", "--port", "8000"]

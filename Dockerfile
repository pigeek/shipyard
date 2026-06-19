# --- Stage 1: build the React SPA bundle into app/web/spa ---
FROM node:22-slim AS spa
WORKDIR /spa
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build   # vite emits to ../app/web/spa via outDir
# outDir resolves relative to /spa, so the bundle lands at /app/web/spa
# (kept out of the build context as an image artifact below).

# --- Stage 2: Python runtime ---
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY app ./app
RUN uv pip install --system .

# Built SPA bundle from the node stage (served at /app by FastAPI).
COPY --from=spa /app/web/spa ./app/web/spa

# Project files needed at runtime.
COPY alembic.ini ./
COPY alembic ./alembic
COPY docker ./docker
RUN chmod +x docker/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

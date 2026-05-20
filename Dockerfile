# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.13
FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=src \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libcups2-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN mkdir -p /app/invoices/downloaded /app/invoices/confirmed
RUN uv sync --no-dev

ARG APP_MODULE=src.discord_bot.app
ENV APP_MODULE=${APP_MODULE}

CMD ["sh", "-c", "uv run python -m ${APP_MODULE}"]

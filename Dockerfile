# Linen Draper - Arch Linux Manual Intervention Tracker
#
# Local Docker development build.
# No Anubis, no Caddy, no SMTP (email writes to .emails/ locally).
#
# Build:
#   docker compose build
# Run:
#   docker compose up

FROM python:3.14-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl ca-certificates unzip \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:${PATH}"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

RUN uv sync --frozen --no-dev \
    && chmod +x /app/docker-entrypoint.sh

EXPOSE 3000

ENV APP_ENV=local
ENV DATABASE_URL=sqlite:///data/reflex.db
ENV API_URL=http://localhost:3000

ENTRYPOINT ["/app/docker-entrypoint.sh"]

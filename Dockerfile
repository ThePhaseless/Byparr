FROM debian:stable-slim AS base

ARG GITHUB_BUILD=false \
    VERSION

ENV GITHUB_BUILD=${GITHUB_BUILD}\
    VERSION=${VERSION}\
    DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/var/cache/uv

WORKDIR /app

RUN apt update && apt -y upgrade && apt install -y curl

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
RUN uvx playwright install-deps firefox && uvx camoufox fetch

FROM base AS devcontainer
RUN apt install -y git
ENTRYPOINT [ "sleep", "infinity" ]


FROM base AS app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/var/cache/uv uv sync

COPY . .
RUN chown -R appuser:appuser /app

FROM app AS test
RUN --mount=type=cache,target=/var/cache/uv uv sync --group test
RUN uv run pytest --retries 3

FROM app
USER appuser
EXPOSE 8191
HEALTHCHECK --interval=15m --timeout=30s --start-period=5s --retries=3 CMD [ "curl", "http://localhost:8191/health" ]
ENTRYPOINT ["uv", "run", "main.py"]

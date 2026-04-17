# Ubuntu is required by playwright
FROM ubuntu:latest AS base

ARG GITHUB_BUILD=false \
    VERSION

ENV GITHUB_BUILD=${GITHUB_BUILD}\
    VERSION=${VERSION}\
    DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    PORT=8191 \
    XDG_CACHE_HOME=/cache \
    HOME=/tmp

RUN apt-get update &&\
    apt-get install -y --no-install-recommends curl ca-certificates tini &&\
    apt-get clean &&\
    rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

FROM base AS devcontainer
RUN apt-get update &&\
    apt-get install -y --no-install-recommends git &&\
    uvx playwright install-deps firefox &&\
    uvx camoufox fetch &&\
    apt-get clean &&\
    rm -rf /var/lib/apt/lists/*
ENTRYPOINT [ "sleep", "infinity" ]

FROM base AS app
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN mkdir -p /cache &&\
    uv sync &&\
    uv run camoufox fetch &&\
    apt-get update &&\
    uv run playwright install-deps firefox &&\
    uv cache clean &&\
    apt-get clean &&\
    rm -rf /var/lib/apt/lists/*

COPY . .

# Make app and cache world-readable; addon scripts dir world-writable (runtime writes)
RUN chmod -R o+rX /app /cache &&\
    find /app/.venv -path "*/camoufox_add_init_script/addon" -type d -exec chmod -R o+rwX {} +

FROM app AS test
RUN \
    uv sync --group test &&\
    uv run pytest --retries 3

FROM app
USER 1000
EXPOSE $PORT
HEALTHCHECK --interval=15m --timeout=30s --start-period=5s --retries=3 CMD curl "http://localhost:${PORT}/health"
ENTRYPOINT ["tini", "--", "/app/.venv/bin/python", "main.py"]

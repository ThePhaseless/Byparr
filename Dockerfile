# Ubuntu is required by playwright. Pinned to 24.04 because Playwright 1.58
# does NOT yet ship dependency lists for ubuntu:26.04 (resolute/latest), and
# `playwright install-deps firefox` is a no-op there — Camoufox then fails
# at runtime with "libgtk-3.so.0: cannot open shared object file".
FROM ubuntu:24.04 AS base

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
    apt-get install -y --no-install-recommends curl ca-certificates &&\
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
# Install the system libs Camoufox/Firefox need at runtime. We try Playwright's
# helper first (the canonical list), then unconditionally install a known-good
# baseline — if Playwright's helper no-ops on a new Ubuntu (it currently
# warns "Cannot install dependencies for ubuntu26.04-x64"), Camoufox would
# otherwise fail at first launch with libgtk-3.so.0 not found.
RUN mkdir -p /cache &&\
    uv sync &&\
    uv run camoufox fetch &&\
    apt-get update &&\
    (uv run playwright install-deps firefox || true) &&\
    apt-get install -y --no-install-recommends \
        libgtk-3-0t64 libnss3 libxss1 libasound2t64 libdbus-glib-1-2 \
        libpci3 libxtst6 libxrandr2 libxcomposite1 libxdamage1 \
        libxfixes3 libgbm1 libpango-1.0-0 libpangocairo-1.0-0 \
        libatk1.0-0t64 libatk-bridge2.0-0t64 libcairo2 libxkbcommon0 \
        fonts-liberation fonts-noto-color-emoji \
    && uv cache clean &&\
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
ENTRYPOINT ["/app/.venv/bin/python", "main.py"]

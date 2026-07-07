# Ubuntu is required by playwright.
# Pin to 24.04 LTS: ubuntu:latest floats to 26.04, which Playwright 1.58
# cannot install firefox deps for (no libgtk-3 -> camoufox fails to launch).
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
    HOME=/tmp \
    # Optional: set to require bearer token on /load requests.
    # Must match EXTERNAL_WEB_LOADER_API_KEY in Open WebUI.
    OWUI_API_KEY=""

RUN apt-get update &&\
    apt-get install -y --no-install-recommends curl ca-certificates git tini &&\
    apt-get clean &&\
    rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

FROM base AS devcontainer
RUN apt-get update &&\
    apt-get install -y --no-install-recommends git &&\
    uvx playwright install-deps firefox &&\
    uvx --from git+https://github.com/feder-cr/invisible_playwright.git python -m invisible_playwright fetch &&\
    apt-get clean &&\
    rm -rf /var/lib/apt/lists/*
ENTRYPOINT [ "sleep", "infinity" ]

FROM base AS app
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN mkdir -p /cache &&\
    uv sync &&\
    uv run python -m invisible_playwright fetch &&\
    apt-get update &&\
    uv run playwright install-deps firefox &&\
    uv cache clean &&\
    apt-get clean &&\
    rm -rf /var/lib/apt/lists/*

COPY . .

# Make app and cache world-readable; cache must be writable for runtime browser/profile data
RUN chmod -R o+rX /app /cache &&\
    chmod -R o+w /cache

FROM app AS test
RUN \
    uv sync --group test &&\
    uv run pytest --retries 3

FROM app
USER 1000
EXPOSE $PORT
HEALTHCHECK --interval=15m --timeout=30s --start-period=5s --retries=3 CMD curl "http://127.0.0.1:${PORT}/health"
ENTRYPOINT ["tini", "--", "/app/.venv/bin/python", "main.py"]

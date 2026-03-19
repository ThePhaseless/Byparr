# Ubuntu is required by playwright
FROM ubuntu:latest AS base

ARG GITHUB_BUILD=false \
    UV_CACHE_DIR=/var/cache/uv \
    VERSION

ENV GITHUB_BUILD=${GITHUB_BUILD}\
    VERSION=${VERSION}\
    DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=${UV_CACHE_DIR} \
    PORT=8191 \
    XDG_CACHE_HOME=/cache \
    HOME=/tmp

RUN apt update &&\
    apt -y upgrade &&\
    apt install -y curl
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

FROM base AS devcontainer
RUN apt install -y git &&\
    uvx playwright install-deps firefox &&\
    uvx camoufox fetch
ENTRYPOINT [ "sleep", "infinity" ]

FROM base AS app
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN mkdir -p /cache &&\
    uv sync &&\
    uv run camoufox fetch &&\
    uv run playwright install-deps firefox

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

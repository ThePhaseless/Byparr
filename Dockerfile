# Ubuntu is required by playwright.
# Pin to 24.04 LTS: ubuntu:latest floats to 26.04, which Playwright 1.58
# cannot install firefox deps for (no libgtk-3 -> camoufox fails to launch).
FROM ubuntu:26.04@sha256:6a06111c3b0a8600feadb270aec771dc239bf407b25625f93f44ab00e11f4d3c AS base

ARG GITHUB_BUILD=false

ENV GITHUB_BUILD=${GITHUB_BUILD}\
    PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    PORT=8191 \
    XDG_CACHE_HOME=/cache \
    HOME=/home/byparr

RUN apt-get update &&\
    apt-get install -y --no-install-recommends curl ca-certificates git tini &&\
    apt-get clean &&\
    rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest@sha256:96f40d3904aad8d0bd010539001d36c8e2188b981e1334471a90c4a1d93bb490 /uv /uvx /bin/

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

RUN mkdir -p /home/byparr &&\
    chmod -R o+rX /app &&\
    chmod -R a+rwX /cache /home/byparr

FROM app AS test
RUN \
    uv sync --group test &&\
    uv run pytest -rs --retries 5

FROM app
ARG VERSION
ENV VERSION=${VERSION}
USER 1000
EXPOSE $PORT
HEALTHCHECK --interval=15m --timeout=30s --start-period=5s --retries=3 CMD curl "http://127.0.0.1:${PORT}/health"
ENTRYPOINT ["tini", "--", "/app/.venv/bin/python", "main.py"]

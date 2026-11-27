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

FROM base AS engine-amd64

FROM base AS engine-arm64
ARG ARM64_ENGINE_URL=https://github.com/ThePhaseless/firefox_antidetect_patch/releases/download/firefox-58-arm64
ARG ARM64_SEAL_SHA256=cf5256b2c7f54fc4b496fffc77e853410c683f3bee8b0afaf92075c4d4f03f80
ARG ARM64_ARCHIVE_SHA256=49bd7233b290c5d8ac7487e36adba22272f401c13abbef084530b20b5f27e61b
ARG ARM64_ENGINE_TREE=firefox-58_159.0_20261108115355
ENV INVISIBLE_SEAL_FILE=/opt/invisible/seal.json \
    INVISIBLE_PLAYWRIGHT_ENGINE_DIR=/opt/invisible/engine
RUN mkdir -p "/opt/invisible/engine/$ARM64_ENGINE_TREE" &&\
    curl -fsSL --retry 3 --retry-all-errors -o /opt/invisible/seal.json "$ARM64_ENGINE_URL/seal.json" &&\
    curl -fsSL --retry 3 --retry-all-errors -o /tmp/engine.tar.gz "$ARM64_ENGINE_URL/firefox-159.0-stealth-linux-arm64.tar.gz" &&\
    echo "$ARM64_SEAL_SHA256  /opt/invisible/seal.json" | sha256sum -c - &&\
    echo "$ARM64_ARCHIVE_SHA256  /tmp/engine.tar.gz" | sha256sum -c - &&\
    tar xzf /tmp/engine.tar.gz --no-same-owner -C "/opt/invisible/engine/$ARM64_ENGINE_TREE" &&\
    rm /tmp/engine.tar.gz

FROM engine-${TARGETARCH} AS app
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN mkdir -p /cache &&\
    uv sync &&\
    if [ -n "${INVISIBLE_SEAL_FILE:-}" ]; then uv run python -c 'import os, sys; from invisible_core.seal import load_seal, packaged_seal_path; p, e = load_seal(packaged_seal_path()), load_seal(os.environ["INVISIBLE_SEAL_FILE"]); k = lambda s: (s.tag, s.upstream_version, s.source_commit); k(p) == k(e) or sys.exit(f"invisible-core is sealed to {p.tag} ({p.upstream_version}, {p.source_commit}) but the arm64 engine seal is {e.tag} ({e.upstream_version}, {e.source_commit}): publish a matching arm64 release in ThePhaseless/firefox_antidetect_patch and update the ARM64_* args")'; fi &&\
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
# -s: register as a subreaper when tini is not PID 1 (e.g. a pod with a shared
# process namespace), so orphaned browser processes are still reaped.
ENTRYPOINT ["tini", "-s", "--", "/app/.venv/bin/python", "main.py"]

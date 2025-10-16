# Ubuntu is required by playwright
FROM ubuntu:latest AS base

ARG GITHUB_BUILD=false \
    UV_CACHE_DIR=/var/cache/uv \
    VERSION \
    USER=ubuntu \
    UID=1000

ARG GROUP=${USER} \
    GID=${UID}

ENV GITHUB_BUILD=${GITHUB_BUILD}\
    VERSION=${VERSION}\
    DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=${UV_CACHE_DIR}

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
RUN chown ${USER}:${GROUP} /app &&\
    mkdir -p ${UV_CACHE_DIR} &&\
    chown ${USER}:${GROUP} ${UV_CACHE_DIR}

USER ${USER}
COPY pyproject.toml uv.lock ./
RUN uv sync && uv run camoufox fetch

USER root
RUN uv run playwright install-deps firefox
USER ${USER}

COPY . .

FROM app AS test
RUN \
    uv sync --group test &&\
    uv run pytest --retries 3

FROM app
EXPOSE 8191
HEALTHCHECK --interval=15m --timeout=30s --start-period=5s --retries=3 CMD [ "curl", "http://localhost:8191/health" ]
ENTRYPOINT ["uv", "run", "main.py"]

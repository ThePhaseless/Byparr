FROM debian:bookworm-slim AS base
ENV HOME=/root

ARG GITHUB_BUILD=false \
    VERSION

ENV GITHUB_BUILD=${GITHUB_BUILD}\
    VERSION=${VERSION}\
    DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="${HOME}/.local/bin:$PATH"

WORKDIR /app

RUN apt-get update && \
    apt-get install -y libgtk-3-0 libasound2 libx11-xcb1 wget xvfb

ADD https://astral.sh/uv/install.sh install.sh
RUN sh install.sh && uv --version
RUN uvx playwright install-deps firefox && uvx camoufox fetch

FROM base AS devcontainer
RUN apt install -y git && apt upgrade -y
ENV UV_LINK_MODE=copy
ENTRYPOINT [ "sleep", "infinity" ]


FROM base AS app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=${HOME}/.cache/uv uv sync

COPY . .
RUN ["uv", "run", "main.py", "--init"]

FROM app AS test
RUN --mount=type=cache,target=${HOME}/.cache/uv uv sync --group test
RUN chmod +x ./test.sh && ./test.sh

FROM app
EXPOSE 8191
HEALTHCHECK --interval=15m --timeout=30s --start-period=5s --retries=3 CMD [ "curl", "http://localhost:8191/health" ]
ENTRYPOINT ["uv", "run", "main.py"]

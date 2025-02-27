FROM debian:bullseye-slim AS base

ARG GITHUB_BUILD=false \
    VERSION

ENV HOME=/root \
    GITHUB_BUILD=${GITHUB_BUILD}\
    VERSION=${VERSION}\
    DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    DISPLAY=:0
ENV PATH="${HOME}/.local/bin:$PATH"

WORKDIR /app

RUN apt update &&\
    apt install -y --no-install-recommends --no-install-suggests xauth xvfb scrot wget chromium chromium-driver

ADD https://astral.sh/uv/install.sh install.sh
RUN sh install.sh
COPY pyproject.toml uv.lock ./
RUN uv sync

# SeleniumBase does not come with an arm64 chromedriver binary
RUN cd .venv/lib/*/site-packages/seleniumbase/drivers && ln -s /usr/bin/chromedriver uc_driver

COPY . .

FROM base AS test

RUN uv sync --group test
RUN ./test.sh

FROM base

EXPOSE 8191
HEALTHCHECK --interval=15m --timeout=30s --start-period=5s --retries=3 CMD [ "curl", "http://localhost:8191/health" ]
CMD ["./cmd.sh"]
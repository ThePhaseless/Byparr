FROM debian:bullseye-slim AS base

# Inspired by https://github.com/Hudrolax/uc-docker-alpine/


ARG \
    GITHUB_BUILD=false \
    VERSION
ENV \
    GITHUB_BUILD=${GITHUB_BUILD}\
    VERSION=${VERSION}

ENV HOME=/root
ENV \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="${HOME}/.local/bin:$PATH" \
    DISPLAY=:0

WORKDIR /app

RUN rm /var/lib/dpkg/info/libc-bin.*
RUN apt-get clean
RUN apt-get update
RUN apt-get install libc-bin

RUN apt update &&\
    apt upgrade -y &&\
    apt install -y --no-install-recommends --no-install-suggests xauth xvfb scrot curl chromium chromium-driver ca-certificates
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
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
FROM debian:bullseye-slim AS base

# Inspired by https://github.com/Hudrolax/uc-docker-alpine/

ARG GITHUB_BUILD=false
ENV GITHUB_BUILD=${GITHUB_BUILD}

ENV HOME=/root
ENV \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    DISPLAY=:0

WORKDIR /app
RUN apt update &&\
    apt install -y xvfb scrot python3-tk curl chromium chromium-driver

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="${HOME}/.local/bin:$PATH"
COPY pyproject.toml uv.lock ./
RUN uv sync --no-group

COPY . .
RUN cd .venv/lib/*/site-packages/seleniumbase/drivers && ln -s /usr/bin/chromedriver uc_driver

FROM base AS test

RUN uv sync --group test
RUN uv run pytest --retries 2 -n auto --xvfb

FROM base

EXPOSE 8191
HEALTHCHECK --interval=60s --timeout=30s --start-period=5s --retries=3 CMD [ "curl", "http://localhost:8191/health" ]
CMD ["./cmd.sh"]
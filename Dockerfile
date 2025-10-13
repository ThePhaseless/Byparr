FROM ubuntu:22.04 AS base
ENV HOME=/root

ARG GITHUB_BUILD=false \
    VERSION

ENV GITHUB_BUILD=${GITHUB_BUILD}\
    VERSION=${VERSION}\
    DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON=python3.12

WORKDIR /app

# Install Python 3.12 and runtime dependencies
RUN apt-get update && apt-get -y upgrade && apt-get install -y \
    software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    ca-certificates \
    curl \
    wget \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

FROM base AS devcontainer
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
ENTRYPOINT [ "sleep", "infinity" ]

FROM base AS builder
# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
ENV PATH="/root/.cargo/bin:${PATH}"

COPY pyproject.toml uv.lock ./

# Sync dependencies with Python 3.12
RUN --mount=type=cache,target=${HOME}/.cache/uv \
    --mount=type=cache,target=${HOME}/.cargo/registry \
    uv sync --frozen --no-dev --python python3.12

FROM base AS app
# Copy built environment from builder
COPY --from=builder /app/.venv /app/.venv
COPY pyproject.toml uv.lock ./

# Install Playwright with dependencies
RUN /app/.venv/bin/python -m playwright install --with-deps firefox

# Pre-create Camoufox directory
RUN mkdir -p /root/.camoufox && chmod -R 755 /root/.camoufox

# Try to fetch Camoufox
RUN /app/.venv/bin/python -m camoufox fetch || echo "Camoufox will be fetched on first run"

COPY . .

FROM app AS test
COPY --from=builder /app/.venv /app/.venv
RUN --mount=type=cache,target=${HOME}/.cache/uv \
    uv sync --frozen --group test --python python3.12
RUN uv run pytest --retries 3 -n auto

FROM app
EXPOSE 8191
HEALTHCHECK --interval=15m --timeout=30s --start-period=5s --retries=3 \
    CMD [ "curl", "-f", "http://localhost:8191/health" ]
ENTRYPOINT ["uv", "run", "main.py"]

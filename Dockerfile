FROM python:3.12-alpine

# Inspired by https://github.com/Hudrolax/uc-docker-alpine/

# Install build dependencies
RUN apk update && apk upgrade && \
    apk add --no-cache --virtual .build-deps \
    alpine-sdk \
    curl \
    wget \
    unzip \
    gnupg

# Install dependencies
RUN apk add --no-cache \
    xvfb \
    x11vnc \
    fluxbox \
    xterm \
    libffi-dev \
    openssl-dev \
    zlib-dev \
    bzip2-dev \
    readline-dev \
    git \
    nss \
    freetype \
    freetype-dev \
    harfbuzz \
    ca-certificates \
    ttf-freefont \
    pipx \
    chromium \
    chromium-chromedriver

WORKDIR /app
EXPOSE 8191

# python
ENV \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    # do not ask any interactive question
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    DISPLAY=:0

RUN pipx install poetry
ENV PATH="/root/.local/bin:$PATH"
COPY pyproject.toml poetry.lock ./
RUN poetry install

COPY fix_nodriver.py ./
RUN . /app/.venv/bin/activate && python fix_nodriver.py
COPY . .
RUN chmod +x entrypoint.sh
RUN ./pytest.sh
CMD ["./entrypoint.sh", "&&", ".", "/app/.venv/bin/activate", "&&", "python", "main.py"]
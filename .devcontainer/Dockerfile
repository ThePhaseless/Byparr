FROM python:3.12

# Inspired by https://github.com/Hudrolax/uc-docker-alpine/

# Install build dependencies
RUN apt update && apt upgrade -y && apt install -y\
    curl \
    wget \
    unzip \
    gnupg \
    bash \
    stow

# Install dependencies
RUN apt install -y \
    xvfb \
    x11vnc \
    fluxbox \
    xterm \
    git \
    ca-certificates \
    pipx \
    chromium

RUN pipx install poetry
# RUN poetry config virtualenvs.in-project true
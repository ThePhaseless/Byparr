FROM debian:latest

RUN apt update && apt upgrade -y && apt install -y chromium chromium-driver xvfb git

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"
FROM python:3.13-bullseye

RUN apt update && apt upgrade -y && apt install -y chromium chromium-driver xvfb

RUN curl -sSL https://install.python-poetry.org | python3 -
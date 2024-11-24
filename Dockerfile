FROM python:3.12-slim

# Inspired by https://github.com/Hudrolax/uc-docker-alpine/

ARG GITHUB_BUILD=false
ENV GITHUB_BUILD=${GITHUB_BUILD}

ENV HOME=/root
ENV \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    # do not ask any interactive question
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    DISPLAY=:0

WORKDIR /app
EXPOSE 8191
ADD https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb ./
RUN apt update &&\
    apt install -y xvfb scrot python3-tk curl ./google-chrome-stable_current_amd64.deb &&\
    rm ./google-chrome-stable_current_amd64.deb

RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="${HOME}/.local/bin:$PATH"
COPY pyproject.toml poetry.lock ./
RUN poetry install

COPY . .
CMD [". .venv/bin/activate && python3 main.py"]
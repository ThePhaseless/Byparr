FROM python:3.12-slim-bullseye

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
RUN apt update &&\
    apt install -y xvfb scrot python3-tk curl chromium chromium-driver

RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="${HOME}/.local/bin:$PATH"
COPY pyproject.toml poetry.lock ./
RUN poetry install

COPY . .
HEALTHCHECK --interval=60s --timeout=30s --start-period=5s --retries=3 CMD [ "curl", "http://localhost:8191/health" ]
RUN ln /usr/bin/chromedriver ./.venv/lib/python3.12/site-packages/seleniumbase/drivers/uc_driver
CMD ["./cmd.sh"]
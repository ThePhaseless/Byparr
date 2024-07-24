FROM python:3.11

# python
ENV PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    # it gets named `.venv`
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    # do not ask any interactive question
    POETRY_NO_INTERACTION=1\
    HEADLESS=1

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="~/.local/share/pypoetry:$PATH"
RUN poetry install

COPY . .
ENTRYPOINT ["python", "run", "main.py"]
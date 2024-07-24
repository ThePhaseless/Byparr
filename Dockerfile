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


RUN apt update && apt upgrade -y
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
RUN apt install -y ./google-chrome-stable_current_amd64.deb

RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="root/.local/bin:$PATH"
RUN /root/.local/bin/poetry install

WORKDIR /app
COPY . /app
RUN poetry install
RUN python fix_nodriver.py
ENTRYPOINT ["python", "main.py"]
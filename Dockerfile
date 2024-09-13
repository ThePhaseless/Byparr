FROM python:3.12

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
    POETRY_VIRTUALENVS_IN_PROJECT=true

RUN apt update && apt upgrade -y
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
RUN apt install -y --no-install-recommends --no-install-suggests ./google-chrome-stable_current_amd64.deb && rm ./google-chrome-stable_current_amd64.deb

RUN apt install pipx -y
RUN pipx ensurepath
RUN pipx install poetry
ENV PATH="/root/.local/bin:$PATH"
COPY pyproject.toml poetry.lock ./
RUN poetry install

ENV INSTALL_NOVNC=false
COPY novnc.sh .
RUN ./novnc.sh
ENV DISPLAY=:1.0

COPY fix_nodriver.py ./
RUN . /app/.venv/bin/activate && python fix_nodriver.py
COPY . .
RUN /usr/local/share/desktop-init.sh && poetry run pytest
CMD /usr/local/share/desktop-init.sh && . /app/.venv/bin/activate && python main.py
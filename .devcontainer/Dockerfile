FROM mcr.microsoft.com/devcontainers/python:1-3.11-bullseye AS devcontainer

USER vscode
RUN sudo apt update && sudo apt upgrade -y && sudo apt install -y --no-install-recommends xvfb
RUN pipx install poetry
RUN poetry config virtualenvs.in-project true
RUN sudo wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
RUN sudo apt install -y ./google-chrome-stable_current_amd64.deb
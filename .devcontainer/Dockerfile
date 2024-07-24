FROM mcr.microsoft.com/devcontainers/python:1-3.11-bullseye

USER vscode
RUN pipx install poetry
RUN poetry config virtualenvs.in-project true
RUN sudo apt update && sudo apt upgrade -y
RUN sudo wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
RUN sudo apt install -y ./google-chrome-stable_current_amd64.deb

if [ "$(uname -m)" == "x86_64" ]; then
    ./entrypoint.sh &&. /app/.venv/bin/activate && poetry run pytest
fi
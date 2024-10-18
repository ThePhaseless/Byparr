if [ $(arch) = "x86_64" ]; then
    ./entrypoint.sh && . ./.venv/bin/activate && poetry run pytest
fi
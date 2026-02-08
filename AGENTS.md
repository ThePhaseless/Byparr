# Copilot Instructions

## Project overview

- FastAPI service that mimics FlareSolverr-style API for bypassing anti-bot pages using Camoufox + Playwright captcha solver.
- Entry point: main app in main.py; routes and request flow defined in src/endpoints.py and src/models.py.
- Browser lifecycle is owned by get_camoufox() in src/utils.py, which yields a page, solver, and context for each request.

## Architecture and data flow

- Request flow: POST /v1 -> read_item() -> browser.goto() -> wait for load states -> detect challenge title -> solve captcha -> return LinkResponse.
- Challenge detection uses CHALLENGE_TITLES from src/consts.py; update this map when adding providers.
- Health check hits /v1 internally with <https://google.com> and fails if status is not OK.
- Logging: LogRequest middleware logs only POST /v1 timing and outcome; other paths pass through.

## Key modules and patterns

- Models use Pydantic v2 with camelCase aliasing for responses (see src/models.py).
- LinkResponse.invalid() is the standard error response shape; keep fields consistent with FlareSolverr style.
- get_camoufox() constructs AsyncCamoufox with addons and optional proxy config from env vars.

## Config and environment

- Core env vars in src/consts.py: HOST, PORT, PROXY_SERVER, PROXY_USERNAME, PROXY_PASSWORD, LOG_LEVEL, VERSION.
- VERSION strips leading "v" for tag-style values.

## Developer workflows

- Local run: uv sync && uv run main.py
- Init mode: uv run main.py --init (pre-warms health check via browser setup)
- Tests: uv sync --group test && uv run pytest --retries 3
- Docker troubleshooting: docker build --target test .

## Tests and external dependencies

- tests/main_test.py calls real websites; tests are network-dependent and may be skipped based on upstream status.
- HTTP client tests use starlette.testclient + httpx; avoid mocking unless needed for local-only changes.

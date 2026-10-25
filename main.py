from __future__ import annotations

import asyncio
import logging
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

from src.concurrency_advisor import concurrency_advisor
from src.consts import HOST, LOG_LEVEL, MAX_CONCURRENCY, PORT, VERSION
from src.endpoints import health_check, router
from src.middlewares import LogRequest
from src.owui import router as owui_router
from src.utils import get_browser, logger

logger.info("Using version %s", VERSION)
logger.info("Log level set to %s", logging.getLevelName(LOG_LEVEL))
logger.info(
    "Concurrency configured: %d simultaneous sessions. Estimated memory: ~%d MB (~%.1f GB).",
    MAX_CONCURRENCY,
    concurrency_advisor.get_memory_estimate_mb(MAX_CONCURRENCY),
    concurrency_advisor.get_memory_estimate_gb(MAX_CONCURRENCY),
)
if MAX_CONCURRENCY >= 8:
    logger.warning(concurrency_advisor.generate_memory_warning(MAX_CONCURRENCY))

app = FastAPI(debug=LOG_LEVEL == logging.DEBUG, log_level=LOG_LEVEL)
app.add_middleware(GZipMiddleware)
app.add_middleware(LogRequest)

app.include_router(router=router)
app.include_router(router=owui_router)


async def init():
    """Initialize the application."""
    async for browser in get_browser():
        await health_check(browser)


if __name__ == "__main__":
    # Check for --init flag to run the app in development mode
    if "--init" in sys.argv:
        logger.info("Running initialization script...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(init())
        logger.info("Initialization complete.")
    else:
        uvicorn.run(app, host=HOST, port=PORT)

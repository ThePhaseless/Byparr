from __future__ import annotations

import asyncio
import logging
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

from src.consts import HOST, LOG_LEVEL, PORT, VERSION
from src.endpoints import health_check, router
from src.middlewares import LogRequest
from src.utils import get_camoufox, logger

logger.info("Using version %s", VERSION)
logger.info("Log level set to %s", logging.getLevelName(LOG_LEVEL))

app = FastAPI(debug=LOG_LEVEL == logging.DEBUG, log_level=LOG_LEVEL)
app.add_middleware(GZipMiddleware)
app.add_middleware(LogRequest)

app.include_router(router=router)


async def init():
    """Initialize the application."""
    async for browser in get_camoufox():
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

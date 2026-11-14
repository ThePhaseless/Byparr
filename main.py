from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

from src.concurrency_advisor import concurrency_advisor
from src.consts import HOST, LOG_LEVEL, MAX_CONCURRENCY, PORT, VERSION
from src.endpoints import router
from src.middlewares import LogRequest
from src.owui import router as owui_router
from src.utils import logger, warm_up

LOG_LEVEL_NAME = logging.getLevelName(LOG_LEVEL).lower()

logger.info("Using version %s", VERSION)
logger.info("Log level set to %s", LOG_LEVEL_NAME)
logger.info(
    "Concurrency configured: %d simultaneous sessions. Estimated memory: ~%d MB (~%.1f GB).",
    MAX_CONCURRENCY,
    concurrency_advisor.get_memory_estimate_mb(MAX_CONCURRENCY),
    concurrency_advisor.get_memory_estimate_gb(MAX_CONCURRENCY),
)
if MAX_CONCURRENCY >= 8:
    logger.warning(concurrency_advisor.generate_memory_warning(MAX_CONCURRENCY))


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    """Fetch the GeoIP database before uvicorn opens the port."""
    await warm_up()
    yield


app = FastAPI(debug=LOG_LEVEL == logging.DEBUG, lifespan=lifespan)
app.add_middleware(GZipMiddleware)
app.add_middleware(LogRequest)

app.include_router(router=router)
app.include_router(router=owui_router)


if __name__ == "__main__":
    if "--init" in sys.argv:
        logger.info("Running initialization script...")
        asyncio.run(warm_up())
        logger.info("Initialization complete.")
    else:
        uvicorn.run(app, host=HOST, port=PORT, log_level=LOG_LEVEL_NAME)

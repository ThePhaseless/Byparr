from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

from src.consts import HOST, LOG_LEVEL, PORT, VERSION
from src.endpoints import router
from src.middlewares import LogRequest
from src.owui import router as owui_router
from src.utils import logger, warm_up

LOG_LEVEL_NAME = logging.getLevelName(LOG_LEVEL).lower()

logger.info("Using version %s", VERSION)
logger.info("Log level set to %s", LOG_LEVEL_NAME)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    """Fetch the GeoIP database before uvicorn opens the port."""
    await warm_up()
    yield


app = FastAPI(debug=LOG_LEVEL == logging.DEBUG, log_level=LOG_LEVEL, lifespan=lifespan)
app.add_middleware(GZipMiddleware)
app.add_middleware(LogRequest)

app.include_router(router=router)
app.include_router(router=owui_router)


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level=LOG_LEVEL_NAME)

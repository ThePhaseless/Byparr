from __future__ import annotations

import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

from src.consts import LOG_LEVEL, PROXY, USE_HEADLESS, USE_XVFB, VERSION
from src.endpoints import router
from src.middlewares import LogRequest
from src.utils import logger

logger.info("Starting Byparr...")
logger.info("Version %s", str(VERSION))
logger.info("Log level %s", str(LOG_LEVEL))
logger.info("Default proxy set: " + ("Yes" if PROXY else "No"))
logger.info("XVFB: " + str(USE_XVFB))
logger.info("Headless mode: " + str(USE_HEADLESS))

app = FastAPI(debug=LOG_LEVEL == logging.DEBUG, log_level=logger.level)
app.add_middleware(GZipMiddleware)
app.add_middleware(LogRequest)

app.include_router(router=router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8191, log_level=logger.level)  # noqa: S104

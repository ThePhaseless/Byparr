from __future__ import annotations

import logging
import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

from src.consts import LOG_LEVEL, VERSION
from src.endpoints import router
from src.middlewares import LogRequest
from src.utils import logger

logger.info("Using version %s", VERSION)

app = FastAPI(debug=LOG_LEVEL == logging.DEBUG, log_level=LOG_LEVEL)
app.add_middleware(GZipMiddleware)
app.add_middleware(LogRequest)

app.include_router(router=router)


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=8191, log_level=LOG_LEVEL, reload=True)  # noqa: S104

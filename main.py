from __future__ import annotations

import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

from src.consts import LOG_LEVEL, VERSION
from src.endpoints import router as api_router
from src.proxy_endpoints import router as proxy_router
import argparse
from src.middlewares import LogRequest
from src.utils import logger

logger.info("Using version %s", VERSION)

def create_app(proxy_mode: bool = False):
    application = FastAPI(debug=LOG_LEVEL == logging.DEBUG, log_level=LOG_LEVEL)
    application.add_middleware(GZipMiddleware)
    application.add_middleware(LogRequest)
    if proxy_mode:
        application.include_router(proxy_router)
        logger.info("Proxy mode enabled.")
    else:
        application.include_router(api_router)
        logger.info("API mode enabled.")
    return application

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Byparr Server")
    parser.add_argument("--proxy-mode", action="store_true", help="Run as HTTP proxy server only.")
    args = parser.parse_args()
    app = create_app(proxy_mode=args.proxy_mode)
    uvicorn.run(app, host="0.0.0.0", port=8191, log_level=LOG_LEVEL)  # noqa: S104

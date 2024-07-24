import logging
import os

logger = logging.getLogger("uvicorn.error")
logger.setLevel(os.getenv("LOG_LEVEL") or logging.INFO)
if len(logger.handlers) == 0:
    logger.addHandler(logging.StreamHandler())

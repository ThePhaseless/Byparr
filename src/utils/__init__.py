import logging

from src.utils.consts import LOG_LEVEL

logger = logging.getLogger("uvicorn.error")
logger.setLevel(LOG_LEVEL)
if len(logger.handlers) == 0:
    logger.addHandler(logging.StreamHandler())

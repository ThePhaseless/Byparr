import logging
from time import gmtime, strftime

from fastapi import Header
from sbase import SB, BaseCase

from src.consts import LOG_LEVEL, PROXY, USE_HEADLESS

logger = logging.getLogger("uvicorn.error")
logger.setLevel(LOG_LEVEL)
if len(logger.handlers) == 0:
    logger.addHandler(logging.StreamHandler())


def get_sb(
    proxy: str | None = Header(
        default=None,
        examples=["username:password@host:port"],
        description="Override default proxy from env",
    ),
):
    """Get SeleniumBase instance."""
    with SB(
        uc=True,
        headless=USE_HEADLESS,
        locale_code="en",
        ad_block=True,
        proxy=proxy or PROXY,
    ) as sb:
        yield sb


def save_screenshot(sb: BaseCase):
    """Save screenshot on HTTPException."""
    sb.save_screenshot(f"screenshots/{strftime('%Y-%m-%d %H:%M:%S', gmtime())}.png")

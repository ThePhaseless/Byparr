import logging
from time import gmtime, strftime

from fastapi import Header, HTTPException
from httpx import codes
from sbase import SB, BaseCase

from src.consts import LOG_LEVEL, PROXY, USE_HEADLESS

logger = logging.getLogger("uvicorn.error")
logger.setLevel(LOG_LEVEL)
if len(logger.handlers) == 0:
    logger.addHandler(logging.StreamHandler())


def get_sb(
    proxy: str | None = Header(
        default=PROXY,
        examples=["protocol://username:password@host:port"],
        description="Override default proxy address",
    ),
):
    """Get SeleniumBase instance."""
    if proxy and proxy.startswith("socks5://") and "@" in proxy:
        raise HTTPException(
            status_code=codes.BAD_REQUEST,
            detail="SOCKS5 proxy with authentication is not supported. Check README for more info.",
        )

    with SB(
        uc=True,
        headless=USE_HEADLESS,
        locale_code="en",
        ad_block=True,
        proxy=proxy,
    ) as sb:
        yield sb


def save_screenshot(sb: BaseCase):
    """Save screenshot on HTTPException."""
    sb.save_screenshot(f"screenshots/{strftime('%Y-%m-%d %H:%M:%S', gmtime())}.png")

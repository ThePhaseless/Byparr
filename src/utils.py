import logging
from time import gmtime, strftime

from anyio.streams import file
from fastapi import Header, HTTPException
from httpx import codes
from sbase import SB, BaseCase

from src.consts import LOG_LEVEL, PROXY, USE_HEADLESS, USE_XVFB

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

    sb = None
    try:
        with SB(
            uc=True,
            test=True,
            headless=USE_HEADLESS,
            xvfb=USE_XVFB,
            locale_code="en",
            ad_block=True,
            proxy=proxy,
        ) as sb:
            yield sb
    except Exception:
        # Log the exception but re-raise it to let FastAPI handle it properly
        logger.exception("Exception in SeleniumBase dependency")
        raise


def save_screenshot(sb: BaseCase):
    """Save screenshot on HTTPException."""
    file_name = f"screenshots_{strftime('%Y-%m-%d_%H:%M:%S', gmtime())}.png"

    logger.info(f"Saving screenshot to {file_name}")
    sb.save_screenshot(file_name)

import asyncio
import logging
import math
import time
from collections.abc import AsyncGenerator
from typing import Annotated, NamedTuple, cast

from fastapi import Header
from invisible_core import prepare_session_geo
from invisible_playwright.async_api import InvisiblePlaywright
from playwright.async_api import Browser, BrowserContext, Page
from pydantic import BaseModel, Field
from tzlocal import get_localzone_name

from src.consts import (
    BROWSER_LOCALE,
    BROWSER_TIMEZONE,
    LOG_LEVEL,
    PROXY_PASSWORD,
    PROXY_SERVER,
    PROXY_USERNAME,
)

solver_logger = logging.getLogger("playwright_captcha")
solver_logger.handlers.clear()
if LOG_LEVEL == logging.DEBUG:
    solver_logger.addHandler(logging.StreamHandler())
    solver_logger.setLevel(LOG_LEVEL)
else:
    solver_logger.handlers.append(logging.NullHandler())

logger = logging.getLogger("uvicorn.error")
logger.setLevel(LOG_LEVEL)
if len(logger.handlers) == 0:
    logger.addHandler(logging.StreamHandler())


class TimeoutTimer(BaseModel):
    duration: int  # in seconds
    start_time: float = Field(default_factory=time.perf_counter)

    def remaining(self) -> float:
        """Get remaining time in seconds."""
        return max(0, self.duration - (time.perf_counter() - self.start_time))


MIN_WAIT_MS = 1.0


def remaining_ms(timer: TimeoutTimer) -> float:
    """Milliseconds left, never 0 - Playwright reads that as no timeout at all."""
    return max(MIN_WAIT_MS, timer.remaining() * 1000)


class BrowserDepClass(NamedTuple):
    page: Page
    context: BrowserContext


GEO_RETRY_SECONDS = 600


class BrowserGeo(NamedTuple):
    timezone: str
    locale: str
    expires_at: float = math.inf


_geo_lock = asyncio.Lock()
_geo: BrowserGeo | None = None


def resolve_browser_geo() -> BrowserGeo:
    """Resolve the timezone and locale of a session without a proxy."""
    geo = prepare_session_geo(BROWSER_TIMEZONE or "", None, BROWSER_LOCALE or "auto")
    locale = BROWSER_LOCALE or (geo.locale.primary if geo.locale else "en-US")
    if geo.timezone:
        logger.info("Browser timezone %s, locale %s", geo.timezone, locale)
        return BrowserGeo(geo.timezone, locale)
    timezone = get_localzone_name() or "UTC"
    logger.warning(
        "Could not resolve the timezone from the egress IP, using %s and locale %s "
        "for %d seconds. Set BROWSER_TIMEZONE and BROWSER_LOCALE to skip the lookup.",
        timezone,
        locale,
        GEO_RETRY_SECONDS,
    )
    return BrowserGeo(timezone, locale, time.monotonic() + GEO_RETRY_SECONDS)


async def get_browser_geo() -> BrowserGeo:
    """Per-process cache of resolve_browser_geo()."""
    global _geo  # noqa: PLW0603
    async with _geo_lock:
        if _geo is None or time.monotonic() >= _geo.expires_at:
            _geo = await asyncio.to_thread(resolve_browser_geo)
        return _geo


async def get_browser(
    x_proxy_server: Annotated[
        str | None,
        Header(
            alias="X-Proxy-Server",
            description="Override proxy server for this request in protocol://host:port format.",
        ),
    ] = None,
    x_proxy_username: Annotated[
        str | None,
        Header(
            alias="X-Proxy-Username",
        ),
    ] = None,
    x_proxy_password: Annotated[
        str | None,
        Header(
            alias="X-Proxy-Password",
        ),
    ] = None,
) -> AsyncGenerator[BrowserDepClass]:
    """Get InvisiblePlaywright browser instance."""
    header_server = x_proxy_server
    header_username = x_proxy_username
    header_password = x_proxy_password

    proxy_config = None
    timezone = BROWSER_TIMEZONE or ""
    locale = BROWSER_LOCALE or "auto"

    if header_server:
        proxy_config = {
            "server": header_server,
            "username": header_username,
            "password": header_password,
        }
    elif PROXY_SERVER:
        proxy_config = {
            "server": PROXY_SERVER,
            "username": PROXY_USERNAME,
            "password": PROXY_PASSWORD,
        }
    else:
        timezone, locale, _ = await get_browser_geo()

    async with InvisiblePlaywright(
        headless=True,
        proxy=proxy_config,
        humanize=True,
        locale=locale,
        timezone=timezone,
        extra_prefs={
            "devtools.jsonview.enabled": False,
            "browser.tabs.remote.useCrossOriginOpenerPolicy": False,
            "browser.tabs.remote.useCrossOriginEmbedderPolicy": False,
            "dom.security.https_first": False,
        },
    ) as browser_raw:
        # InvisiblePlaywright yields a Browser instance
        browser = cast("Browser", browser_raw)
        context = await browser.new_context()
        page = await context.new_page()
        yield BrowserDepClass(page, context)

import asyncio
import logging
import math
import threading
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Annotated, NamedTuple, cast

from fastapi import Header
from invisible_core import GeoTimezoneError, SessionGeo, prepare_session_geo
from invisible_core import _geo as invisible_geo  # pyright: ignore[reportPrivateUsage]
from invisible_core import download as invisible_download
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
# Short at first: proxied launches with an "auto" timezone fail outright while the
# database is missing. Doubles per failure up to GEO_RETRY_SECONDS, because every
# launch waits on the lock while a retry runs.
GEOIP_RETRY_SECONDS = 30


class RememberedLookup[T]:
    """
    Remember a direct (unproxied) invisible-core lookup for the process.

    invisible-core asks for the egress IP and checks GitHub for the GeoIP
    database on every browser launch. A success is kept until restart. A
    failure is kept for ``retry_seconds``, doubled per consecutive failure up
    to GEO_RETRY_SECONDS; a proxied call always passes through, since each
    proxy has its own egress.
    """

    def __init__(
        self, lookup: Callable[..., T], retry_seconds: float = GEO_RETRY_SECONDS
    ) -> None:
        """Wrap ``lookup``, kept public so tests can patch it."""
        self.lookup = lookup
        self.retry_seconds = retry_seconds
        self._lock = threading.Lock()
        self._value: T | None = None
        self._error: Exception | None = None
        self._expires_at = 0.0
        self._failures = 0

    def __call__(self, proxy: dict[str, str] | None = None, **kwargs: object) -> T:
        """Call ``lookup`` through the proxy, or return the remembered result."""
        if proxy:
            return self.lookup(proxy, **kwargs)
        with self._lock:
            if time.monotonic() >= self._expires_at:
                try:
                    self._value, self._error = self.lookup(**kwargs), None
                    self._expires_at, self._failures = math.inf, 0
                except Exception as exc:
                    self._value, self._error = None, exc
                    self._expires_at = time.monotonic() + min(
                        self.retry_seconds * 2**self._failures, GEO_RETRY_SECONDS
                    )
                    # Capped so a week-long outage cannot overflow a float window.
                    self._failures = min(self._failures + 1, 16)
            if self._error is not None:
                raise self._error.with_traceback(None)
            return cast("T", self._value)

    def clear(self) -> None:
        """Forget the remembered result."""
        with self._lock:
            self._value, self._error, self._expires_at = None, None, 0.0
            self._failures = 0


# shortcut: private invisible-core seams (no public parameter in 55.50); tests/utils_test.py guards them, switch to an upstream option if one appears.
discover_egress_ip = RememberedLookup(invisible_geo.discover_egress_ip)
ensure_geoip_mmdb = RememberedLookup(
    invisible_download.ensure_geoip_mmdb,  # pyright: ignore[reportPrivateImportUsage]
    GEOIP_RETRY_SECONDS,
)
invisible_geo.discover_egress_ip = discover_egress_ip
invisible_download.ensure_geoip_mmdb = ensure_geoip_mmdb  # pyright: ignore[reportPrivateImportUsage]


class BrowserGeo(NamedTuple):
    timezone: str
    locale: str
    expires_at: float = math.inf


_geo_lock = asyncio.Lock()
_geo: BrowserGeo | None = None


def resolve_browser_geo() -> BrowserGeo:
    """Resolve the timezone and locale of a session without a proxy."""
    try:
        geo = prepare_session_geo(
            BROWSER_TIMEZONE or "", None, BROWSER_LOCALE or "auto"
        )
    except GeoTimezoneError as exc:
        # Since invisible-core 49.46 a failed "auto" lookup raises instead of
        # returning an empty zone; the host zone below is still the fallback.
        logger.debug("Egress geo lookup failed: %s", exc)
        geo = SessionGeo("", None)
    locale = BROWSER_LOCALE or (geo.locale.primary if geo.locale else "en-US")
    if geo.timezone:
        logger.info("Browser timezone %s, locale %s", geo.timezone, locale)
        return BrowserGeo(geo.timezone, locale)
    timezone = get_localzone_name() or "UTC"
    logger.warning(
        "Could not resolve the timezone from the egress IP, using %s and locale %s "
        "for %d seconds. Set BROWSER_TIMEZONE and BROWSER_LOCALE to not depend on it.",
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


_warm_lock = asyncio.Lock()
_warmed = False


def _warm_geoip_database() -> None:
    try:
        ensure_geoip_mmdb()
    except Exception as exc:
        logger.warning(
            "Could not get the GeoIP database: %s. Browsers start without it; "
            "the next request after %d seconds retries.",
            exc,
            ensure_geoip_mmdb.retry_seconds,
        )


async def warm_up() -> None:
    """
    Fetch the GeoIP database and, without a proxy, the egress geo once.

    Every browser launch waits for this, so a fresh container downloads the
    database once instead of once per concurrent first request. A failure is
    kept by RememberedLookup and retried after its retry_seconds.
    """
    global _warmed  # noqa: PLW0603
    async with _warm_lock:
        if _warmed:
            return
        logger.info(
            "Fetching the GeoIP database and egress IP before starting browsers"
        )
        lookups: list[Awaitable[object]] = [asyncio.to_thread(_warm_geoip_database)]
        # With PROXY_SERVER every session is proxied, so the direct IP is never used.
        if not PROXY_SERVER:
            lookups.append(get_browser_geo())
        await asyncio.gather(*lookups)
        _warmed = True


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
    # The lifespan already ran it under uvicorn; this covers callers without one.
    await warm_up()
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

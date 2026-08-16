import logging
import time
from collections.abc import AsyncGenerator
from typing import Annotated, NamedTuple, cast

from fastapi import Header
from invisible_playwright.async_api import InvisiblePlaywright
from playwright.async_api import Browser, BrowserContext, Page
from playwright_captcha import (
    ClickSolver,
    FrameworkType,
)
from pydantic import BaseModel, Field

from src.consts import (
    BROWSER_LOCALE,
    LOG_LEVEL,
    MAX_ATTEMPTS,
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


# Cloudflare embeds its challenge widget in an iframe carrying
# allow="cross-origin-isolated". Firefox honours that by moving the iframe into
# a cross-origin-isolated content process, where Juggler sees a frame with no
# docShell and no URL, so content_frame() raises "Permission denied to access
# property docShell on cross-origin object" and the solver never reaches the
# checkbox.
#
# Turning the two policies off (as upstream Playwright's Firefox does, and as
# v2.1.0 did via camoufox's disable_coop=True) restores that access, and the
# solver then clicks the checkbox successfully.
#
# The COOP/COEP pair is not a demonstrated win: toggling it changed no outcome
# on any site measured, from either a datacenter or a residential address. It is
# kept for parity with v2.1.0, which clears the interactive challenge where this
# stack does not, because reaching the checkbox is a precondition for ever
# passing one.
#
# devtools.jsonview.enabled is load-bearing and must stay. Firefox renders
# application/json in a viewer whose CSP blocks eval, so page.evaluate() dies
# with "call to eval() blocked by CSP" and /v1 500s on every JSON API (#394).
BROWSER_PREFS = {
    "devtools.jsonview.enabled": False,
    "browser.tabs.remote.useCrossOriginOpenerPolicy": False,
    "browser.tabs.remote.useCrossOriginEmbedderPolicy": False,
}


class TimeoutTimer(BaseModel):
    duration: int  # in seconds
    start_time: float = Field(default_factory=time.perf_counter)

    def remaining(self) -> float:
        """Get remaining time in seconds."""
        return max(0, self.duration - (time.perf_counter() - self.start_time))


class BrowserDepClass(NamedTuple):
    page: Page
    solver: ClickSolver
    context: BrowserContext


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

    async with InvisiblePlaywright(
        headless=True,
        proxy=proxy_config,
        humanize=True,
        locale=BROWSER_LOCALE or "auto",
        extra_prefs=BROWSER_PREFS,
    ) as browser_raw:
        # InvisiblePlaywright yields a Browser instance
        browser = cast("Browser", browser_raw)
        context = await browser.new_context()
        page = await context.new_page()
        async with ClickSolver(
            # Not PATCHRIGHT: that path skips the unlockShadowRoot init script
            # and injects it over CDP instead, which Firefox has no session for
            # ("CDP session is only available in Chromium"). Cloudflare builds
            # its widget inside a closed shadow root, so without that script
            # nothing -- not the solver, not page.locator -- can see the
            # challenge iframe, and every solve attempt fails outright.
            framework=FrameworkType.PLAYWRIGHT,
            page=page,
            max_attempts=MAX_ATTEMPTS,
            attempt_delay=1,
        ) as solver:
            yield BrowserDepClass(page, solver, context)

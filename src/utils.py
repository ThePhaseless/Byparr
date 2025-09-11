import logging
import time
from collections.abc import AsyncGenerator
from typing import NamedTuple, cast

from camoufox import AsyncCamoufox
from playwright.async_api import Browser, BrowserContext, Page
from playwright_captcha import (
    ClickSolver,
    FrameworkType,
)
from pydantic import BaseModel, Field

from src.consts import (
    ADDON_PATH,
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


class TimeoutTimer(BaseModel):
    duration: int  # in seconds
    start_time: float = Field(default_factory=time.perf_counter)

    def remaining(self) -> float:
        """Get remaining time in seconds."""
        return max(0, self.duration - (time.perf_counter() - self.start_time))


class CamoufoxDepClass(NamedTuple):
    page: Page
    solver: ClickSolver
    context: BrowserContext


async def get_camoufox() -> AsyncGenerator[CamoufoxDepClass, None]:
    """Get Camoufox instance."""
    proxy_config = (
        {
            "server": PROXY_SERVER,
            "username": PROXY_USERNAME,
            "password": PROXY_PASSWORD,
        }
        if PROXY_SERVER
        else None
    )

    async with AsyncCamoufox(
        main_world_eval=True,
        addons=[ADDON_PATH],
        geoip=True,
        proxy=proxy_config,
        locale="en-US",
        headless=True,
        humanize=True,
        i_know_what_im_doing=True,
        config={"forceScopeAccess": True},  # add this when creating Camoufox instance
        disable_coop=True,  # add this when creating Camoufox instance
    ) as browser_raw:
        # Cast to Browser since AsyncCamoufox always returns a Browser, not BrowserContext
        browser = cast("Browser", browser_raw)
        context = await browser.new_context()
        page = await context.new_page()
        async with ClickSolver(
            framework=FrameworkType.CAMOUFOX,
            page=page,
            max_attempts=MAX_ATTEMPTS,
            attempt_delay=1,
        ) as solver:
            yield CamoufoxDepClass(page, solver, context)

import logging
from collections.abc import AsyncGenerator
from typing import NamedTuple, cast

from camoufox import AsyncCamoufox
from fastapi import Header, HTTPException
from httpx import codes
from playwright.async_api import Browser, BrowserContext, Page
from playwright_captcha import (
    ClickSolver,
    FrameworkType,
)

from src.consts import (
    ADDON_PATH,
    LOG_LEVEL,
    MAX_ATTEMPTS,
    PROXY,
)

solver_logger = logging.getLogger("playwright_captcha.solvers")
solver_logger.handlers.clear()
solver_logger.handlers.append(logging.NullHandler())

logger = logging.getLogger("uvicorn.error")
logger.setLevel(LOG_LEVEL)
if len(logger.handlers) == 0:
    logger.addHandler(logging.StreamHandler())


class CamoufoxDepType(NamedTuple):
    page: Page
    solver: ClickSolver
    context: BrowserContext


async def get_camoufox(
    proxy: str | None = Header(
        default=PROXY,
        examples=["protocol://username:password@host:port"],
        description="Override default proxy address",
    ),
) -> AsyncGenerator[CamoufoxDepType, None]:
    """Get Camoufox instance."""
    if proxy and proxy.startswith("socks5://") and "@" in proxy:
        raise HTTPException(
            status_code=codes.BAD_REQUEST,
            detail="SOCKS5 proxy with authentication is not supported. Check README for more info.",
        )

    async with AsyncCamoufox(
        main_world_eval=True,
        addons=[ADDON_PATH],
        geoip=True,
        proxy={"server": proxy} if proxy else None,
        locale="en-US",
        headless=True,
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
            yield CamoufoxDepType(page, solver, context)

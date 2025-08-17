import logging
from collections.abc import AsyncGenerator
from typing import cast

from camoufox import AsyncCamoufox
from fastapi import Header, HTTPException
from httpx import codes
from playwright.async_api import Browser, BrowserContext, Page
from playwright_captcha import (
    CaptchaType,
    ClickSolver,
    FrameworkType,
)

from src.consts import (
    ADDON_PATH,
    LOG_LEVEL,
    PROXY,
)

solver_logger = logging.getLogger("playwright_captcha.solvers")
solver_logger.handlers.clear()
solver_logger.handlers.append(logging.NullHandler())

logger = logging.getLogger("uvicorn.error")
logger.setLevel(LOG_LEVEL)
if len(logger.handlers) == 0:
    logger.addHandler(logging.StreamHandler())


async def solve_turnstile(page: Page):
    """Solve Turnstile challenge."""
    async with ClickSolver(framework=FrameworkType.CAMOUFOX, page=page) as solver:
        await page.goto("https://www.crunchbase.com/organization/scrapingbee")
        await page.wait_for_load_state(state="domcontentloaded")
        await page.wait_for_load_state("networkidle")

        # Solve the captcha
        await solver.solve_captcha(  # pyright: ignore[reportUnknownMemberType]
            captcha_container=page,
            captcha_type=CaptchaType.CLOUDFLARE_INTERSTITIAL,
        )
        logger.debug("Challenge solved successfully.")


async def get_camoufox(
    proxy: str | None = Header(
        default=PROXY,
        examples=["protocol://username:password@host:port"],
        description="Override default proxy address",
    ),
) -> AsyncGenerator[BrowserContext, None]:
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
        proxy=proxy,
        locale="en-US",
        headless=True,
        i_know_what_im_doing=True,
        config={"forceScopeAccess": True},  # add this when creating Camoufox instance
        disable_coop=True,  # add this when creating Camoufox instance
    ) as browser_raw:
        # Cast to Browser since AsyncCamoufox always returns a Browser, not BrowserContext
        browser = cast("Browser", browser_raw)
        context = await browser.new_context()
        yield context

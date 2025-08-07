import logging
from pathlib import Path

from camoufox import AsyncCamoufox
from fastapi import Header, HTTPException
from httpx import codes
from playwright.async_api import Page
from playwright_captcha import (  # pyright: ignore[reportMissingTypeStubs]
    CaptchaType,
    ClickSolver,
    FrameworkType,
)
from playwright_captcha.utils.camoufox_add_init_script.add_init_script import (  # pyright: ignore[reportMissingTypeStubs]
    get_addon_path,
)

from src.consts import (
    HEADLESS_MODE,
    LOG_LEVEL,
    PROXY,
)

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
        logger.info("Captcha Turnstile solved")


async def get_camoufox(
    proxy: str | None = Header(
        default=PROXY,
        examples=["protocol://username:password@host:port"],
        description="Override default proxy address",
    ),
):
    """Get Camoufox instance."""
    if proxy and proxy.startswith("socks5://") and "@" in proxy:
        raise HTTPException(
            status_code=codes.BAD_REQUEST,
            detail="SOCKS5 proxy with authentication is not supported. Check README for more info.",
        )

    async with AsyncCamoufox(
        main_world_eval=True,  # add this
        addons=[str(Path(get_addon_path()).resolve())],  # add this
        geoip=True,
        proxy=proxy,
        locale="en-US",
        persistent_context=True,
        user_data_dir="browser_data",
        headless=HEADLESS_MODE,
        i_know_what_im_doing=True,
        config={"forceScopeAccess": True},  # add this when creating Camoufox instance
        disable_coop=True,  # add this when creating Camoufox instance
    ) as sb:
        yield sb

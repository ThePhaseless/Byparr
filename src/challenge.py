import time
from asyncio import sleep
from contextlib import suppress

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import FloatRect, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright_captcha.solvers.click.cloudflare.utils.detection import (
    CF_INTERSTITIAL_INDICATORS_SELECTORS,
    detect_cloudflare_challenge,
)

from src.utils import TimeoutTimer, logger

__all__ = [
    "CF_INTERSTITIAL_INDICATORS_SELECTORS",
    "challenge_present",
    "solve_challenge",
]

POLL_INTERVAL = 0.25
CLICK_SETTLE = 1.5
CLICK_COOLDOWN = 4
PROBE_INTERVAL = 0.5
TOKEN_READ_TIMEOUT = 1000
BOX_READ_TIMEOUT = 1000
CHECKBOX_INSET = 25
TURNSTILE_INPUT = 'input[name="cf-turnstile-response"]'
WIDGET_ANCESTOR_DEPTHS = (1, 2, 3, 4)
WIDGET_MIN_WIDTH = 40
WIDGET_MIN_HEIGHT = 20
WIDGET_MAX_HEIGHT = 120


async def challenge_present(page: Page) -> bool:
    """Report whether the Cloudflare interstitial is up."""
    return await detect_cloudflare_challenge(page, "interstitial")


async def widget_box(page: Page) -> FloatRect | None:
    """Measure the widget container with locators; running page scripts resets the challenge."""
    for depth in WIDGET_ANCESTOR_DEPTHS:
        widget = page.locator(f"{TURNSTILE_INPUT} >> xpath=ancestor::div[{depth}]")
        with suppress(PlaywrightError, PlaywrightTimeoutError):
            if await widget.count() == 0:
                continue
            box = await widget.first.bounding_box(timeout=BOX_READ_TIMEOUT)
            if (
                box
                and box["width"] > WIDGET_MIN_WIDTH
                and WIDGET_MIN_HEIGHT < box["height"] < WIDGET_MAX_HEIGHT
            ):
                return box
    return None


async def click_checkbox(page: Page) -> bool:
    """Click the checkbox through its container, leaving its closed shadow root alone."""
    box = await widget_box(page)
    if box is None:
        return False
    await page.mouse.move(box["x"] + CHECKBOX_INSET, box["y"] + box["height"] / 2)
    try:
        await page.mouse.down()
    finally:
        await page.mouse.up()
    return True


async def checkbox_already_answered(page: Page) -> bool:
    """Report whether Turnstile has already filled in its response token."""
    token = page.locator(TURNSTILE_INPUT)
    with suppress(PlaywrightError, PlaywrightTimeoutError):
        if await token.count() > 0:
            return bool(await token.first.input_value(timeout=TOKEN_READ_TIMEOUT))
    return False


async def challenge_is_gone(page: Page) -> bool:
    """Confirm the interstitial is really gone and not just between navigations."""
    if await challenge_present(page):
        return False
    await sleep(POLL_INTERVAL)
    return not await challenge_present(page)


async def solve_challenge(page: Page, timer: TimeoutTimer) -> None:
    """Wait out the interstitial, clicking its checkbox whenever one is offered."""
    logger.info("Challenge detected, waiting for it to clear...")
    clicks = 0
    next_click = 0.0
    while True:
        if await challenge_is_gone(page):
            logger.debug("Challenge cleared.")
            if clicks:
                await sleep(min(CLICK_SETTLE, timer.remaining()))
            return

        if time.perf_counter() >= next_click:
            landed = False
            with suppress(PlaywrightError, PlaywrightTimeoutError):
                landed = not await checkbox_already_answered(
                    page
                ) and await click_checkbox(page)
            if landed:
                clicks += 1
                logger.info("Clicked the challenge checkbox (attempt %d).", clicks)
            next_click = time.perf_counter() + (
                CLICK_COOLDOWN if landed else PROBE_INTERVAL
            )

        if timer.remaining() <= 0:
            break
        await sleep(POLL_INTERVAL)

    message = "Challenge still present when the request budget ran out"
    raise TimeoutError(message)

import asyncio

import nodriver as webdriver
from nodriver.core.element import Element

from src.utils import logger
from src.utils.consts import CHALLENGE_TITLES
from src.utils.extentions import downloaded_extentions


async def new_browser():
    config: webdriver.Config = webdriver.Config()
    config.sandbox = False
    config.add_argument(f"--load-extension={','.join(downloaded_extentions)}")

    return await webdriver.start(config=config)


async def bypass_cloudflare(page: webdriver.Tab):
    challenged = False
    while True:
        await page.wait(0.5)
        logger.debug(f"Current page: {page.target.title}")
        if page.target.title not in CHALLENGE_TITLES:
            return challenged
        if not challenged:
            logger.info("Found challenge")
            challenged = True
        try:
            elem = await asyncio.wait_for(
                page.query_selector(".cf-turnstile-wrapper"), timeout=3
            )
        except asyncio.TimeoutError:
            logger.warning("Timed out waiting for element, trying again")
            continue
        if isinstance(elem, Element):
            await elem.mouse_click()

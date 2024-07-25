from pathlib import Path

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
        await page
        await page.wait(0.5)
        logger.debug(page.target.title)
        if page.target.title not in CHALLENGE_TITLES:
            return challenged
        if not challenged:
            logger.info("Found challenge")
            await page.save_screenshot(Path("screenshots/screenshot.png"))
            challenged = True
            Path("screenshots").mkdir(exist_ok=True)
        logger.debug("Clicking element")
        await page.save_screenshot(Path("screenshots/screenshot.png"))
        elem = await page.query_selector(".cf-turnstile-wrapper")
        if isinstance(elem, Element):
            await elem.mouse_click()

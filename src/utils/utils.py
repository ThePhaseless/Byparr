import logging
from venv import logger

import nodriver as webdriver
from nodriver.core.element import Element

from src.utils.consts import CHALLENGE_TITLES


def get_logger():
    return logging.getLogger("uvicorn.error")


async def new_browser():
    config: webdriver.Config = webdriver.Config()
    config.sandbox = False

    return await webdriver.start(config=config)


async def bypass_cloudflare(page: webdriver.Tab):
    while True:
        await page
        if page.target.title not in CHALLENGE_TITLES:
            break
        elem = await page.query_selector(".cf-turnstile-wrapper")
        if isinstance(elem, Element):
            logger.info(f"Clicking element: {elem}")
            await elem.mouse_click()

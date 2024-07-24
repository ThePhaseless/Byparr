import nodriver as webdriver
from nodriver.core.element import Element

from src.utils import logger
from src.utils.utils import CHALLENGE_TITLES


async def new_browser():
    config: webdriver.Config = webdriver.Config()
    config.sandbox = False

    return await webdriver.start(config=config)


async def bypass_cloudflare(page: webdriver.Tab):
    challenged = False
    while True:
        logger.info("Bypassing cloudflare")
        await page
        await page.wait(0.5)
        if page.target.title not in CHALLENGE_TITLES:
            return challenged
        challenged = True
        elem = await page.query_selector(".cf-turnstile-wrapper")
        if isinstance(elem, Element):
            logger.info(f"Clicking element: {elem}")
            await elem.mouse_click()

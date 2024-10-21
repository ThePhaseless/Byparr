import asyncio

import nodriver as webdriver
from nodriver.core.element import Element

from src.utils import logger
from src.utils.consts import CHALLENGE_TITLES, UBLOCK_TITLE
from src.utils.extentions import download_extentions

downloaded_extentions = download_extentions()


async def new_browser():
    """
    Create a new browser instance with the specified configuration.

    Returns
    -------
        A coroutine that resolves to the newly created browser instance.

    Raises
    ------
        Any exceptions that may occur during the creation of the browser instance.

    """
    config: webdriver.Config = webdriver.Config(
        browser_executable_path="/usr/bin/chromium", sandbox=True
    )
    config.add_argument(f"--load-extension={','.join(downloaded_extentions)}")

    return await webdriver.start(config=config)


async def bypass_cloudflare(page: webdriver.Tab):
    """
    Asynchronously bypasses Cloudflare challenges on the given web page.

    Args:
    ----
        page (webdriver.Tab): The web page to bypass Cloudflare challenges on.

    Returns:
    -------
        bool: True if the page was successfully bypassed, False otherwise.

    Raises:
    ------
        Exception: If the element containing the Cloudflare challenge could not be found.

    Notes:
    -----
        This function repeatedly checks the title of the page until it is not in the
        list of known Cloudflare challenge titles. Once a challenge is found, it attempts
        to locate the element containing the challenge and click it. If the element cannot
        be found within a certain time limit, the function will retry. If the element is
        found, it will be clicked. If the element cannot be found at all, an exception will
        be raised.

    """
    challenged = False
    await page
    while True:
        logger.debug(f"Current page: {page.target.title}")

        if page.target.title not in CHALLENGE_TITLES:
            if page.target.title == UBLOCK_TITLE:
                continue
            return challenged

        if not challenged:
            logger.info("Found challenge")
            challenged = True

        if (
            page.target.title != "Just a moment..."
        ):  # If not in cloudflare, wait for autobypass
            await asyncio.sleep(3)
            logger.debug("Waiting for challenge to complete")
            continue

        loaded = False
        try:
            elem = await page.find("lds-ring", timeout=3)
        except asyncio.TimeoutError:
            logger.error(
                "Couldn't find lds-ring, probably not a cloudflare challenge, trying again..."
            )
            continue
        if elem is None:
            logger.error("elem is None")
            logger.debug(elem)
            raise InvalidElementError

        parent = elem.parent
        if not isinstance(parent, Element) or parent.attributes is None:
            logger.error("parent is not an element or has no attributes")
            logger.debug(parent)
            raise InvalidElementError

        for attr in parent.attributes:
            if attr == "display: none; visibility: hidden;":
                loaded = True
                logger.info("Page loaded")

        if not loaded:
            logger.debug("Challenge still loading")
            continue

        elem = await page.find("input")
        elem = elem.parent
        # Get the element containing the shadow root
        if isinstance(elem, Element) and elem.shadow_roots:
            logger.info("Found shadow root")
            inner_elem = Element(elem.shadow_roots[0], page, elem.tree).children[0]
            if isinstance(inner_elem, Element):
                logger.info("Found elem inside shadow root")
                logger.debug("Clicking element")
                await inner_elem.mouse_click()
                await asyncio.sleep(3)
                continue
            logger.warning(
                "Couldn't find element containing shadow root, trying again..."
            )
            logger.debug(inner_elem)
        else:
            logger.warning("Coulnd't find checkbox, trying again...")
            logger.debug(elem)


class InvalidElementError(Exception):
    pass

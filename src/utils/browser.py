import asyncio

import nodriver as webdriver
from nodriver.core.element import Element

from src.utils import logger
from src.utils.consts import CHALLENGE_TITLES
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
    while True:
        await page
        logger.debug(f"Current page: {page.target.title}")
        if page.target.title not in CHALLENGE_TITLES:
            return challenged
        if not challenged:
            logger.info("Found challenge")
            challenged = True
        try:
            elem = await page.find(
                "Verify you are human by completing the action below.",
                timeout=3,
            )
        # If challenge solves by itself
        except asyncio.TimeoutError:
            if page.target.title not in CHALLENGE_TITLES:
                return challenged

        if elem is None:
            logger.debug("Couldn't find the title, trying other method...")
            continue

        if not isinstance(elem, Element):
            logger.fatal("Element is a string, please report this to Byparr dev")
            raise InvalidElementError

        elem = await page.find("input")
        elem = elem.parent
        # Get the element containing the shadow root

        if isinstance(elem, Element) and elem.shadow_roots:
            inner_elem = Element(elem.shadow_roots[0], page, elem.tree).children[0]
            if isinstance(inner_elem, Element):
                logger.debug("Clicking element")
                await inner_elem.mouse_click()
            else:
                logger.warning(
                    "Element is a string, please report this to Byparr dev"
                )  # I really hope this never happens
        else:
            logger.warning("Coulnd't find checkbox, trying again...")


def get_first_div(elem):
    """
    Retrieve the first div element from the given element's children.

    Args:
    ----
        elem: The parent element to search for a div child.

    Returns:
    -------
        The first div element found, or the original element if no div is found.

    """
    for child in elem.children:
        if child.tag_name == "div":
            return child
    raise InvalidElementError


class InvalidElementError(Exception):
    pass

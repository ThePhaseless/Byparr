import base64
from contextlib import suppress

from invisible_playwright.async_api import Error
from playwright.async_api import Page

from src.models import LinkRequest
from src.utils import TimeoutTimer, logger, remaining_ms


async def build_response_content(
    page: Page,
    request: LinkRequest,
    page_request: object,
    timer: TimeoutTimer,
) -> tuple[str, str]:
    """Build (content_type, response_content) from the settled page."""
    if request.return_only_cookies:
        return "text/html", ""

    if page_request and page_request.headers.get("content-type", "").startswith(
        "application/pdf"
    ):
        return await fetch_pdf_content(page)

    return "text/html", await read_settled_html(page, timer)


async def read_settled_html(page: Page, timer: TimeoutTimer) -> str:
    """Read the page's HTML, reading it again if a navigation pulled it away."""
    try:
        return await page.content()
    except Error:
        logger.info("Page navigated while being read; reading it again once idle")
        with suppress(Error):
            await page.wait_for_load_state("networkidle", timeout=remaining_ms(timer))
        return await page.content()


async def fetch_pdf_content(page: Page) -> tuple[str, str]:
    """Fetch raw PDF bytes as base64, falling back to viewer HTML on failure."""
    try:
        fetch_response = await page.request.fetch(page.url)
        response_content = base64.b64encode(await fetch_response.body()).decode("ascii")
    except Exception:
        logger.exception("Failed to fetch PDF bytes, falling back to viewer HTML")
        return "text/html", await page.content()
    return "application/pdf", response_content

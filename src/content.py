import base64

from playwright.async_api import Page

from src.models import LinkRequest
from src.utils import logger


async def build_response_content(
    page: Page,
    request: LinkRequest,
    page_request: object,
    *,
    challenge_detected: bool,
    page_html: str | None,
) -> tuple[str, str]:
    """Build (content_type, response_content) from the settled page."""
    if request.return_only_cookies:
        return "text/html", ""

    if page_request and page_request.headers.get("content-type", "").startswith(
        "application/pdf"
    ):
        return await fetch_pdf_content(page)

    response_content = (
        page_html
        if page_html is not None and not challenge_detected
        else await page.content()
    )
    return "text/html", response_content


async def fetch_pdf_content(page: Page) -> tuple[str, str]:
    """Fetch raw PDF bytes as base64, falling back to viewer HTML on failure."""
    try:
        fetch_response = await page.request.fetch(page.url)
        response_content = base64.b64encode(await fetch_response.body()).decode("ascii")
    except Exception:
        logger.exception("Failed to fetch PDF bytes, falling back to viewer HTML")
        return "text/html", await page.content()
    return "application/pdf", response_content

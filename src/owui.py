"""Open WebUI external web loader endpoint: POST /load."""

from __future__ import annotations

from hmac import compare_digest
from typing import Annotated

import trafilatura
from fastapi import APIRouter, Depends, Header, HTTPException
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from pydantic import BaseModel

from src.consts import OWUI_API_KEY
from src.utils import BrowserDepClass, get_browser, logger

router = APIRouter(tags=["Open WebUI"])

BrowserDep = Annotated[BrowserDepClass, Depends(get_browser)]


class LoadRequest(BaseModel):
    urls: list[str]


class LoadResult(BaseModel):
    page_content: str
    metadata: dict[str, str]


def require_auth(authorization: Annotated[str | None, Header()] = None) -> None:
    """Enforce a bearer token on /load when OWUI_API_KEY is set."""
    if not OWUI_API_KEY:
        return
    if authorization is None or not compare_digest(
        authorization.encode(), f"Bearer {OWUI_API_KEY}".encode()
    ):
        raise HTTPException(status_code=401, detail="Unauthorized")


async def _extract_content(page: Page) -> str:
    """Return the page's main article text, falling back to visible text."""
    article = trafilatura.extract(await page.content())
    if article:
        return article
    result = await page.locator("body").inner_text()
    return "\n".join(line.strip() for line in result.splitlines() if line.strip())


@router.post("/load", response_model=list[LoadResult])
async def load_urls(
    request: LoadRequest,
    _auth: Annotated[None, Depends(require_auth)],
    dep: BrowserDep,
) -> list[LoadResult]:
    """
    Fetch URLs through the anti-bot browser and return their text content.

    Each URL is fetched sequentially; a failing URL yields empty
    page_content so Open WebUI's RAG pipeline degrades gracefully.
    """
    results: list[LoadResult] = []
    for url in request.urls:
        try:
            await dep.page.goto(url, timeout=60_000)
            await dep.page.wait_for_load_state("domcontentloaded", timeout=30_000)
            try:
                await dep.page.wait_for_load_state("networkidle", timeout=15_000)
            except PlaywrightTimeoutError:
                logger.debug("networkidle timed out for %s; extracting anyway", url)
            content = await _extract_content(dep.page)
        except Exception as exc:
            logger.warning("Failed to load %s: %s", url, exc)
            content = ""
        results.append(LoadResult(page_content=content, metadata={"source": url}))
    return results

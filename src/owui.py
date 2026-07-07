"""
src/owui.py — Open WebUI external web loader endpoint.

Implements the contract expected by Open WebUI's WEB_LOADER_ENGINE=external:
  POST /load
    Request:  {"urls": ["https://..."]}
    Response: [{"page_content": str, "metadata": {"source": str}}]

Reuses Byparr's existing browser dependency injection so each request
gets a properly-initialised browser context with challenge solving.
Uses document.body.innerText for content extraction.

Configure in Open WebUI:
  WEB_LOADER_ENGINE=external
  EXTERNAL_WEB_LOADER_URL=http://byparr:8191/load
  EXTERNAL_WEB_LOADER_API_KEY=<value of OWUI_API_KEY env var, if set>
"""

from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from src.utils import BrowserDepClass, get_browser, logger

_API_KEY: str | None = os.getenv("OWUI_API_KEY") or None

router = APIRouter(tags=["Open WebUI"])

BrowserDep = Annotated[BrowserDepClass, Depends(get_browser)]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class LoadRequest(BaseModel):
    urls: list[str]


class LoadResult(BaseModel):
    page_content: str
    metadata: dict[str, Any]


# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------


async def _extract_content(page: Any) -> str:
    """
    Extract text content from the page using document.body.innerText.
    Whitespace is collapsed for clean RAG chunking.
    """
    result: str = await page.evaluate("""
        () => {
            return document.body ? document.body.innerText : "";
        }
    """)
    lines = [line.strip() for line in result.splitlines() if line.strip()]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def _check_auth(authorization: str | None) -> None:
    if not _API_KEY:
        return
    if authorization != f"Bearer {_API_KEY}":
        raise HTTPException(status_code=401, detail="Unauthorized")


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/load", response_model=list[LoadResult])
async def load_urls(
    request: LoadRequest,
    authorization: Annotated[str | None, Header()] = None,
    dep: BrowserDep = None,  # type: ignore[assignment]
) -> list[LoadResult]:
    """
    Fetch URLs through InvisiblePlaywright, bypassing Cloudflare challenges.
    Returns plain-text content for Open WebUI's RAG pipeline.
    Failed URLs return empty page_content so the search degrades gracefully.
    """
    _check_auth(authorization)

    results: list[LoadResult] = []

    for url in request.urls:
        try:
            logger.info("OWUI loader fetching: %s", url)
            await dep.page.goto(url, timeout=60_000)
            await dep.page.wait_for_load_state("domcontentloaded", timeout=30_000)
            await dep.page.wait_for_load_state("networkidle", timeout=15_000)
            content = await _extract_content(dep.page)
            logger.debug("OWUI loader: %s -> %d chars", url, len(content))
            results.append(LoadResult(page_content=content, metadata={"source": url}))
        except Exception as exc:  # noqa: BLE001
            logger.warning("OWUI loader failed for %s: %s", url, exc)
            results.append(LoadResult(page_content="", metadata={"source": url}))

    return results

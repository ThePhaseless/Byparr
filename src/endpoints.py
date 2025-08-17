import time
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from playwright.async_api import BrowserContext

from src.consts import CHALLENGE_TITLES
from src.models import (
    HealthcheckResponse,
    LinkRequest,
    LinkResponse,
    Solution,
)
from src.utils import get_camoufox, logger, solve_turnstile

router = APIRouter()

CamoufoxDep = Annotated[BrowserContext, Depends(get_camoufox)]


@router.get("/", include_in_schema=False)
def read_root():
    """Redirect to /docs."""
    logger.debug("Redirecting to /docs")
    return RedirectResponse(url="/docs", status_code=301)


@router.get("/health")
async def health_check(sb: CamoufoxDep):
    """Health check endpoint."""
    health_check_request = await read_item(
        LinkRequest.model_construct(url="https://google.com"),
        sb,
    )

    if health_check_request.solution.status != HTTPStatus.OK:
        raise HTTPException(
            status_code=500,
            detail="Health check failed",
        )

    return HealthcheckResponse(user_agent=health_check_request.solution.user_agent)


@router.post("/v1")
async def read_item(request: LinkRequest, sb: CamoufoxDep) -> LinkResponse:
    """Handle POST requests."""
    start_time = int(time.time() * 1000)
    request.url = request.url.replace('"', "").strip()
    page = await sb.new_page()
    page_request = await page.goto(request.url, timeout=request.max_timeout * 1000)
    logger.debug(f"Got webpage: {request.url}")
    if await page.title() in CHALLENGE_TITLES:
        logger.info("Challenge detected, attempting to solve...")
        await solve_turnstile(page)

    cookies = await sb.cookies()

    return LinkResponse(
        message="Success",
        solution=Solution(
            user_agent=await page.evaluate("navigator.userAgent"),
            url=page.url,
            status=200,
            cookies=cookies,
            headers=page_request.headers if page_request else {},
            response=await page.content(),
        ),
        start_timestamp=start_time,
    )

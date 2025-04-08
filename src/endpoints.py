import time
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sbase import BaseCase

from src.consts import CHALLENGE_TITLES
from src.models import (
    LinkRequest,
    LinkResponse,
    Solution,
)

from .utils import get_sb, logger, save_screenshot

router = APIRouter()

SeleniumDep = Annotated[BaseCase, Depends(get_sb)]


@router.get("/", include_in_schema=False)
def read_root():
    """Redirect to /docs."""
    logger.debug("Redirecting to /docs")
    return RedirectResponse(url="/docs", status_code=301)


@router.get("/health")
def health_check(sb: SeleniumDep):
    """Health check endpoint."""
    health_check_request = read_item(
        LinkRequest.model_construct(url="https://google.com"),
        sb,
    )

    if health_check_request.solution.status != HTTPStatus.OK:
        raise HTTPException(
            status_code=500,
            detail="Health check failed",
        )

    return {"status": "ok"}


@router.post("/v1")
def read_item(request: LinkRequest, sb: SeleniumDep) -> LinkResponse:
    """Handle POST requests."""
    start_time = int(time.time() * 1000)
    sb.uc_open_with_reconnect(request.url)
    logger.debug(f"Got webpage: {request.url}")
    source_bs = sb.get_beautiful_soup()
    title_tag = source_bs.title
    if title_tag and title_tag.string in CHALLENGE_TITLES:
        logger.debug("Challenge detected")
        sb.uc_gui_click_captcha()
        logger.info("Clicked captcha")

    if sb.get_title() in CHALLENGE_TITLES:
        save_screenshot(sb)
        raise HTTPException(status_code=500, detail="Could not bypass challenge")

    cookies = sb.get_cookies()
    for cookie in cookies:
        if 'expiry' in cookie:
            cookie['expires'] = cookie['expiry']

    return LinkResponse(
        message="Success",
        solution=Solution(
            userAgent=sb.get_user_agent(),
            url=sb.get_current_url(),
            status=200,
            cookies=cookies,
            headers={},
            response=str(sb.get_beautiful_soup()),
        ),
        start_timestamp=start_time,
    )

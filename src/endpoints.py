import time
from asyncio import wait_for
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from playwright_captcha import CaptchaType

from src.consts import CHALLENGE_TITLES
from src.models import (
    HealthcheckResponse,
    LinkRequest,
    LinkResponse,
    Solution,
)
from src.utils import CamoufoxDepType, get_camoufox, logger

router = APIRouter()

CamoufoxDep = Annotated[CamoufoxDepType, Depends(get_camoufox)]


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
async def read_item(request: LinkRequest, dep: CamoufoxDep) -> LinkResponse:
    """Handle POST requests."""
    start_time = int(time.time() * 1000)
    request.url = request.url.replace('"', "").strip()
    page_request = await dep.page.goto(request.url)
    await dep.page.wait_for_load_state(state="domcontentloaded")
    await dep.page.wait_for_load_state("networkidle")

    if await dep.page.title() in CHALLENGE_TITLES:
        logger.info("Challenge detected, attempting to solve...")
        # Solve the captcha
        remaining_timeout = request.max_timeout - (int(time.time()) - start_time / 1000)
        logger.debug(
            "Remaining timeout for solving the challenge: %d ms", remaining_timeout
        )
        await wait_for(
            dep.solver.solve_captcha(  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType]
                captcha_container=dep.page,
                captcha_type=CaptchaType.CLOUDFLARE_INTERSTITIAL,
            ),
            timeout=remaining_timeout,
        )
        logger.debug("Challenge solved successfully.")

    cookies = await dep.context.cookies()

    return LinkResponse(
        message="Success",
        solution=Solution(
            user_agent=await dep.page.evaluate("navigator.userAgent"),
            url=dep.page.url,
            status=page_request.status if page_request else HTTPStatus.OK,
            cookies=cookies,
            headers=page_request.headers if page_request else {},
            response=await dep.page.content(),
        ),
        start_timestamp=start_time,
    )

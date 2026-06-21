import base64
import time
import warnings
from asyncio import wait_for
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright_captcha import CaptchaType

from src.consts import CHALLENGE_TITLES
from src.models import (
    HealthcheckResponse,
    LinkRequest,
    LinkResponse,
    Solution,
)
from src.utils import BrowserDepClass, TimeoutTimer, get_browser, logger

warnings.filterwarnings("ignore", category=SyntaxWarning)


router = APIRouter()

BrowserDep = Annotated[BrowserDepClass, Depends(get_browser)]


@router.get("/", include_in_schema=False)
def read_root():
    """Redirect to /docs."""
    logger.debug("Redirecting to /docs")
    return RedirectResponse(url="/docs", status_code=301)


@router.get("/health")
async def health_check(sb: BrowserDep):
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
async def read_item(request: LinkRequest, dep: BrowserDep) -> LinkResponse:
    """Handle POST requests."""
    start_time = int(time.time() * 1000)

    timer = TimeoutTimer(duration=request.max_timeout)

    request.url = request.url.replace('"', "").strip()

    if request.block_media:
        async def block_media_route(route):
            if route.request.resource_type in ("image", "media", "font"):
                await route.abort()
            else:
                await route.continue_()

        await dep.page.route("**/*", block_media_route)

    try:
        page_request = await dep.page.goto(
            request.url, timeout=timer.remaining() * 1000
        )
        status = page_request.status if page_request else HTTPStatus.OK
        await dep.page.wait_for_load_state(
            state="domcontentloaded", timeout=timer.remaining() * 1000
        )

        if await dep.page.title() in CHALLENGE_TITLES:
            logger.info("Challenge detected, attempting to solve...")
            # Solve the captcha
            await wait_for(
                dep.solver.solve_captcha(  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType]
                    captcha_container=dep.page,
                    captcha_type=CaptchaType.CLOUDFLARE_INTERSTITIAL,
                    wait_checkbox_attempts=1,
                    wait_checkbox_delay=0.5,
                ),
                timeout=timer.remaining(),
            )
            status = HTTPStatus.OK
            logger.debug("Challenge solved successfully.")
        else:
            try:
                await dep.page.wait_for_load_state(
                    "networkidle", timeout=timer.remaining() * 1000
                )
            except PlaywrightTimeoutError:
                logger.warning(
                    "Timed out waiting for networkidle after domcontentloaded; continuing"
                )
    except (TimeoutError, PlaywrightTimeoutError) as e:
        logger.error("Timed out while loading the page or solving the challenge")
        raise HTTPException(
            status_code=408,
            detail="Timed out while loading the page or solving the challenge",
        ) from e

    cookies = await dep.context.cookies()

    content_type = "text/html"
    response_content = ""

    if request.return_only_cookies:
        response_content = ""
    elif page_request and page_request.headers.get("content-type", "").startswith(
        "application/pdf"
    ):
        content_type = "application/pdf"
        try:
            fetch_response = await dep.page.request.fetch(dep.page.url)
            response_content = base64.b64encode(
                await fetch_response.body()
            ).decode("ascii")
        except Exception:
            logger.exception("Failed to fetch PDF bytes, falling back to viewer HTML")
            content_type = "text/html"
            response_content = await dep.page.content()
    else:
        response_content = await dep.page.content()

    return LinkResponse(
        message="Success",
        solution=Solution(
            user_agent=await dep.page.evaluate("navigator.userAgent"),
            url=dep.page.url,
            status=status,
            cookies=cookies,
            headers=page_request.headers if page_request else {},
            response=response_content,
            content_type=content_type,
        ),
        start_timestamp=start_time,
    )

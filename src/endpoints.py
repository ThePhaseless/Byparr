import time
import warnings
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from src.challenge import challenge_present, solve_challenge
from src.content import build_response_content
from src.models import (
    HealthcheckResponse,
    LinkRequest,
    LinkResponse,
    Solution,
)
from src.utils import (
    BrowserDepClass,
    TimeoutTimer,
    get_browser,
    logger,
    remaining_ms,
)

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

    await setup_routes(request, dep)

    try:
        challenge_detected, page_html, page_request = await _navigate_and_solve(
            dep, request, timer
        )
    except (TimeoutError, PlaywrightTimeoutError) as e:
        logger.error("Timed out while loading the page or solving the challenge")
        raise HTTPException(
            status_code=408,
            detail="Timed out while loading the page or solving the challenge",
        ) from e
    except PlaywrightError as e:
        logger.error("Could not reach the target: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach the target: {e}",
        ) from e

    cookies = await dep.context.cookies()
    content_type, response_content = await build_response_content(
        dep.page,
        request,
        page_request,
        challenge_detected=challenge_detected,
        page_html=page_html,
    )

    user_agent = (
        page_request.request.headers.get("user-agent") or "" if page_request else ""
    )

    return LinkResponse(
        message="Success",
        solution=Solution(
            user_agent=user_agent,
            url=dep.page.url,
            status=HTTPStatus.OK,
            cookies=cookies,
            headers=page_request.headers if page_request else {},
            response=response_content,
            content_type=content_type,
        ),
        start_timestamp=start_time,
    )


async def setup_routes(request: LinkRequest, dep: BrowserDep) -> None:
    """Install request routes for media blocking."""
    if request.block_media:

        async def block_media_route(route) -> None:
            if route.request.resource_type in ("image", "media", "font"):
                await route.abort()
            else:
                await route.continue_()

        await dep.page.route("**/*", block_media_route)


async def _navigate_and_solve(
    dep: BrowserDep,
    request: LinkRequest,
    timer: TimeoutTimer,
) -> tuple[bool, str | None, object]:
    """Navigate to the URL, then solve a challenge or wait for network idle."""
    page_html: str | None = None
    page_request = await dep.page.goto(request.url, timeout=remaining_ms(timer))
    await dep.page.wait_for_load_state(
        state="domcontentloaded", timeout=remaining_ms(timer)
    )

    if not await challenge_present(dep.page):
        page_html = await dep.page.content()
        await _wait_for_networkidle(dep, timer)
        return False, page_html, page_request

    await solve_challenge(dep.page, timer)
    await _wait_for_networkidle(dep, timer)
    return True, page_html, page_request


async def _wait_for_networkidle(dep: BrowserDep, timer: TimeoutTimer) -> None:
    """Wait for network idle, tolerating post-DOM-load stalls."""
    try:
        await dep.page.wait_for_load_state("networkidle", timeout=remaining_ms(timer))
    except PlaywrightTimeoutError:
        logger.info(
            "networkidle timed out after domcontentloaded; continuing with loaded page"
        )

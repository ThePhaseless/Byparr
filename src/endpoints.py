import time
import warnings
from http import HTTPStatus
from typing import Annotated
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Route
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


POST_CONTENT_TYPE = "application/x-www-form-urlencoded"
MEDIA_RESOURCE_TYPES = ("image", "media", "font")


def _urls_match(first: str, second: str) -> bool:
    """Compare navigation URLs, ignoring fragments and percent-encoding."""
    return unquote(first.split("#", 1)[0]) == unquote(second.split("#", 1)[0])


def _navigation_headers(request: LinkRequest) -> dict[str, str] | None:
    """Merge caller headers, defaulting post_data to form encoding."""
    headers = dict(request.headers or {})
    if request.post_data is not None and not any(
        key.lower() == "content-type" for key in headers
    ):
        headers["content-type"] = POST_CONTENT_TYPE
    return headers or None


async def setup_routes(request: LinkRequest, dep: BrowserDep) -> None:
    """
    Install one route handler covering media blocking and POST navigation.

    A single handler keeps media blocking and the method override from
    fighting over Playwright's reverse registration order. The POST override
    applies to every main-frame navigation to the target URL, so a challenge
    reload after solving re-issues the POST with the cleared cookies.
    """
    wants_post = request.cmd == "request.post"
    if not (request.block_media or wants_post or request.headers):
        return

    first_navigation = True

    async def handle_route(route: Route) -> None:
        nonlocal first_navigation
        if request.block_media and route.request.resource_type in MEDIA_RESOURCE_TYPES:
            await route.abort()
            return

        if route.request.is_navigation_request() and (
            route.request.frame.parent_frame is None
        ):
            # The URL check re-applies the POST after a challenge reload; the
            # first-navigation fallback covers browser URL normalization.
            matches_target = _urls_match(route.request.url, request.url)
            if first_navigation:
                first_navigation = False
                matches_target = True

            if matches_target:
                if wants_post:
                    await route.continue_(
                        method="POST",
                        post_data=request.post_data,
                        headers=_navigation_headers(request),
                    )
                    return
                headers = _navigation_headers(request)
                if headers:
                    await route.continue_(headers=headers)
                    return

        await route.continue_()

    await dep.page.route("**/*", handle_route)


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

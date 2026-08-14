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
from playwright_captcha.solvers.click.cloudflare.utils.detection import (
    detect_cloudflare_challenge,
)

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

# Headers to strip from the fulfilled response: CSP is removed for navigation
# freedom, and content-encoding/content-length are stale once we request an
# uncompressed body via accept-encoding: identity below.
DROP_HEADERS = frozenset(
    {
        "content-security-policy",
        "content-security-policy-report-only",
        "content-encoding",
        "content-length",
    }
)


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

    try:
        user_agent = await dep.page.evaluate("navigator.userAgent")
    except Exception:
        logger.warning("Could not determine User-Agent via page.evaluate")
        user_agent = None

    final_url = await setup_routes(request, dep)

    try:
        challenge_detected, page_html, page_request, status = (
            await _navigate_and_solve(dep, request, timer)
        )
    except (TimeoutError, PlaywrightTimeoutError) as e:
        logger.error("Timed out while loading the page or solving the challenge")
        raise HTTPException(
            status_code=408,
            detail="Timed out while loading the page or solving the challenge",
        ) from e

    cookies = await dep.context.cookies()
    content_type, response_content = await build_response_content(
        dep, request, page_request,
        challenge_detected=challenge_detected,
        page_html=page_html,
    )

    if user_agent is None:
        user_agent = page_request.request.headers.get("user-agent") if page_request else ""

    return LinkResponse(
        message="Success",
        solution=Solution(
            user_agent=user_agent,
            url=final_url if final_url is not None else dep.page.url,
            status=status,
            cookies=cookies,
            headers=page_request.headers if page_request else {},
            response=response_content,
            content_type=content_type,
        ),
        start_timestamp=start_time,
    )


async def setup_routes(request: LinkRequest, dep: BrowserDep) -> str | None:
    """
    Install request routes for media blocking and CSP stripping.

    Returns the final URL captured during navigation; callers read it after
    the page settles.
    """
    if request.block_media:

        async def block_media_route(route) -> None:
            if route.request.resource_type in ("image", "media", "font"):
                await route.abort()
            else:
                await route.continue_()

        await dep.page.route("**/*", block_media_route)

    final_url: str | None = None

    async def strip_csp_route(route) -> None:
        nonlocal final_url
        if route.request.resource_type != "document":
            await route.continue_()
            return
        # Request an uncompressed body via accept-encoding: identity. When
        # route.fulfill re-serves the fetched response (by uid), it forwards
        # the original compressed bytes; stripping content-encoding below
        # would leave the browser reading compressed bytes as plain text.
        response = await route.fetch(
            headers={**route.request.headers, "accept-encoding": "identity"}
        )
        if route.request.frame == dep.page.main_frame:
            final_url = response.url
        await route.fulfill(
            response=response,
            headers={
                key: value
                for key, value in response.headers.items()
                if key.lower() not in DROP_HEADERS
            },
        )

    await dep.page.route("**/*", strip_csp_route)
    return final_url


async def _navigate_and_solve(
    dep: BrowserDep,
    request: LinkRequest,
    timer: TimeoutTimer,
) -> tuple[bool, str | None, object, HTTPStatus]:
    """Navigate to the URL, then solve a challenge or wait for network idle."""
    page_html: str | None = None
    page_request = await dep.page.goto(
        request.url, timeout=timer.remaining() * 1000
    )
    status = page_request.status if page_request else HTTPStatus.OK
    await dep.page.wait_for_load_state(
        state="domcontentloaded", timeout=timer.remaining() * 1000
    )

    challenge_active = (
        await detect_cloudflare_challenge(dep.page, "interstitial")
        or await detect_cloudflare_challenge(dep.page, "turnstile")
    )
    if not challenge_active:
        page_html = await dep.page.content()
        await _wait_for_networkidle(dep, timer)
        return False, page_html, page_request, status

    await _solve_challenge(dep, timer)
    status = HTTPStatus.OK
    return True, page_html, page_request, status


async def _solve_challenge(dep: BrowserDep, timer: TimeoutTimer) -> None:
    """Attempt to solve a detected Cloudflare interstitial challenge."""
    logger.info("Challenge detected, attempting to solve...")
    await wait_for(
        dep.solver.solve_captcha(  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType]
            captcha_container=dep.page,
            captcha_type=CaptchaType.CLOUDFLARE_INTERSTITIAL,
            wait_checkbox_attempts=1,
            wait_checkbox_delay=0.5,
        ),
        timeout=timer.remaining(),
    )
    logger.debug("Challenge solved successfully.")


async def _wait_for_networkidle(dep: BrowserDep, timer: TimeoutTimer) -> None:
    """Wait for network idle, tolerating post-DOM-load stalls."""
    try:
        await dep.page.wait_for_load_state(
            "networkidle", timeout=timer.remaining() * 1000
        )
    except PlaywrightTimeoutError:
        logger.info(
            "networkidle timed out after domcontentloaded; "
            "continuing with loaded page"
        )


async def build_response_content(
    dep: BrowserDep,
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
        return await _fetch_pdf_content(dep)

    response_content = (
        page_html
        if page_html is not None and not challenge_detected
        else await dep.page.content()
    )
    return "text/html", response_content


async def _fetch_pdf_content(dep: BrowserDep) -> tuple[str, str]:
    """Fetch raw PDF bytes as base64, falling back to viewer HTML on failure."""
    try:
        fetch_response = await dep.page.request.fetch(dep.page.url)
        response_content = base64.b64encode(
            await fetch_response.body()
        ).decode("ascii")
    except Exception:
        logger.exception("Failed to fetch PDF bytes, falling back to viewer HTML")
        return "text/html", await dep.page.content()
    return "application/pdf", response_content

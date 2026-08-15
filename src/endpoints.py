import base64
import time
import warnings
from asyncio import sleep, wait_for
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright_captcha import CaptchaType
from playwright_captcha.solvers.click.cloudflare.utils.detection import (
    detect_cloudflare_challenge,
)
from playwright_captcha.utils.exceptions import (
    CaptchaDetectionError,
    CaptchaSolvingError,
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

# Markup only an unsolved challenge has. Two near misses to avoid:
#
#   script[src*="/cdn-cgi/challenge-platform/"] on its own also matches the jsd
#   bot-scoring beacon Cloudflare serves from that path on ordinary pages, so it
#   has to be narrowed to the challenge orchestrator (chl_page).
#
#   iframe[src*="challenges.cloudflare.com"] looks like the widget but outlives
#   it: a cleared nowsecure.nl carries two of them with no challenge in sight.
CHALLENGE_MARKERS = (
    'script[src*="/cdn-cgi/challenge-platform/"][src*="chl_page"], '
    "#challenge-error-text, #challenge-running, #challenge-stage"
)

# How long to let Cloudflare verify a click before trying again, and how often
# to look. Verification took 5-15s in testing.
CHALLENGE_SETTLE_SECONDS = 20.0
CHALLENGE_POLL_SECONDS = 1.0


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
        challenge_detected, page_html, page_request, status = await _navigate_and_solve(
            dep, request, timer
        )
    except (TimeoutError, PlaywrightTimeoutError) as e:
        logger.error("Timed out while loading the page or solving the challenge")
        raise HTTPException(
            status_code=408,
            detail="Timed out while loading the page or solving the challenge",
        ) from e

    cookies = await dep.context.cookies()
    content_type, response_content = await build_response_content(
        dep,
        request,
        page_request,
        challenge_detected=challenge_detected,
        page_html=page_html,
    )

    user_agent = page_request.request.headers.get("user-agent") if page_request else ""

    return LinkResponse(
        message="Success",
        solution=Solution(
            user_agent=user_agent,
            url=dep.page.url,
            status=status,
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
) -> tuple[bool, str | None, object, HTTPStatus]:
    """Navigate to the URL, then solve a challenge or wait for network idle."""
    page_html: str | None = None
    page_request = await dep.page.goto(request.url, timeout=timer.remaining() * 1000)
    status = page_request.status if page_request else HTTPStatus.OK
    await dep.page.wait_for_load_state(
        state="domcontentloaded", timeout=timer.remaining() * 1000
    )

    challenge_active = await detect_cloudflare_challenge(
        dep.page, "interstitial"
    ) or await detect_cloudflare_challenge(dep.page, "turnstile")
    if not challenge_active:
        page_html = await dep.page.content()
        await _wait_for_networkidle(dep, timer)
        return False, page_html, page_request, status

    await _solve_challenge(dep, timer)
    status = HTTPStatus.OK
    return True, page_html, page_request, status


async def _solve_challenge(dep: BrowserDep, timer: TimeoutTimer) -> None:
    """
    Attempt to solve a detected Cloudflare interstitial challenge.

    The solver's own verdict is not trusted. It judges its click by waiting for
    networkidle, which returns the moment the network happens to be quiet --
    measured at 9ms after the click -- and then reports "challenge still
    present". Cloudflare needs seconds: it replaces the checkbox with
    "verifying you are human" before the page turns over. So try, then wait for
    the challenge itself to go away, and only give up once the budget is gone.

    That bounds what used to be unbounded. With max_attempts at sys.maxsize the
    solver retried an unreachable widget ~1300 times per request and the caller
    waited out the whole max_timeout for a 408 it was always going to get.
    """
    logger.info("Challenge detected, attempting to solve...")
    while timer.remaining() > 0:
        try:
            await wait_for(
                dep.solver.solve_captcha(  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType]
                    captcha_container=dep.page,
                    captcha_type=CaptchaType.CLOUDFLARE_INTERSTITIAL,
                    wait_checkbox_attempts=1,
                    wait_checkbox_delay=0.5,
                ),
                timeout=timer.remaining(),
            )
        except (CaptchaDetectionError, CaptchaSolvingError) as e:
            # Both mean "not solved yet", not "cannot be solved": the widget is
            # mid-verification and momentarily absent, or the click has landed
            # and the verdict was taken too early.
            logger.debug(f"Solver attempt inconclusive: {e}")

        if await _challenge_cleared(dep, timer):
            logger.info("Challenge cleared")
            return

    message = "Challenge still present when the request budget ran out"
    raise TimeoutError(message)


async def _challenge_cleared(dep: BrowserDep, timer: TimeoutTimer) -> bool:
    """
    Wait out Cloudflare's post-click verification, up to CHALLENGE_SETTLE_SECONDS.

    Polls rather than waiting for a load event: Cloudflare swaps the widget for
    a spinner in place and only navigates once it is satisfied, so there is no
    single event to await.
    """
    deadline = min(CHALLENGE_SETTLE_SECONDS, timer.remaining())
    waited = 0.0
    while waited < deadline:
        if not await _challenge_visible(dep.page):
            return True
        await sleep(CHALLENGE_POLL_SECONDS)
        waited += CHALLENGE_POLL_SECONDS
    return not await _challenge_visible(dep.page)


async def _challenge_visible(page: Page) -> bool:
    """
    Report whether an unsolved challenge is still on the page.

    Cloudflare serves two different scripts from /cdn-cgi/challenge-platform/:
    the challenge orchestrator on an interstitial, and the jsd bot-scoring
    beacon on ordinary pages once a visitor is cleared. detect_cloudflare_
    challenge() matches both, so on its own it never reports success. Match the
    orchestrator and the widget instead.
    """
    try:
        return await page.locator(CHALLENGE_MARKERS).count() > 0
    except Exception:
        # A navigation tore down the execution context mid-check, which only
        # happens once Cloudflare has moved us on.
        logger.debug("Challenge lookup interrupted by a navigation")
        return False


async def _wait_for_networkidle(dep: BrowserDep, timer: TimeoutTimer) -> None:
    """Wait for network idle, tolerating post-DOM-load stalls."""
    try:
        await dep.page.wait_for_load_state(
            "networkidle", timeout=timer.remaining() * 1000
        )
    except PlaywrightTimeoutError:
        logger.info(
            "networkidle timed out after domcontentloaded; continuing with loaded page"
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
        response_content = base64.b64encode(await fetch_response.body()).decode("ascii")
    except Exception:
        logger.exception("Failed to fetch PDF bytes, falling back to viewer HTML")
        return "text/html", await dep.page.content()
    return "application/pdf", response_content

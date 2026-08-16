import base64
import time
import warnings
from asyncio import sleep
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
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

# The widget lives in an iframe served from here; the checkbox is an invisible
# input inside it, so it is pressed by position rather than by locator. 30px in
# from the widget's left edge is the middle of the box Cloudflare draws.
CF_WIDGET_HOST = "challenges.cloudflare.com"
CHECKBOX_SELECTOR = 'input[type="checkbox"]'
CHECKBOX_OFFSET_X = 30

# How often to look, and how long to leave a press alone before trying again.
# Verification takes 5-15s, and pressing over the top of it just restarts the
# cycle.
CHALLENGE_POLL_SECONDS = 1.0
PRESS_INTERVAL_SECONDS = 12.0


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

    Handles both shapes Cloudflare serves: the non-interactive challenge, which
    clears itself given a few seconds, and the interactive one, which needs the
    checkbox pressed. Both are covered by the same loop -- watch for the
    challenge markup to disappear, and press whenever a checkbox is on offer.

    playwright-captcha's solver is deliberately not used here. It clicks the
    checkbox input directly, and that input is invisible, so the click reports
    success while `checked` never flips. It also judges the result by waiting
    for networkidle, which returned 9ms after the click while Cloudflare was
    still verifying, so it reported failure on challenges that were about to
    pass.
    """
    logger.info("Challenge detected, attempting to solve...")
    last_press = -PRESS_INTERVAL_SECONDS
    while timer.remaining() > 0:
        if not await _challenge_visible(dep.page):
            logger.info("Challenge cleared")
            return

        elapsed = timer.duration - timer.remaining()
        if elapsed - last_press >= PRESS_INTERVAL_SECONDS and await _press_checkbox(
            dep.page
        ):
            last_press = elapsed

        await sleep(CHALLENGE_POLL_SECONDS)

    message = "Challenge still present when the request budget ran out"
    raise TimeoutError(message)


def _cloudflare_frame(page: Page) -> object | None:
    """Find the turnstile widget's frame; None while Cloudflare is between states."""
    for frame in page.frames:
        if CF_WIDGET_HOST in frame.url and not frame.is_detached():
            return frame
    return None


async def _press_checkbox(page: Page) -> bool:
    """
    Press the checkbox, if one is currently on offer. True when a press happened.

    Two things make this harder than locator.click():

    Cloudflare cycles between "checking if you are human", where the widget
    frame holds no input at all, and the state where the checkbox is offered.
    Pressing during the first phase clicks nothing, so wait for the input to
    exist before reaching for the mouse.

    And the input is invisible -- it sits under a styled overlay. Playwright
    reports a successful click on it and `checked` never flips, which is why
    playwright-captcha's own click has never solved one of these. Pressing the
    widget's visible pixels does work: measured against ext.to, this clears the
    challenge and returns a cf_clearance cookie.
    """
    frame = _cloudflare_frame(page)
    if frame is None:
        return False
    try:
        checkbox = frame.locator(CHECKBOX_SELECTOR)
        if not await checkbox.count():
            return False
        if await checkbox.first.is_checked():
            # A press has already landed and Cloudflare is verifying it.
            # Pressing over the top restarts that verification, which is how
            # ext.to and speed.cd sat on "performing security verification" for
            # a full 300s budget while being pressed a dozen times.
            return False
        element = await frame.frame_element()
        box = await element.bounding_box()
    except Exception:
        # The widget is mid-swap; try again on the next poll.
        return False
    if not box:
        return False

    x = box["x"] + CHECKBOX_OFFSET_X
    y = box["y"] + box["height"] / 2
    try:
        # Approach before pressing: a cursor that teleports onto the target is
        # itself a signal.
        await page.mouse.move(x - 180, y - 120)
        await sleep(0.3)
        await page.mouse.move(x - 45, y - 20, steps=18)
        await sleep(0.2)
        await page.mouse.move(x, y, steps=10)
        await sleep(0.35)
        await page.mouse.down()
        await sleep(0.08)
        await page.mouse.up()
    except Exception as exc:
        logger.debug(f"Checkbox press failed: {exc}")
        return False
    logger.info(f"Pressed the Cloudflare checkbox at ({x:.0f}, {y:.0f}) in {box}")
    return True


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

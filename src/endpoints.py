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

# Markup only an unsolved challenge has. chl_page is required: the bare
# challenge-platform path also matches the jsd beacon served on cleared pages,
# and the widget iframe outlives the challenge (a cleared nowsecure.nl has two).
CHALLENGE_MARKERS = (
    'script[src*="/cdn-cgi/challenge-platform/"][src*="chl_page"], '
    "#challenge-error-text, #challenge-running, #challenge-stage"
)

# 30px in from the widget's left edge is the middle of the box Cloudflare draws.
CF_WIDGET_HOST = "challenges.cloudflare.com"
CHECKBOX_SELECTOR = 'input[type="checkbox"]'
CHECKBOX_OFFSET_X = 30

# Verification takes 5-15s; pressing over the top of it restarts the cycle.
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
    Clear a Cloudflare challenge, whether or not it needs the checkbox pressed.

    playwright-captcha's solver is not used: it clicks the invisible input, so
    the click reports success while `checked` never flips, and it judges the
    result on networkidle, which returns while Cloudflare is still verifying.
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
    Press the widget's visible pixels. True when a press actually happened.

    Cloudflare cycles through a state where the frame holds no input, and an
    already-checked box means a press is being verified -- pressing again
    restarts that. The point comes from the iframe, not the input, because the
    input is invisible beneath a styled overlay.
    """
    frame = _cloudflare_frame(page)
    if frame is None:
        return False
    try:
        checkbox = frame.locator(CHECKBOX_SELECTOR)
        if not await checkbox.count() or await checkbox.first.is_checked():
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
        # A cursor that teleports onto the target is itself a signal.
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
    logger.info(f"Pressed the Cloudflare checkbox at ({x:.0f}, {y:.0f})")
    return True


async def _challenge_visible(page: Page) -> bool:
    """
    Report whether an unsolved challenge is still on the page.

    detect_cloudflare_challenge() matches the jsd beacon served on cleared pages
    too, so on its own it never reports success.
    """
    try:
        return await page.locator(CHALLENGE_MARKERS).count() > 0
    except Exception:
        # A navigation tore down the context mid-check; that only happens once
        # Cloudflare has moved us on.
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

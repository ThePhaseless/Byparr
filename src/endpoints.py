import time
import warnings
from asyncio import wait_for
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from playwright.async_api import Error as PlaywrightError, Page
from playwright_captcha import CaptchaType
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_fixed,
)

from src.consts import CHALLENGE_TITLES
from src.models import (
    HealthcheckResponse,
    LinkRequest,
    LinkResponse,
    Solution,
)
from src.utils import CamoufoxDepClass, TimeoutTimer, get_camoufox, logger

warnings.filterwarnings("ignore", category=SyntaxWarning)


router = APIRouter()

CamoufoxDep = Annotated[CamoufoxDepClass, Depends(get_camoufox)]


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


def _is_page_crash(exception: BaseException) -> bool:
    """Check if exception is a page crash error."""
    return isinstance(exception, PlaywrightError) and "Page crashed" in str(exception)


@router.post("/v1")
async def read_item(request: LinkRequest, dep: CamoufoxDep) -> LinkResponse:
    """Handle POST requests."""
    start_time = int(time.time() * 1000)

    timer = TimeoutTimer(duration=request.max_timeout)

    request.url = request.url.replace('"', "").strip()

    # Use a container to hold the current page so we can update it during retries
    page_container: list[Page] = [dep.page]
    page_request = None
    status = HTTPStatus.OK

    async def _navigate_and_solve() -> None:
        """Navigate to URL and solve challenges if present."""
        nonlocal page_request, status

        current_page = page_container[0]

        page_request = await current_page.goto(
            request.url, timeout=timer.remaining() * 1000
        )
        status = page_request.status if page_request else HTTPStatus.OK
        await current_page.wait_for_load_state(
            state="domcontentloaded", timeout=timer.remaining() * 1000
        )
        await current_page.wait_for_load_state(
            "networkidle", timeout=timer.remaining() * 1000
        )

        if await current_page.title() in CHALLENGE_TITLES:
            logger.info("Challenge detected, attempting to solve...")
            # Solve the captcha
            await wait_for(
                dep.solver.solve_captcha(  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType]
                    captcha_container=current_page,
                    captcha_type=CaptchaType.CLOUDFLARE_INTERSTITIAL,
                    wait_checkbox_attempts=1,
                    wait_checkbox_delay=0.5,
                ),
                timeout=timer.remaining(),
            )
            status = HTTPStatus.OK
            logger.debug("Challenge solved successfully.")

    # Use tenacity for retry logic with page crash handling
    try:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception(_is_page_crash),
            stop=stop_after_attempt(2),
            wait=wait_fixed(0.5),
            reraise=True,
        ):
            with attempt:
                try:
                    await _navigate_and_solve()
                except PlaywrightError as e:
                    if _is_page_crash(e):
                        logger.warning(f"Page crashed on attempt {attempt.retry_state.attempt_number}, recreating page and retrying...")
                        try:
                            # Close the crashed page
                            await page_container[0].close()
                        except Exception as close_error:
                            logger.debug(f"Error closing crashed page: {close_error}")

                        # Create a new page from the existing context
                        page_container[0] = await dep.context.new_page()
                    raise  # Re-raise to trigger retry or final failure
    except PlaywrightError as e:
        logger.error(f"Playwright error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Browser error: {str(e)}",
        ) from e
    except TimeoutError as e:
        logger.error("Timed out while solving the challenge")
        raise HTTPException(
            status_code=408,
            detail="Timed out while solving the challenge",
        ) from e

    cookies = await dep.context.cookies()
    current_page = page_container[0]

    return LinkResponse(
        message="Success",
        solution=Solution(
            user_agent=await current_page.evaluate("navigator.userAgent"),
            url=current_page.url,
            status=status,
            cookies=cookies,
            headers=page_request.headers if page_request else {},
            response=await current_page.content(),
        ),
        start_timestamp=start_time,
    )

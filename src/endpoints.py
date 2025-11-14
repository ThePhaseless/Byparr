import time
import warnings
from asyncio import wait_for
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from playwright.async_api import Error as PlaywrightError
from playwright_captcha import CaptchaType

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


@router.post("/v1")
async def read_item(request: LinkRequest, dep: CamoufoxDep) -> LinkResponse:
    """Handle POST requests."""
    start_time = int(time.time() * 1000)

    timer = TimeoutTimer(duration=request.max_timeout)

    request.url = request.url.replace('"', "").strip()

    # Track retry attempts for page crashes
    max_retries = 2
    current_page = dep.page
    page_request = None
    status = HTTPStatus.OK

    for attempt in range(max_retries):
        try:
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
            break  # Success, exit retry loop
        except PlaywrightError as e:
            if "Page crashed" in str(e) and attempt < max_retries - 1:
                logger.warning(f"Page crashed on attempt {attempt + 1}, recreating page and retrying...")
                try:
                    # Close the crashed page
                    await current_page.close()
                except Exception as close_error:
                    logger.debug(f"Error closing crashed page: {close_error}")

                # Create a new page from the existing context
                current_page = await dep.context.new_page()
                continue  # Retry with the new page
            else:
                # Either not a page crash or out of retries
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

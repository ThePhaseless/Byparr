import base64
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
async def health_check():
    """
    Lightweight liveness check.

    Returns immediately so docker healthchecks are not held hostage by upstream
    network latency. Use ``--init`` to exercise the full Camoufox stack at
    startup.
    """
    return HealthcheckResponse()


async def deep_health_check(sb: CamoufoxDep) -> HealthcheckResponse:
    """Exercise the bypass stack against google.com. Used by ``--init``."""
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
    try:
        page_request = await dep.page.goto(
            request.url, timeout=timer.remaining() * 1000
        )
        status = page_request.status if page_request else HTTPStatus.OK
        await dep.page.wait_for_load_state(
            state="domcontentloaded", timeout=timer.remaining() * 1000
        )
        await dep.page.wait_for_load_state(
            "networkidle", timeout=timer.remaining() * 1000
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
    except TimeoutError as e:
        logger.error("Timed out while solving the challenge")
        raise HTTPException(
            status_code=408,
            detail="Timed out while solving the challenge",
        ) from e
    except PlaywrightError as e:
        logger.error("Upstream navigation failed: %s", e)
        raise HTTPException(
            status_code=502,
            detail=str(e),
        ) from e

    cookies = await dep.context.cookies()

    headers = page_request.headers if page_request else {}
    raw_content_type = (headers.get("content-type") or "").lower()
    # Firefox renders PDFs in its built-in viewer, so page.content() would
    # return the viewer's HTML chrome instead of the PDF. Re-fetch via the
    # context's API client (which inherits cookies/UA) and return bytes.
    if "application/pdf" in raw_content_type:
        api_resp = await dep.context.request.get(dep.page.url)
        body_bytes = await api_resp.body()
        response_body = base64.b64encode(body_bytes).decode("ascii")
        response_content_type = "application/pdf"
    else:
        response_body = await dep.page.content()
        response_content_type = "text/html"

    return LinkResponse(
        message="Success",
        solution=Solution(
            user_agent=await dep.page.evaluate("navigator.userAgent"),
            url=dep.page.url,
            status=status,
            cookies=cookies,
            headers=headers,
            response=response_body,
            content_type=response_content_type,
        ),
        start_timestamp=start_time,
    )

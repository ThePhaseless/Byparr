import base64
import time
import warnings
from asyncio import wait_for
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from playwright_captcha import CaptchaType

from src.consts import CHALLENGE_TITLES
from src.models import (
    HealthcheckResponse,
    LinkRequest,
    LinkResponse,
    Solution,
)
from src.utils import CamoufoxDepClass, TimeoutTimer, get_camoufox, logger

BINARY_CONTENT_TYPES = (
    "application/pdf", "application/zip", "application/gzip",
    "application/octet-stream", "application/x-tar",
    "image/", "audio/", "video/", "font/",
)

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


def _is_binary_content_type(ct: str) -> bool:
    """Check if content-type indicates binary content."""
    ct_lower = ct.lower()
    return any(ct_lower.startswith(b) for b in BINARY_CONTENT_TYPES)


@router.post("/v1")
async def read_item(request: LinkRequest, dep: CamoufoxDep) -> LinkResponse:
    """Handle POST requests."""
    start_time = int(time.time() * 1000)

    timer = TimeoutTimer(duration=request.max_timeout)

    request.url = request.url.replace('"', "").strip()

    # Capture binary responses (PDF, images, etc.) at network level.
    # After challenge solving, the browser may navigate to binary content
    # (e.g. PDF). page_request only reflects the initial response (challenge
    # page), not the final content. Intercept via response event instead.
    # Only capture responses matching the requested URL (ignore fonts,
    # images, and other sub-resources).
    captured_binary: bytes | None = None
    target_url = request.url.split("?")[0].split("#")[0]

    async def _capture_binary_response(response):
        nonlocal captured_binary
        resp_url = response.url.split("?")[0].split("#")[0]
        if resp_url != target_url:
            return
        ct = response.headers.get("content-type", "")
        if _is_binary_content_type(ct):
            try:
                captured_binary = await response.body()
                logger.info(f"Captured binary response: {ct} ({len(captured_binary)} bytes)")
            except Exception as e:
                logger.warning(f"Failed to capture binary body: {e}")

    dep.page.on("response", _capture_binary_response)

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

        dep.page.remove_listener("response", _capture_binary_response)
    except TimeoutError as e:
        logger.error("Timed out while solving the challenge")
        raise HTTPException(
            status_code=408,
            detail="Timed out while solving the challenge",
        ) from e

    cookies = await dep.context.cookies()

    # Binary content: use captured response if available
    response_body = ""
    response_type = "text"
    if captured_binary is not None:
        response_body = base64.b64encode(captured_binary).decode("ascii")
        response_type = "base64"
    else:
        response_body = await dep.page.content()

    return LinkResponse(
        message="Success",
        solution=Solution(
            user_agent=await dep.page.evaluate("navigator.userAgent"),
            url=dep.page.url,
            status=status,
            cookies=cookies,
            headers=page_request.headers if page_request else {},
            response=response_body,
            response_type=response_type,
        ),
        start_timestamp=start_time,
    )

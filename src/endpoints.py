from __future__ import annotations

import time
import warnings
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from fastapi.responses import RedirectResponse
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

try:
    from invisible_playwright._pw.async_api import (
        Error as IPPlaywrightError,
        TimeoutError as IPPlaywrightTimeoutError,
    )
except ImportError:
    IPPlaywrightError = None  # type: ignore[assignment,misc]
    IPPlaywrightTimeoutError = None  # type: ignore[assignment,misc]

from src.browser_manager import BrowserDepClass, browser_manager, get_browser
from src.challenge import challenge_present, solve_challenge
from src.concurrency_advisor import concurrency_advisor
from src.consts import AUTO_SYNC_CONCURRENCY, MAX_CONCURRENCY
from src.content import build_response_content
from src.models import (
    ConcurrencyConfigRequest,
    ConcurrencyConfigResponse,
    HealthcheckResponse,
    LinkRequest,
    LinkResponse,
    Solution,
)
from src.protocol_fallback import protocol_fallback_manager
from src.utils import (
    TimeoutTimer,
    logger,
    remaining_ms,
)

warnings.filterwarnings("ignore", category=SyntaxWarning)

router = APIRouter()

BrowserDep = Annotated[BrowserDepClass, Depends(get_browser)]

TIMEOUT_EXCEPTIONS = tuple(
    exc for exc in (PlaywrightTimeoutError, IPPlaywrightTimeoutError) if exc is not None
)
PLAYWRIGHT_EXCEPTIONS = tuple(
    exc for exc in (PlaywrightError, IPPlaywrightError) if exc is not None
)


@router.get("/")
def index() -> RedirectResponse:
    """Redirect to swagger docs."""
    logger.debug("Redirecting to /docs")
    return RedirectResponse(url="/docs", status_code=301)


@router.get("/config")
async def get_config() -> ConcurrencyConfigResponse:
    """Returns current concurrency configuration and estimated memory footprint."""
    current_limit = browser_manager.max_concurrency
    return ConcurrencyConfigResponse(
        max_concurrency=current_limit,
        estimated_memory_mb=concurrency_advisor.get_memory_estimate_mb(current_limit),
        memory_warning=concurrency_advisor.generate_memory_warning(current_limit),
        auto_sync=AUTO_SYNC_CONCURRENCY,
    )


@router.post("/config")
async def set_config(config: ConcurrencyConfigRequest) -> ConcurrencyConfigResponse:
    """Updates maximum concurrency dynamically at runtime."""
    new_limit = browser_manager.update_concurrency(config.max_concurrency)
    concurrency_advisor.byparr_concurrency = new_limit
    return ConcurrencyConfigResponse(
        max_concurrency=new_limit,
        estimated_memory_mb=concurrency_advisor.get_memory_estimate_mb(new_limit),
        memory_warning=concurrency_advisor.generate_memory_warning(new_limit),
        auto_sync=AUTO_SYNC_CONCURRENCY,
    )


@router.get("/health")
async def health_check(sb: BrowserDep):
    """Health check endpoint with concurrency and memory estimates."""
    health_check_request = await read_item(
        LinkRequest.model_construct(url="https://google.com"),
        sb,
    )

    if health_check_request.solution.status != HTTPStatus.OK:
        raise HTTPException(
            status_code=500,
            detail="Health check failed",
        )

    current_concurrency = browser_manager.max_concurrency
    mem_warning = concurrency_advisor.generate_memory_warning(current_concurrency)

    return HealthcheckResponse(
        user_agent=health_check_request.solution.user_agent,
        max_concurrency=current_concurrency,
        estimated_memory_mb=concurrency_advisor.get_memory_estimate_mb(current_concurrency),
        memory_warning=mem_warning,
    )


@router.post("/v1")
async def read_item(
    request: LinkRequest,
    dep: BrowserDep,
    response: Response = Response(),
    x_jackett_concurrency: Annotated[
        int | None,
        Header(
            alias="X-Jackett-Concurrency",
            description="Concurrency limit configured in Jackett client.",
        ),
    ] = None,
    x_proxy_server: Annotated[str | None, Header(alias="X-Proxy-Server")] = None,
    x_proxy_username: Annotated[str | None, Header(alias="X-Proxy-Username")] = None,
    x_proxy_password: Annotated[str | None, Header(alias="X-Proxy-Password")] = None,
) -> LinkResponse:
    """Handle POST requests with automatic HTTP/3 -> HTTP/2 fallback and concurrency checks."""
    start_time = int(time.time() * 1000)
    timer = TimeoutTimer(duration=request.max_timeout)
    request.url = request.url.replace('"', "").strip()

    # Auto-Sync: automatically adjust Byparr concurrency if requested by Jackett
    if AUTO_SYNC_CONCURRENCY and x_jackett_concurrency is not None:
        if 1 <= x_jackett_concurrency <= 64 and x_jackett_concurrency != browser_manager.max_concurrency:
            browser_manager.update_concurrency(x_jackett_concurrency)
            concurrency_advisor.byparr_concurrency = x_jackett_concurrency
            logger.info(
                "Auto-Sync: Concurrency dynamically synchronized to %d sessions matching Jackett.",
                x_jackett_concurrency,
            )

    # Evaluate concurrency divergence between Jackett and Byparr
    effective_limit, divergence_msg = concurrency_advisor.evaluate_divergence(
        x_jackett_concurrency
    )
    if divergence_msg:
        logger.info("[Concurrency Check] %s", divergence_msg)

    current_limit = browser_manager.max_concurrency
    if response is not None:
        response.headers["X-Byparr-Concurrency"] = str(current_limit)
        response.headers["X-Byparr-Memory-Estimate-MB"] = str(
            concurrency_advisor.get_memory_estimate_mb(current_limit)
        )
        if divergence_msg:
            response.headers["X-Concurrency-Divergence"] = divergence_msg

    # Check if domain was previously recorded as requiring HTTP/2 fallback
    if protocol_fallback_manager.requires_http2_fallback(request.url) and dep.http3_enabled:
        logger.info(
            "Host for %s is registered for HTTP/2 fallback. Acquiring HTTP/2 session directly...",
            request.url,
        )
        async for fallback_dep in browser_manager.acquire_browser(
            header_server=x_proxy_server,
            header_username=x_proxy_username,
            header_password=x_proxy_password,
            disable_http3=True,
        ):
            return await _execute_request_flow(
                request, fallback_dep, timer, start_time, divergence_msg, effective_limit
            )

    try:
        return await _execute_request_flow(
            request, dep, timer, start_time, divergence_msg, effective_limit
        )
    except PLAYWRIGHT_EXCEPTIONS as e:
        # Check for HTTP/3 protocol failure and attempt immediate fallback to HTTP/2
        if protocol_fallback_manager.is_http3_error(e):
            host = protocol_fallback_manager.record_http3_failure(request.url)
            logger.warning(
                "HTTP/3 error '%s' on %s. Retrying seamlessly with HTTP/2 fallback...",
                e,
                host,
            )
            async for fallback_dep in browser_manager.acquire_browser(
                header_server=x_proxy_server,
                header_username=x_proxy_username,
                header_password=x_proxy_password,
                disable_http3=True,
            ):
                return await _execute_request_flow(
                    request,
                    fallback_dep,
                    timer,
                    start_time,
                    divergence_msg,
                    effective_limit,
                )

        logger.error("Could not reach the target: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach the target: {e}",
        ) from e


async def _execute_request_flow(
    request: LinkRequest,
    dep: BrowserDepClass,
    timer: TimeoutTimer,
    start_time: int,
    divergence_msg: str | None = None,
    effective_limit: int = MAX_CONCURRENCY,
) -> LinkResponse:
    """Internal helper to set up routes, solve challenges, and construct LinkResponse."""
    await setup_routes(request, dep)

    try:
        challenge_detected, page_html, page_request = await _navigate_and_solve(
            dep, request, timer
        )
    except TIMEOUT_EXCEPTIONS as e:
        logger.error("Timed out while loading the page or solving the challenge: %s", e)
        raise HTTPException(
            status_code=408,
            detail="Timed out while loading the page or solving the challenge",
        ) from e
    except Exception as e:
        if protocol_fallback_manager.is_http3_error(e):
            raise
        logger.error("Error navigating to target: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach the target: {e}",
        ) from e

    cookies = await dep.context.cookies()
    headers = await page_request.all_headers() if page_request else {}
    content_type, response_content = await build_response_content(
        dep.page,
        request,
        page_request,
        challenge_detected=challenge_detected,
        page_html=page_html,
    )

    return LinkResponse(
        solution=Solution(
            url=dep.page.url,
            status=page_request.status if page_request else 200,
            cookies=cookies,
            user_agent=await dep.page.evaluate("navigator.userAgent"),
            headers=headers,
            response=response_content,
        ),
        start_timestamp=start_time,
        concurrency_limit=effective_limit,
        concurrency_warning=divergence_msg,
    )


async def setup_routes(request: LinkRequest, dep: BrowserDepClass) -> None:
    """Install request routes for media blocking."""
    if request.block_media:

        async def block_media_route(route):
            if route.request.resource_type in ("image", "media", "font"):
                await route.abort()
            else:
                await route.continue_()

        await dep.page.route("**/*", block_media_route)


async def _navigate_and_solve(
    dep: BrowserDepClass,
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


async def _wait_for_networkidle(dep: BrowserDepClass, timer: TimeoutTimer) -> None:
    """Wait for network idle, tolerating post-DOM-load stalls."""
    try:
        await dep.page.wait_for_load_state("networkidle", timeout=remaining_ms(timer))
    except TIMEOUT_EXCEPTIONS:
        logger.info(
            "Network idle not reached within timeout, continuing with current page state."
        )

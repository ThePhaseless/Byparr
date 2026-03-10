import contextlib
import time
import warnings
from asyncio import wait_for
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from playwright.async_api import Page, Response
from playwright_captcha import CaptchaType, ClickSolver

from src.consts import CHALLENGE_TITLES
from src.models import (
    HealthcheckResponse,
    InteractAction,
    LinkRequest,
    LinkResponse,
    Solution,
)
from src.utils import CamoufoxDepClass, TimeoutTimer, get_camoufox, logger

# Truncation limits for logging and error responses
LOG_JS_RESULT_MAX = 200  # JS evaluation result in log output
LOG_JS_CODE_MAX = 80  # JS code snippet in debug log
ERROR_MESSAGE_MAX = 500  # error message returned to client in JSON response

warnings.filterwarnings("ignore", category=SyntaxWarning)


router = APIRouter()

CamoufoxDep = Annotated[CamoufoxDepClass, Depends(get_camoufox)]


@router.get("/", include_in_schema=False)
def read_root() -> RedirectResponse:
    """Redirect to /docs."""
    logger.debug("Redirecting to /docs")
    return RedirectResponse(url="/docs", status_code=301)


@router.get("/health")
async def health_check(sb: CamoufoxDep) -> HealthcheckResponse:
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


async def _navigate_and_wait(
    page: Page, url: str, timer: TimeoutTimer,
) -> tuple[Response | None, int]:
    """Navigate to URL and wait for page load states."""
    page_request = await page.goto(url, timeout=timer.remaining() * 1000)
    status = page_request.status if page_request else HTTPStatus.OK
    await page.wait_for_load_state(
        state="domcontentloaded", timeout=timer.remaining() * 1000
    )
    with contextlib.suppress(TimeoutError):
        await page.wait_for_load_state(
            "networkidle", timeout=timer.remaining() * 1000
        )
    return page_request, status


async def _solve_challenge_if_needed(
    page: Page, solver: ClickSolver, timer: TimeoutTimer,
) -> bool:
    """Detect and solve Cloudflare challenge if present."""
    if await page.title() in CHALLENGE_TITLES:
        logger.info("Challenge detected, attempting to solve...")
        await wait_for(
            solver.solve_captcha(
                captcha_container=page,
                captcha_type=CaptchaType.CLOUDFLARE_INTERSTITIAL,
                wait_checkbox_attempts=1,
                wait_checkbox_delay=0.5,
            ),
            timeout=timer.remaining(),
        )
        logger.debug("Challenge solved successfully.")
        return True
    return False


async def _execute_input_action(
    act: InteractAction, page: Page, timeout_ms: int,
) -> bool:
    """Execute input-type actions (fill, click, type, wait, wait_url)."""
    match act.action:
        case "fill":
            if act.selector and act.value is not None:
                await page.fill(act.selector, act.value, timeout=timeout_ms)
        case "click":
            if act.selector:
                await page.click(act.selector, timeout=timeout_ms)
        case "type":
            if act.value is not None:
                await page.keyboard.type(act.value)
        case "wait":
            return await _action_wait(act, page, timeout_ms)
        case "wait_url":
            return await _action_wait_url(act, page, timeout_ms)
    return True


async def _execute_action(
    act: InteractAction, page: Page, solver: ClickSolver, timer: TimeoutTimer,
) -> bool:
    """Execute a single browser action. Returns False to break the action loop."""
    t = min(act.timeout, int(timer.remaining() * 1000))
    match act.action:
        case "fill" | "click" | "type" | "wait" | "wait_url":
            return await _execute_input_action(act, page, t)
        case "solve_turnstile":
            await _action_solve_turnstile(page, solver, t, timer)
        case "sleep":
            await page.wait_for_timeout(t)
        case "js":
            if act.value:
                js_result = await page.evaluate(act.value)
                if js_result and str(js_result) != "None":
                    logger.info(f"JS result: {str(js_result)[:LOG_JS_RESULT_MAX]}")
                else:
                    logger.debug(f"JS executed: {act.value[:LOG_JS_CODE_MAX]}")
        case "screenshot":
            path = act.value or "/tmp/screenshot.png"  # noqa: S108
            await page.screenshot(path=path, full_page=True)
            logger.info(f"Screenshot saved to {path}")
        case _:
            logger.warning(f"Unknown or incomplete action: {act.action}")
    return True


async def _action_wait(act: InteractAction, page: Page, timeout_ms: int) -> bool:
    """Handle 'wait' action."""
    if not act.selector:
        return True
    try:
        await page.wait_for_selector(act.selector, timeout=timeout_ms)
    except TimeoutError as e:
        logger.warning(f"wait for '{act.selector}' failed: {e}")
        return False
    return True


async def _action_wait_url(act: InteractAction, page: Page, timeout_ms: int) -> bool:
    """Handle 'wait_url' action."""
    if not act.value:
        return True
    try:
        await page.wait_for_url(act.value, timeout=timeout_ms)
    except TimeoutError:
        logger.info(f"wait_url '{act.value}' timed out, URL unchanged")
        return False
    return True


async def _action_solve_turnstile(
    page: Page, solver: ClickSolver, timeout_ms: int, timer: TimeoutTimer,
) -> None:
    """Handle 'solve_turnstile' action."""
    logger.info("Solving Cloudflare Turnstile...")
    try:
        await wait_for(
            solver.solve_captcha(
                captcha_container=page,
                captcha_type=CaptchaType.CLOUDFLARE_TURNSTILE,
            ),
            timeout=min(timeout_ms / 1000, timer.remaining()),
        )
        logger.info("Turnstile solved via solver.")
        with contextlib.suppress(TimeoutError):
            await page.wait_for_load_state(
                "networkidle", timeout=timer.remaining() * 1000
            )
    except TimeoutError as e:
        logger.warning(f"Turnstile solver failed: {e}")


async def _handle_interact(
    request: LinkRequest, dep: CamoufoxDepClass, timer: TimeoutTimer, start_time: int,
) -> LinkResponse:
    """Handle request.interact command."""
    _, status = await _navigate_and_wait(dep.page, request.url, timer)

    await _solve_challenge_if_needed(dep.page, dep.solver, timer)

    for act in request.actions:
        if not await _execute_action(act, dep.page, dep.solver, timer):
            break

    # Wait for network to settle after actions
    with contextlib.suppress(TimeoutError):
        await dep.page.wait_for_load_state(
            "networkidle", timeout=timer.remaining() * 1000
        )

    status = HTTPStatus.OK
    cookies = await dep.context.cookies()
    response_body = "" if request.return_only_cookies else await dep.page.content()

    return LinkResponse(
        message="Success",
        solution=Solution(
            user_agent=await dep.page.evaluate("navigator.userAgent"),
            url=dep.page.url,
            status=status,
            cookies=cookies,
            headers={},
            response=response_body,
        ),
        start_timestamp=start_time,
    )


async def _handle_post(
    request: LinkRequest, dep: CamoufoxDepClass, timer: TimeoutTimer, start_time: int,
) -> LinkResponse:
    """Handle request.post command."""
    api_resp = await dep.context.request.post(
        request.url,
        form={
            k: v
            for pair in request.post_data.split("&")
            for k, v in [pair.split("=", 1)]
        }
        if request.post_data
        else None,
        timeout=timer.remaining() * 1000,
    )
    status = api_resp.status
    response_headers = await api_resp.all_headers()
    response_body = (await api_resp.body()).decode("utf-8", errors="replace")
    cookies = await dep.context.cookies()

    return LinkResponse(
        message="Success",
        solution=Solution(
            user_agent=await dep.page.evaluate("navigator.userAgent"),
            url=api_resp.url,
            status=status,
            cookies=cookies,
            headers=response_headers,
            response="" if request.return_only_cookies else response_body,
        ),
        start_timestamp=start_time,
    )


async def _handle_get(
    request: LinkRequest, dep: CamoufoxDepClass, timer: TimeoutTimer, start_time: int,
) -> LinkResponse:
    """Handle request.get command (default)."""
    page_request, status = await _navigate_and_wait(dep.page, request.url, timer)

    if await _solve_challenge_if_needed(dep.page, dep.solver, timer):
        status = HTTPStatus.OK

    cookies = await dep.context.cookies()

    return LinkResponse(
        message="Success",
        solution=Solution(
            user_agent=await dep.page.evaluate("navigator.userAgent"),
            url=dep.page.url,
            status=status,
            cookies=cookies,
            headers=page_request.headers if page_request else {},
            response="" if request.return_only_cookies else await dep.page.content(),
        ),
        start_timestamp=start_time,
    )


@router.post("/v1")
async def read_item(request: LinkRequest, dep: CamoufoxDep) -> LinkResponse:
    """Handle POST requests."""
    start_time = int(time.time() * 1000)

    timer = TimeoutTimer(duration=request.max_timeout)

    request.url = request.url.replace('"', "").strip()

    # Inject cookies into browser context before navigation
    # Playwright requires each cookie to have either url or domain+path
    if request.cookies:
        valid_cookies = [c for c in request.cookies if c.get("domain") or c.get("url")]
        if valid_cookies:
            await dep.context.add_cookies(valid_cookies)

    is_post = request.cmd == "request.post" or request.post_data is not None
    is_interact = request.cmd == "request.interact"

    try:
        match (is_interact, is_post):
            case (True, _):
                return await _handle_interact(request, dep, timer, start_time)
            case (_, True):
                return await _handle_post(request, dep, timer, start_time)
            case _:
                return await _handle_get(request, dep, timer, start_time)
    except TimeoutError as e:
        logger.error("Timed out while solving the challenge")
        raise HTTPException(
            status_code=408,
            detail="Timed out while solving the challenge",
        ) from e
    except Exception as e:  # noqa: BLE001
        error_msg = str(e)
        logger.error(f"Navigation failed: {error_msg}")
        return LinkResponse(
            status="error",
            message=error_msg[:ERROR_MESSAGE_MAX],
            solution=Solution(url=request.url, status=0),
            start_timestamp=start_time,
        )

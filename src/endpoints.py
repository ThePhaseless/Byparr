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

    # Inject cookies into browser context before navigation
    if request.cookies:
        await dep.context.add_cookies(request.cookies)

    is_post = request.cmd == "request.post" or request.post_data is not None
    is_interact = request.cmd == "request.interact"

    try:
        if is_interact:
            # INTERACT: navigate, solve challenge, execute browser actions
            page_request = await dep.page.goto(
                request.url, timeout=timer.remaining() * 1000
            )
            status = page_request.status if page_request else HTTPStatus.OK
            await dep.page.wait_for_load_state(
                state="domcontentloaded", timeout=timer.remaining() * 1000
            )
            try:
                await dep.page.wait_for_load_state(
                    "networkidle", timeout=15000
                )
            except Exception:
                logger.debug("networkidle timeout on interact (expected for pages with active scripts)")

            # Solve Cloudflare challenge if detected
            if await dep.page.title() in CHALLENGE_TITLES:
                logger.info("Challenge detected during interact, solving...")
                await wait_for(
                    dep.solver.solve_captcha(
                        captcha_container=dep.page,
                        captcha_type=CaptchaType.CLOUDFLARE_INTERSTITIAL,
                        wait_checkbox_attempts=1,
                        wait_checkbox_delay=0.5,
                    ),
                    timeout=timer.remaining(),
                )
                logger.debug("Challenge solved.")

            # Execute actions sequentially
            for act in request.actions:
                t = min(act.timeout, int(timer.remaining() * 1000))
                if act.action == "fill" and act.selector and act.value is not None:
                    await dep.page.fill(act.selector, act.value, timeout=t)
                elif act.action == "click" and act.selector:
                    await dep.page.click(act.selector, timeout=t)
                elif act.action == "type" and act.value is not None:
                    await dep.page.keyboard.type(act.value)
                elif act.action == "wait" and act.selector:
                    try:
                        await dep.page.wait_for_selector(act.selector, timeout=t)
                    except Exception as e:
                        logger.warning(f"wait for '{act.selector}' failed: {e}")
                        break
                elif act.action == "wait_url" and act.value:
                    try:
                        await dep.page.wait_for_url(act.value, timeout=t)
                    except Exception:
                        logger.info(f"wait_url '{act.value}' timed out, URL unchanged")
                        break
                elif act.action == "solve_turnstile":
                    logger.info("Solving Cloudflare Turnstile...")
                    # Try multiple iframe selectors
                    iframe_selectors = [
                        "iframe[src*='challenges.cloudflare.com']",
                        "iframe[src*='cloudflare.com/cdn-cgi']",
                        "iframe[src*='turnstile']",
                        "#turnstile-login iframe",
                        "[class*='turnstile'] iframe",
                        "iframe[allow*='cross-origin-isolated']",
                        "#cf-turnstile iframe",
                        "div[id*='turnstile'] iframe",
                    ]
                    iframe_found = False
                    for sel in iframe_selectors:
                        try:
                            await dep.page.wait_for_selector(sel, timeout=3000)
                            logger.info(f"Turnstile iframe found via: {sel}")
                            iframe_found = True
                            break
                        except Exception:
                            continue

                    if not iframe_found:
                        # Last resort: check all frames in context
                        frames = dep.page.frames
                        cf_frames = [f.url for f in frames if 'cloudflare' in f.url or 'turnstile' in f.url]
                        if cf_frames:
                            logger.info(f"Found CF frames via context: {cf_frames}")
                            iframe_found = True
                        else:
                            title = await dep.page.title()
                            all_frame_urls = [f.url for f in frames if f.url != 'about:blank']
                            logger.info(f"No Turnstile iframe found (title: {title}, frames: {all_frame_urls}), skipping.")
                            continue

                    solved = False
                    # Collect CF frames FIRST (before any slow operation)
                    cf_frames = [f for f in dep.page.frames if 'cloudflare' in f.url or 'turnstile' in f.url]
                    logger.info(f"CF frames found: {len(cf_frames)} ({[f.url[:60] for f in cf_frames]})")

                    # Method 1 (fast): Click iframe bbox on parent page
                    for frame in cf_frames:
                        try:
                            el = await frame.frame_element()
                            box = await el.bounding_box()
                            logger.info(f"CF frame bbox: {box}")
                            if box and box["width"] > 0 and box["height"] > 0:
                                x = box["x"] + 30
                                y = box["y"] + box["height"] / 2
                                await dep.page.mouse.click(x, y)
                                solved = True
                                logger.info(f"Clicked Turnstile iframe bbox at ({x}, {y})")
                                break
                        except Exception as bbox_err:
                            logger.warning(f"Bbox click failed: {bbox_err}")

                    # Method 2: Click inside CF frames
                    if not solved:
                        for frame in cf_frames:
                            for click_sel in ["body", "input[type='checkbox']", "#challenge-stage", "label"]:
                                try:
                                    await frame.click(click_sel, timeout=3000)
                                    solved = True
                                    logger.info(f"Clicked '{click_sel}' in CF frame.")
                                    break
                                except Exception:
                                    continue
                            if solved:
                                break

                    # Method 3: playwright_captcha solver (slow, last resort, 15s max)
                    if not solved:
                        try:
                            await wait_for(
                                dep.solver.solve_captcha(
                                    captcha_container=dep.page,
                                    captcha_type=CaptchaType.CLOUDFLARE_TURNSTILE,
                                ),
                                timeout=min(t / 1000, 15),
                            )
                            solved = True
                            logger.info("Turnstile solved via solver.")
                        except (TimeoutError, Exception) as e:
                            logger.warning(f"Turnstile solver also failed: {e}")

                    if solved:
                        await dep.page.wait_for_timeout(5000)
                    else:
                        logger.warning("All Turnstile methods failed, continuing...")
                elif act.action == "sleep":
                    await dep.page.wait_for_timeout(t)
                elif act.action == "js" and act.value:
                    js_result = await dep.page.evaluate(act.value)
                    if js_result and str(js_result) != 'None':
                        logger.info(f"JS result: {str(js_result)[:200]}")
                    else:
                        logger.debug(f"JS executed: {act.value[:80]}")
                elif act.action == "screenshot":
                    path = act.value or "/tmp/screenshot.png"
                    await dep.page.screenshot(path=path, full_page=True)
                    logger.info(f"Screenshot saved to {path}")
                else:
                    logger.warning(f"Unknown or incomplete action: {act.action}")

            # Wait for network to settle after actions
            try:
                await dep.page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

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

        if is_post:
            # POST: use API-level request (no page rendering, but with context cookies)
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

        # GET: navigate with page (supports challenge solving)
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

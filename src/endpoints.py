import time
import warnings
from asyncio import wait_for
from http import HTTPStatus
from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, Response
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

# /binary endpoint defaults
BINARY_DEFAULT_MAX_BYTES = 25 * 1024 * 1024  # 25 MiB
BINARY_DEFAULT_MAX_TIMEOUT = 90  # seconds (whole-request budget)
BINARY_FETCH_TIMEOUT_MS = 60_000  # per direct subresource fetch attempt


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

    cookies = await dep.context.cookies()

    return LinkResponse(
        message="Success",
        solution=Solution(
            user_agent=await dep.page.evaluate("navigator.userAgent"),
            url=dep.page.url,
            status=status,
            cookies=cookies,
            headers=page_request.headers if page_request else {},
            response=await dep.page.content(),
        ),
        start_timestamp=start_time,
    )


def _is_cf_challenge_body(body: bytes) -> bool:
    """Heuristic: detect Cloudflare interstitial HTML in a response body."""
    if len(body) > 200_000:  # CF challenge pages are small HTML
        return False
    head = body[:4096].lower()
    if b"<html" not in head and b"<!doctype" not in head:
        return False
    return (
        b"just a moment" in head
        or b"cf-challenge" in head
        or b"cf_chl_opt" in head
        or b"challenge-platform" in head
    )


async def _solve_challenge_for_origin(dep: CamoufoxDepClass, origin: str, timer: TimeoutTimer) -> None:
    """Navigate to the origin root and solve any CF interstitial.

    This warms the browser context's cookie jar with cf_clearance bound to
    THIS browser's TLS+H2 fingerprint, so the subsequent context.request.get()
    can succeed. Bytes never leave the browser process, eliminating cookie
    portability issues.
    """
    page_request = await dep.page.goto(origin, timeout=timer.remaining() * 1000)
    status = page_request.status if page_request else HTTPStatus.OK
    try:
        await dep.page.wait_for_load_state(
            state="domcontentloaded", timeout=timer.remaining() * 1000
        )
    except TimeoutError:
        pass  # noqa: S110 — best-effort warm-up; the solver below is what matters
    try:
        if await dep.page.title() in CHALLENGE_TITLES:
            logger.info("Challenge detected at %s, attempting to solve...", origin)
            await wait_for(
                dep.solver.solve_captcha(  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType]
                    captcha_container=dep.page,
                    captcha_type=CaptchaType.CLOUDFLARE_INTERSTITIAL,
                    wait_checkbox_attempts=1,
                    wait_checkbox_delay=0.5,
                ),
                timeout=timer.remaining(),
            )
            logger.debug("Challenge at %s solved.", origin)
    except TimeoutError as e:
        logger.error("Timed out solving the challenge at %s", origin)
        raise HTTPException(
            status_code=408, detail="Timed out while solving the challenge"
        ) from e
    logger.debug("Origin warm-up status=%s for %s", status, origin)


@router.get("/binary")
async def fetch_binary(
    dep: CamoufoxDep,
    url: Annotated[str, Query(description="Absolute http(s) URL of the binary asset to fetch")],
    referer: Annotated[
        str | None,
        Query(description="Optional referer URL; defaults to <scheme>://<host>/ of `url`"),
    ] = None,
    max_bytes: Annotated[
        int,
        Query(ge=1, le=200 * 1024 * 1024, description="Reject responses larger than this"),
    ] = BINARY_DEFAULT_MAX_BYTES,
    max_timeout: Annotated[
        int,
        Query(ge=10, le=180, description="Whole-request budget in seconds"),
    ] = BINARY_DEFAULT_MAX_TIMEOUT,
):
    """Fetch a binary asset (e.g. an image) through the same browser session
    that solves the Cloudflare challenge.

    Strategy:
      1. Try a direct subresource fetch via `context.request.get` — uses the
         browser's TLS/H2 fingerprint, UA, and cookie jar. Cheapest path.
      2. If that returns a CF challenge (status >= 400 or HTML interstitial),
         navigate to the origin root, solve the challenge, then retry (1).

    Bytes are streamed back with the upstream Content-Type. cf_clearance never
    leaves the browser process, which avoids the cookie-portability problem
    that breaks out-of-browser HTTP clients.
    """
    timer = TimeoutTimer(duration=max_timeout)

    cleaned_url = url.replace('"', "").strip()
    parsed = urlparse(cleaned_url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="url scheme must be http or https")
    if not parsed.netloc:
        raise HTTPException(status_code=400, detail="url has no host")

    origin = f"{parsed.scheme}://{parsed.netloc}/"
    referer_url = referer.strip() if referer else origin

    async def _do_fetch() -> tuple[int, dict[str, str], bytes]:
        """Issue one subresource fetch through the browser context.

        Returns (status, lowercased-headers, body). Verifies the body
        length matches the upstream Content-Length header when present
        — Playwright's APIRequestContext.body() can return early if
        the upstream connection drops before the full response body is
        delivered (most commonly seen with large JPEGs over flaky CDN
        edge nodes). Without this check, Sharp downstream would crash
        with `VipsJpeg: Premature end of input file` on 50%+ of
        chapter pages. We retry once at the call site if mismatch.
        """
        per_attempt_timeout = min(BINARY_FETCH_TIMEOUT_MS, int(timer.remaining() * 1000))
        if per_attempt_timeout <= 0:
            raise HTTPException(status_code=408, detail="Time budget exhausted")
        try:
            response = await dep.context.request.get(
                cleaned_url,
                headers={"Referer": referer_url, "Accept": "*/*"},
                max_redirects=5,
                timeout=per_attempt_timeout,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Subresource fetch errored for %s: %s", cleaned_url, exc)
            raise HTTPException(status_code=502, detail=f"upstream fetch error: {exc}") from exc
        body = await response.body()
        # Lowercase header dict so callers can do case-insensitive
        # lookups without re-implementing it everywhere.
        headers_lc = {k.lower(): v for k, v in dict(response.headers).items()}
        # Defensive length check — rejects truncated bodies that
        # Playwright didn't catch.
        cl_raw = headers_lc.get("content-length")
        if cl_raw is not None:
            try:
                expected = int(cl_raw)
            except ValueError:
                expected = -1
            if expected >= 0 and len(body) != expected:
                logger.warning(
                    "Body length mismatch for %s: got %dB, Content-Length=%dB — likely truncated",
                    cleaned_url, len(body), expected,
                )
                # Sentinel status — caller will treat as a transient
                # failure and retry once. Never collides with real HTTP
                # codes (max 599).
                return -1, headers_lc, body
        return response.status, headers_lc, body

    # Phase A — direct attempt
    status, headers, body = await _do_fetch()
    # Truncation retry — one extra attempt before giving up.
    if status == -1:
        logger.info("Retrying truncated fetch for %s", cleaned_url)
        status, headers, body = await _do_fetch()
        if status == -1:
            raise HTTPException(
                status_code=502,
                detail=f"upstream body truncated (got {len(body)}B vs Content-Length)",
            )
    needs_warmup = (
        status in (HTTPStatus.FORBIDDEN, HTTPStatus.SERVICE_UNAVAILABLE, 429)
        or _is_cf_challenge_body(body)
    )

    if needs_warmup:
        logger.info(
            "Direct fetch for %s returned status=%s, body=%dB — warming up via origin %s",
            cleaned_url, status, len(body), origin,
        )
        await _solve_challenge_for_origin(dep, origin, timer)
        # Phase B — retry after warm-up. Truncation here also retries
        # once for symmetry with Phase A, then escalates to 502.
        status, headers, body = await _do_fetch()
        if status == -1:
            logger.info("Retrying truncated fetch (post-warmup) for %s", cleaned_url)
            status, headers, body = await _do_fetch()
            if status == -1:
                raise HTTPException(
                    status_code=502,
                    detail=f"upstream body truncated (got {len(body)}B vs Content-Length)",
                )

    if status < HTTPStatus.OK or status >= HTTPStatus.MULTIPLE_CHOICES:
        raise HTTPException(
            status_code=status if 400 <= status < 600 else HTTPStatus.BAD_GATEWAY,
            detail=f"upstream returned {status}",
        )

    if len(body) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"response too large: {len(body)} > {max_bytes}",
        )

    if _is_cf_challenge_body(body):
        # Still a challenge after warm-up — give up.
        raise HTTPException(
            status_code=403,
            detail="upstream returned a Cloudflare challenge after warm-up",
        )

    # Headers are always lowercased by _do_fetch().
    media_type = headers.get("content-type") or "application/octet-stream"
    # Strip parameters like "image/jpeg; charset=binary" we don't care about, but keep "image/jpeg"
    safe_media_type = media_type.split(";")[0].strip() or "application/octet-stream"

    response_headers = {
        "X-Byparr-Bytes": str(len(body)),
        "X-Byparr-Source": cleaned_url,
        "Cache-Control": "no-store",
    }
    return Response(content=body, media_type=safe_media_type, headers=response_headers)

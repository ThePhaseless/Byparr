from fastapi import APIRouter, Request, Response
from fastapi.responses import PlainTextResponse, HTMLResponse
import logging
from src.utils import get_sb, logger, save_screenshot
from src.consts import CHALLENGE_TITLES
from fastapi import HTTPException
from sbase import BaseCase

router = APIRouter()
proxy_logger = logging.getLogger("proxy")

async def log_proxy_request(request: Request):
    proxy_logger.info(f"Proxying {request.method} {request.url}")

@router.api_route("/{full_path:path}", methods=["GET"])
async def proxy_handler(full_path: str, request: Request):
    await log_proxy_request(request)

    # Only support GET for proxy mode (as /v1 does)
    # Extract the full URL from the incoming request (including scheme)
    # FastAPI's request.url._url gives the full proxy-style URL (e.g., http:// or https://)
    url = request.url._url
    # Remove the proxy server's own host/port, so we get the target URL
    # Example: url = 'https://www.bikemn.org/get-involved/clubs-teams/'
    # This works for curl and most HTTP clients using --proxy
    # If the scheme is missing, fallback to http
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url.lstrip("/")

    # Use the same Selenium logic as /v1
    try:
        sb_gen = get_sb(proxy=None)
        sb = next(sb_gen)
        sb.uc_open_with_reconnect(url)
        logger.debug(f"Got webpage: {url}")
        source_bs = sb.get_beautiful_soup()
        title_tag = source_bs.title
        if title_tag and title_tag.string in CHALLENGE_TITLES:
            logger.debug("Challenge detected")
            sb.uc_gui_click_captcha()
            logger.info("Clicked captcha")
        if sb.get_title() in CHALLENGE_TITLES:
            save_screenshot(sb)
            return Response("Could not bypass challenge", status_code=500)
        cookies = sb.get_cookies()
        # Compose Set-Cookie headers
        response_headers = {}
        set_cookie_headers = []
        for cookie in cookies:
            cookie_str = f"{cookie['name']}={cookie['value']}"
            if 'expiry' in cookie:
                cookie_str += f"; Expires={cookie['expiry']}"
            if cookie.get('path'):
                cookie_str += f"; Path={cookie['path']}"
            set_cookie_headers.append(("set-cookie", cookie_str))
        # Compose response
        html = str(sb.get_beautiful_soup())
        # Use FastAPI's HTMLResponse to set multiple Set-Cookie headers
        resp = HTMLResponse(
            content=html,
            status_code=200,
            headers={h: v for h, v in set_cookie_headers},
        )
        # Actually set all Set-Cookie headers
        for k, v in set_cookie_headers:
            resp.headers.append(k, v)
        return resp
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        return Response("Internal server error", status_code=500)

from __future__ import annotations

import logging
import time

import uvicorn.config
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from sbase import SB, BaseCase

import src
import src.utils
import src.utils.consts
from src.models.requests import LinkRequest, LinkResponse, Solution
from src.utils import logger
from src.utils.consts import LOG_LEVEL

app = FastAPI(debug=LOG_LEVEL == logging.DEBUG, log_level=LOG_LEVEL)


@app.get("/")
def read_root():
    """Redirect to /docs."""
    logger.info("Redirecting to /docs")
    return RedirectResponse(url="/docs", status_code=301)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    logger.info("Health check")
    # browser: Chrome = await new_browser()
    # browser.get("https://google.com")
    # browser.stop()
    return {"status": "ok"}


@app.post("/v1")
def read_item(request: LinkRequest):
    """Handle POST requests."""
    start_time = int(time.time() * 1000)
    # request.url = "https://nowsecure.nl"
    logger.info(f"Request: {request}")
    response: LinkResponse

    # start_time = int(time.time() * 1000)
    with SB(uc=True, locale_code="en", test=False, xvfb=True, ad_block=True) as sb:
        sb: BaseCase
        sb.uc_open_with_reconnect(request.url)
        sb.uc_gui_click_captcha()
        logger.info(f"Got webpage: {request.url}")
        sb.save_screenshot("screenshot.png")
        logger.info(f"Got webpage: {request.url}")

        source = sb.get_page_source()
        source_bs = BeautifulSoup(source, "html.parser")
        title_tag = source_bs.title
        if title_tag is None:
            raise HTTPException(status_code=500, detail="Title tag not found")

        if title_tag.string in src.utils.consts.CHALLENGE_TITLES:
            raise HTTPException(status_code=500, detail="Could not bypass challenge")

        title = title_tag.string
        logger.info(f"Title: {title}")
        response = LinkResponse(
            message="Success",
            solution=Solution(
                userAgent=sb.get_user_agent(),
                url=sb.get_current_url(),
                status=200,
                cookies=sb.get_cookies(),
                headers={},
                response=source,
            ),
            startTimestamp=start_time,
        )

    return response


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8191, log_level=LOG_LEVEL)  # noqa: S104

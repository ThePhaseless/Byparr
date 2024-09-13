from __future__ import annotations

import asyncio
import logging
import time

import uvicorn
import uvicorn.config
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from src.models.requests import LinkRequest, LinkResponse
from src.utils import logger
from src.utils.browser import bypass_cloudflare, new_browser
from src.utils.consts import LOG_LEVEL

app = FastAPI(debug=LOG_LEVEL == logging.DEBUG, log_level=LOG_LEVEL)


@app.get("/")
def read_root():
    """Redirect to /docs."""
    logger.info("Redirecting to /docs")
    return RedirectResponse(url="/docs", status_code=301)


@app.post("/v1")
async def read_item(request: LinkRequest):
    """Handle POST requests."""
    # request.url = "https://nowsecure.nl"
    logger.info(f"Request: {request}")
    start_time = int(time.time() * 1000)
    browser = await new_browser()
    page = await browser.get(request.url)
    await page.bring_to_front()
    timeout = request.maxTimeout
    if timeout == 0:
        timeout = None

    challenged = await asyncio.wait_for(bypass_cloudflare(page), timeout=timeout)

    logger.info(f"Got webpage: {request.url}")

    response = await LinkResponse.create(
        page=page,
        start_timestamp=start_time,
        challenged=challenged,
    )

    browser.stop()
    return response


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8191, log_level=LOG_LEVEL)  # noqa: S104

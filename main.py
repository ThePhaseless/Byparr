from __future__ import annotations

import asyncio
import time

import uvicorn
import uvicorn.config
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from src.models.requests import LinkRequest, LinkResponse
from src.utils import logger
from src.utils.extentions import download_extentions
from src.utils.misc import bypass_cloudflare, new_browser

download_extentions()
app = FastAPI(debug=True)


@app.get("/")
def read_root():
    """Redirect to /docs."""
    logger.info("Redirecting to /docs")
    return RedirectResponse(url="/docs", status_code=301)


@app.post("/v1")
async def read_item(request: LinkRequest):
    """Handle POST requests."""
    logger.info(f"Request: {request}")
    start_time = int(time.time() * 1000)
    browser = await new_browser()
    page = await browser.get(request.url)

    challenged = await asyncio.wait_for(
        bypass_cloudflare(page), timeout=request.maxTimeout
    )
    if challenged:
        logger.info("Challenged")
    else:
        logger.info("Not challenged")

    response = await LinkResponse.create(
        page=page,
        start_timestamp=start_time,
        challenged=challenged,
    )
    browser.stop()
    return response


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8191)  # noqa: S104

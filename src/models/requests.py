from __future__ import annotations

import re
import time
from typing import Any

from nodriver import Tab
from pydantic import BaseModel


class LinkRequest(BaseModel):
    cmd: str
    url: str
    maxTimeout: int  # noqa: N815 # Ignore to preserve compatibility


class ProtectionTriggeredError(Exception):
    pass


class Solution(BaseModel):
    url: str
    status: int
    cookies: list[dict]
    userAgent: str  # noqa: N815 # Ignore to preserve compatibility
    headers: dict[str, Any]
    response: str


class LinkResponse(BaseModel):
    status: str = "ok"
    message: str
    solution: Solution
    startTimestamp: int  # noqa: N815 # Ignore to preserve compatibility
    endTimestamp: int = int(time.time() * 1000)  # noqa: N815 # Ignore to preserve compatibility
    version: str = "3.3.21"  # TODO: Implement versioning

    @classmethod
    async def create(
        cls,
        page: Tab,
        start_timestamp: int,
        *,
        challenged: bool = False,
    ):
        message = "Passed challenge" if challenged else "Challenge not detected"

        user_agent = await page.js_dumps("navigator")
        if not isinstance(user_agent, dict):
            raise ProtectionTriggeredError("User agent is not a dictionary")
        user_agent = user_agent["userAgent"]
        re.sub(pattern="HEADLESS", repl="", string=user_agent, flags=re.IGNORECASE)

        # cookies = await page.browser.cookies.get_all(requests_cookie_format=True)
        # # Convert cookies to json
        # cookies = [cookie.to_json() for cookie in cookies]

        cookies = []
        solution = Solution(
            url=page.url,
            status=200,
            cookies=cookies,
            userAgent=user_agent,
            headers={},
            response=await page.get_content(),
        )

        return cls(
            message=message,
            solution=solution,
            startTimestamp=start_timestamp,
        )

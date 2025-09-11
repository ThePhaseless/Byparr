from __future__ import annotations

import time
from http.client import INTERNAL_SERVER_ERROR
from typing import Any

from playwright.sync_api import Cookie
from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel

from src import consts


class LinkRequest(BaseModel):
    cmd: str = Field(
        default="request.get",
        description="Type of request, currently only supports GET requests. This string is purely for compatibility with FlareSolverr.",
    )
    url: str = Field(pattern=r"^https?://", default="https://")
    max_timeout: int = Field(
        default=60,
        description="Maximum timeout in seconds for resolving the anti-bot challenge.",
    )


class HealthcheckResponse(BaseModel):
    model_config = {"alias_generator": to_camel, "populate_by_name": True}
    msg: str = "Byparr is working!"
    version: str = consts.VERSION
    user_agent: str


class Solution(BaseModel):
    model_config = {"alias_generator": to_camel, "populate_by_name": True}
    url: str
    status: int
    cookies: list[Cookie] = []
    user_agent: str = ""
    headers: dict[str, Any] = {}
    response: str = ""


class LinkResponse(BaseModel):
    model_config = {"alias_generator": to_camel, "populate_by_name": True}
    status: str = "ok"
    message: str
    solution: Solution
    start_timestamp: int
    end_timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))
    version: str = consts.VERSION

    @classmethod
    def invalid(cls, url: str):
        """
        Return an invalid LinkResponse with default error values.

        This method is used to generate a response indicating an invalid request.
        """
        return cls(
            status="error",
            message="Invalid request",
            solution=Solution(url=url, status=INTERNAL_SERVER_ERROR),
            start_timestamp=int(time.time() * 1000),
        )

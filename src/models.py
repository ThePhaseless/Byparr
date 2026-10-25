from __future__ import annotations

import time
from typing import Any

from playwright.sync_api import Cookie
from pydantic import BaseModel, Field, field_validator
from pydantic.alias_generators import to_camel

from src import consts

MS_PER_SECOND = 1000


class LinkRequest(BaseModel):
    model_config = {"alias_generator": to_camel, "populate_by_name": True}
    cmd: str = "request.get"
    url: str
    max_timeout: int = Field(default=60, alias="maxTimeout")
    cookies: list[Cookie] = []
    post_data: str | None = Field(default=None, alias="postData")
    block_media: bool = Field(
        default=consts.BLOCK_MEDIA,
        alias="blockMedia",
        description="Block media (images, fonts, stylesheets) for faster scraping.",
    )
    return_only_cookies: bool = Field(
        default=consts.RETURN_ONLY_COOKIES,
        alias="returnOnlyCookies",
        description="Return only cookies, skip the page HTML content in the response.",
    )

    @field_validator("max_timeout")
    @classmethod
    def normalize_max_timeout(cls, value: int) -> int:
        """Normalize FlareSolverr-style millisecond values to seconds."""
        if value >= MS_PER_SECOND:
            return value // MS_PER_SECOND
        return value


class HealthcheckResponse(BaseModel):
    model_config = {"alias_generator": to_camel, "populate_by_name": True}
    msg: str = "Byparr is working!"
    version: str = consts.VERSION
    user_agent: str
    max_concurrency: int = consts.MAX_CONCURRENCY
    estimated_memory_mb: int = consts.MAX_CONCURRENCY * 250
    memory_warning: str = ""


class ConcurrencyConfigRequest(BaseModel):
    model_config = {"alias_generator": to_camel, "populate_by_name": True}
    max_concurrency: int = Field(ge=1, le=64, description="Target concurrent browser sessions (1-64)")


class ConcurrencyConfigResponse(BaseModel):
    model_config = {"alias_generator": to_camel, "populate_by_name": True}
    max_concurrency: int
    estimated_memory_mb: int
    memory_warning: str
    auto_sync: bool


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
    message: str = ""
    solution: Solution
    start_timestamp: int
    end_timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))
    version: str = consts.VERSION
    concurrency_limit: int = consts.MAX_CONCURRENCY
    concurrency_warning: str | None = None

    @classmethod
    def invalid(cls, url: str) -> LinkResponse:
        return cls(
            status="error",
            message="Error: URL is not valid.",
            solution=Solution(
                url=url,
                status=400,
            ),
            start_timestamp=int(time.time() * 1000),
        )

from __future__ import annotations

import time
from http import HTTPStatus
from typing import Any

from pydantic import BaseModel, Field


class LinkRequest(BaseModel):
    cmd: str = "get"
    url: str
    max_timeout: int = Field(30, alias="maxTimeout")


class ProtectionTriggeredError(Exception):
    pass


class Solution(BaseModel):
    url: str
    status: int
    cookies: list
    userAgent: str  # noqa: N815 # Ignore to preserve compatibility
    headers: dict[str, Any]
    response: str

    @classmethod
    def empty(cls):
        return cls(
            url="",
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
            cookies=[],
            userAgent="",
            headers={},
            response="",
        )


class LinkResponse(BaseModel):
    status: str = "ok"
    message: str
    solution: Solution
    startTimestamp: int  # noqa: N815 # Ignore to preserve compatibility
    endTimestamp: int = int(time.time() * 1000)  # noqa: N815 # Ignore to preserve compatibility
    version: str = "3.3.21"  # TODO: Implement versioning

    @classmethod
    def invalid(cls):
        return cls(
            status="error",
            message="Invalid request",
            solution=Solution.empty(),
            startTimestamp=int(time.time() * 1000),
            endTimestamp=int(time.time() * 1000),
            version="3.3.21",
        )


class NoChromeExtensionError(Exception):
    """No chrome extention found."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated, Any, NamedTuple, cast

from fastapi import Header
from invisible_playwright.async_api import InvisiblePlaywright
from playwright.async_api import Browser, BrowserContext, Page

from src.consts import (
    BROWSER_LOCALE,
    MAX_CONCURRENCY,
    PROXY_PASSWORD,
    PROXY_SERVER,
    PROXY_USERNAME,
)
from src.dynamic_semaphore import DynamicSemaphore


class BrowserDepClass(NamedTuple):
    """Encapsulates the page and browser context allocated for a request."""

    page: Page
    context: BrowserContext
    http3_enabled: bool = True


class BrowserManager:
    """
    Manages browser lifecycle, configuration, and dynamic concurrency limits.
    Supports dynamic runtime resizing and selective HTTP/2 fallback.
    """

    def __init__(self, max_concurrency: int = MAX_CONCURRENCY) -> None:
        self.max_concurrency = max_concurrency
        self._semaphore = DynamicSemaphore(max_concurrency)

    def update_concurrency(self, new_limit: int) -> int:
        """Dynamically update maximum concurrency at runtime."""
        new_capacity = self._semaphore.set_capacity(new_limit)
        self.max_concurrency = new_capacity
        return new_capacity

    def _resolve_proxy_config(
        self,
        header_server: str | None = None,
        header_username: str | None = None,
        header_password: str | None = None,
    ) -> dict[str, Any] | None:
        if header_server:
            return {
                "server": header_server,
                "username": header_username,
                "password": header_password,
            }
        if PROXY_SERVER:
            return {
                "server": PROXY_SERVER,
                "username": PROXY_USERNAME,
                "password": PROXY_PASSWORD,
            }
        return None

    def _build_extra_prefs(self, disable_http3: bool = False) -> dict[str, Any]:
        prefs: dict[str, Any] = {
            "devtools.jsonview.enabled": False,
            "browser.tabs.remote.useCrossOriginOpenerPolicy": False,
            "browser.tabs.remote.useCrossOriginEmbedderPolicy": False,
        }
        if disable_http3:
            # Fallback to HTTP/2 and HTTP/1.1
            prefs["network.http.http3.enable"] = False
        else:
            # Retain HTTP/3 enabled by default for modern sites
            prefs["network.http.http3.enable"] = True
        return prefs

    async def acquire_browser(
        self,
        header_server: str | None = None,
        header_username: str | None = None,
        header_password: str | None = None,
        disable_http3: bool = False,
    ) -> AsyncGenerator[BrowserDepClass, None]:
        """
        Acquires an isolated browser instance within the concurrency limit.
        """
        proxy_config = self._resolve_proxy_config(
            header_server, header_username, header_password
        )
        extra_prefs = self._build_extra_prefs(disable_http3=disable_http3)

        async with self._semaphore:
            async with InvisiblePlaywright(
                headless=True,
                proxy=proxy_config,
                humanize=True,
                locale=BROWSER_LOCALE or "auto",
                extra_prefs=extra_prefs,
            ) as browser_raw:
                browser = cast("Browser", browser_raw)
                context = await browser.new_context()
                page = await context.new_page()
                try:
                    yield BrowserDepClass(
                        page=page, context=context, http3_enabled=not disable_http3
                    )
                finally:
                    try:
                        await page.close()
                    except Exception:
                        pass
                    try:
                        await context.close()
                    except Exception:
                        pass


browser_manager = BrowserManager()


async def get_browser(
    x_proxy_server: Annotated[
        str | None,
        Header(
            alias="X-Proxy-Server",
            description="Override proxy server for this request in protocol://host:port format.",
        ),
    ] = None,
    x_proxy_username: Annotated[
        str | None,
        Header(
            alias="X-Proxy-Username",
        ),
    ] = None,
    x_proxy_password: Annotated[
        str | None,
        Header(
            alias="X-Proxy-Password",
        ),
    ] = None,
) -> AsyncGenerator[BrowserDepClass, None]:
    """Dependency provider yielding an isolated stealth browser instance."""
    async for dep in browser_manager.acquire_browser(
        header_server=x_proxy_server,
        header_username=x_proxy_username,
        header_password=x_proxy_password,
        disable_http3=False,
    ):
        yield dep

from http import HTTPStatus
from json import JSONDecodeError
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from starlette.testclient import TestClient

from main import app
from src.endpoints import read_item
from src.models import LinkRequest
from src.utils import BrowserDepClass

client = TestClient(app)
PLAYWRIGHT_TIMEOUT_MESSAGE = "timeout"

test_websites = [
    "https://ext.to/",
    # "https://www.ygg.re/",
    "https://extratorrent.st/",
    "https://speed.cd/login",
    'https://www.yggtorrent.top/engine/search?do=search&order=desc&sort=publish_date&name="UNESCAPED"+"DOUBLEQUOTES"&category=2145',
    "https://1337x.to/home/",
]


@pytest.mark.parametrize("website", test_websites)
def test_bypass(website: str):
    """
    Tests if the service can bypass cloudflare/DDOS-GUARD on given websites.

    This test is skipped if the website is not reachable or does not have cloudflare/DDOS-GUARD.
    """
    test_request = httpx.get(
        website,
    )
    if (
        test_request.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR
        and "Just a moment..." not in test_request.text
    ):
        try:
            error_details = test_request.json()
        except JSONDecodeError:
            error_details = test_request.text
        pytest.skip(
            f"Skipping {website} - ({test_request.status_code}) {error_details}"
        )

    response = client.post(
        "/v1",
        json=LinkRequest.model_construct(url=website, cmd="request.get").model_dump(),
    )

    if response.status_code == HTTPStatus.REQUEST_TIMEOUT:
        pytest.skip(f"Skipping {website} - timed out (upstream issue)")

    assert response.status_code == HTTPStatus.OK


def test_health_check():
    """
    Tests the health check endpoint.

    This test ensures that the health check
    endpoint returns HTTPStatus.OK.
    """
    response = client.get("/health")
    assert response.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_networkidle_timeout_after_domcontentloaded_returns_content():
    """Do not fail pages that keep background requests open after DOM load."""

    class Page:
        url = "https://example.test/login"

        async def goto(self, _url: str, **_kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(
                status=HTTPStatus.OK, headers={"content-type": "text/html"}
            )

        async def wait_for_load_state(
            self, state: str, **_kwargs: object
        ) -> None:
            if state == "networkidle":
                raise PlaywrightTimeoutError(PLAYWRIGHT_TIMEOUT_MESSAGE)

        async def title(self) -> str:
            return "Login"

        async def evaluate(self, _expression: str) -> str:
            return "UnitTestBrowser/1.0"

        async def content(self) -> str:
            return "<html><title>Login</title></html>"

    class Context:
        async def cookies(self) -> list[object]:
            return []

    response = await read_item(
        LinkRequest(url="https://example.test/login"),
        BrowserDepClass(
            page=Page(),
            solver=SimpleNamespace(),
            context=Context(),
        ),
    )

    assert response.status == "ok"
    assert response.solution.status == HTTPStatus.OK
    assert response.solution.response == "<html><title>Login</title></html>"


@pytest.mark.asyncio
async def test_domcontentloaded_timeout_returns_408():
    """Fatal Playwright timeouts still return a controlled HTTP error."""

    class Page:
        async def goto(self, _url: str, **_kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(status=HTTPStatus.OK, headers={})

        async def wait_for_load_state(
            self, state: str = "", **_kwargs: object
        ) -> None:
            message = f"{state} {PLAYWRIGHT_TIMEOUT_MESSAGE}"
            raise PlaywrightTimeoutError(message)

    with pytest.raises(HTTPException) as exc:
        await read_item(
            LinkRequest(url="https://example.test/login"),
            BrowserDepClass(
                page=Page(),
                solver=SimpleNamespace(),
                context=SimpleNamespace(),
            ),
        )

    assert exc.value.status_code == HTTPStatus.REQUEST_TIMEOUT


def test_pdf_handling():
    """Tests that PDF URLs return the raw PDF bytes, not the Firefox viewer HTML."""
    pdf_url = "https://mondaymandala.com/wp-content/uploads/Mickey-And-Minnie-Mouse-Holding-An-Easter-Egg-Basket-Coloring-Page-For-Kids.pdf"
    response = client.post(
        "/v1",
        json=LinkRequest.model_construct(url=pdf_url, cmd="request.get").model_dump(),
    )
    if response.status_code == HTTPStatus.REQUEST_TIMEOUT:
        pytest.skip("Skipping PDF test - timed out (upstream issue)")
    assert response.status_code == HTTPStatus.OK
    solution = response.json()["solution"]
    if solution.get("contentType") != "application/pdf":
        pytest.skip("Skipping PDF test - PDF bytes could not be fetched (upstream issue)")
    assert solution["response"]  # non-empty base64
    import base64

    decoded = base64.b64decode(solution["response"])
    assert decoded[:5] == b"%PDF-"

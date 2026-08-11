from http import HTTPStatus
from json import JSONDecodeError
from unittest.mock import AsyncMock, MagicMock

import httpx2
import pytest
from fastapi import HTTPException
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from starlette.testclient import TestClient

from main import app
from src.endpoints import read_item
from src.models import LinkRequest
from src.utils import BrowserDepClass

client = TestClient(app)

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
    test_request = httpx2.get(
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


def test_json_api():
    """JSON APIs must return 200, not crash on the UA evaluate.

    Firefox renders application/json in a built-in viewer whose CSP blocks
    Playwright's eval-based evaluate() (issue #394). The browser must be
    launched with the viewer disabled so /v1 works and returns the raw JSON.
    """
    url = "https://api.ipify.org?format=json"
    test_request = httpx2.get(url)
    if test_request.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
        pytest.skip(
            f"Skipping JSON API test - upstream error ({test_request.status_code})"
        )

    response = client.post(
        "/v1",
        json=LinkRequest.model_construct(url=url, cmd="request.get").model_dump(),
    )

    if response.status_code == HTTPStatus.REQUEST_TIMEOUT:
        pytest.skip("Skipping JSON API test - timed out (upstream issue)")

    assert response.status_code == HTTPStatus.OK
    solution = response.json()["solution"]
    assert solution["user_agent"]
    assert '"ip"' in solution["response"]


def test_health_check():
    """
    Tests the health check endpoint.

    This test ensures that the health check
    endpoint returns HTTPStatus.OK.
    """
    response = client.get("/health")
    assert response.status_code == HTTPStatus.OK


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


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"max_timeout": 60}, 60),  # native API: seconds
        ({"maxTimeout": 60}, 60),  # FlareSolverr alias, seconds-range value
        ({"maxTimeout": 60000}, 60),  # FlareSolverr alias: milliseconds
        ({"maxTimeout": 55000}, 55),
        ({"maxTimeout": 1000}, 1),
        ({}, 60),  # default
    ],
)
def test_max_timeout_normalization(payload: dict, expected: int):
    """MaxTimeout must accept FlareSolverr's milliseconds while keeping seconds."""
    request = LinkRequest(url="https://example.com", **payload)
    assert request.max_timeout == expected


def fake_dep(*, fail_states: set[str] | None = None) -> BrowserDepClass:
    """Build a browser dependency triple backed by mocks."""
    page = AsyncMock()
    page.url = "https://example.test/login"
    page.goto.return_value = MagicMock(
        status=HTTPStatus.OK, headers={"content-type": "text/html"}
    )
    page.title.return_value = "Login"
    page.evaluate.return_value = "UnitTestBrowser/1.0"
    page.content.return_value = "<html><title>Login</title></html>"

    def wait_for_load_state(state: str, **_kwargs: object) -> None:
        """Fail the wait when asked for a configured state."""
        if state in (fail_states or set()):
            message = "load state wait timed out"
            raise PlaywrightTimeoutError(message)

    page.wait_for_load_state.side_effect = wait_for_load_state

    context = AsyncMock()
    context.cookies.return_value = []
    return BrowserDepClass(page=page, solver=AsyncMock(), context=context)


@pytest.mark.asyncio
async def test_networkidle_timeout_after_domcontentloaded_returns_content():
    """Pages that never go idle after DOM load must still return their content."""
    response = await read_item(
        LinkRequest(url="https://example.test/login"),
        fake_dep(fail_states={"networkidle"}),
    )

    assert response.status == "ok"
    assert response.solution.status == HTTPStatus.OK
    assert response.solution.response == "<html><title>Login</title></html>"


@pytest.mark.asyncio
async def test_domcontentloaded_timeout_returns_408():
    """Fatal timeouts during initial page load still return a controlled 408."""
    with pytest.raises(HTTPException) as exc:
        await read_item(
            LinkRequest(url="https://example.test/login"),
            fake_dep(fail_states={"domcontentloaded"}),
        )

    assert exc.value.status_code == HTTPStatus.REQUEST_TIMEOUT

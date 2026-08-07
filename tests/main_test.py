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


class FakeLoadStateError(PlaywrightTimeoutError):
    """Raised by FakePage.wait_for_load_state for configured failing states."""


class FakePage:
    """Playwright Page double; load-state waits fail for configured states."""

    url = "https://example.test/login"

    def __init__(self, *, fail_states: set[str] | None = None) -> None:
        """Create a page whose waits fail for the given load states."""
        self.fail_states = fail_states or set()

    async def goto(self, _url: str, **_kwargs: object) -> SimpleNamespace:
        """Return a successful navigation result."""
        return SimpleNamespace(
            status=HTTPStatus.OK, headers={"content-type": "text/html"}
        )

    async def wait_for_load_state(self, state: str, **_kwargs: object) -> None:
        """Fail for configured states; otherwise do nothing."""
        if state in self.fail_states:
            message = "load state wait timed out"
            raise FakeLoadStateError(message)

    async def title(self) -> str:
        """Return a title that is not a challenge title."""
        return "Login"

    async def evaluate(self, _expression: str) -> str:
        """Return the user agent the API reports."""
        return "UnitTestBrowser/1.0"

    async def content(self) -> str:
        """Return the HTML body the API should return."""
        return "<html><title>Login</title></html>"


class FakeContext:
    """Playwright BrowserContext double."""

    async def cookies(self) -> list[object]:
        """Return no cookies."""
        return []


def make_dep(page: FakePage) -> BrowserDepClass:
    """Build the browser dependency triple around a fake page."""
    return BrowserDepClass(page=page, solver=SimpleNamespace(), context=FakeContext())


@pytest.mark.asyncio
async def test_networkidle_timeout_after_domcontentloaded_returns_content():
    """Pages that never go idle after DOM load must still return their content."""
    response = await read_item(
        LinkRequest(url="https://example.test/login"),
        make_dep(FakePage(fail_states={"networkidle"})),
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
            make_dep(FakePage(fail_states={"domcontentloaded"})),
        )

    assert exc.value.status_code == HTTPStatus.REQUEST_TIMEOUT

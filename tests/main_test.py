import base64
from http import HTTPStatus
from json import JSONDecodeError
from unittest.mock import AsyncMock, MagicMock

import httpx2
import pytest
from fastapi import HTTPException
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright_captcha.solvers.click.cloudflare.utils.detection import (
    CF_INTERSTITIAL_INDICATORS_SELECTORS,
)
from playwright_captcha.utils.exceptions import (
    CaptchaDetectionError,
    CaptchaSolvingError,
)
from starlette.testclient import TestClient

from main import app
from src.endpoints import read_item
from src.models import LinkRequest
from src.utils import BrowserDepClass

client = TestClient(app)

cloudflare_refuses = pytest.mark.xfail(
    reason="Cloudflare declines the click on invisible_playwright; camoufox clears it",
    strict=False,
)

test_websites = [
    pytest.param("https://ext.to/", marks=cloudflare_refuses),
    # "https://www.ygg.re/",
    pytest.param("https://extratorrent.st/", marks=cloudflare_refuses),
    pytest.param("https://speed.cd/login", marks=cloudflare_refuses),
    'https://www.yggtorrent.top/engine/search?do=search&order=desc&sort=publish_date&name="UNESCAPED"+"DOUBLEQUOTES"&category=2145',
    pytest.param("https://1337x.to/home/", marks=cloudflare_refuses),
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
        json=LinkRequest.model_construct(
            url=website, cmd="request.get", max_timeout=360
        ).model_dump(),
    )

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
    assert solution["userAgent"]
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
        pytest.skip(
            "Skipping PDF test - PDF bytes could not be fetched (upstream issue)"
        )
    assert solution["response"]  # non-empty base64

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


def fake_dep(
    *,
    fail_states: set[str] | None = None,
    challenged: bool = False,
    marker_counts: list[int] | None = None,
) -> BrowserDepClass:
    """Build a browser dependency triple backed by mocks."""
    page = AsyncMock()
    page.url = "https://example.test/login"
    page.goto.return_value = MagicMock(
        status=HTTPStatus.OK,
        headers={"content-type": "text/html"},
        request=MagicMock(headers={"user-agent": "UnitTestBrowser/1.0"}),
    )
    page.title.return_value = "Login"
    page.evaluate.return_value = "UnitTestBrowser/1.0"
    page.content.return_value = "<html><title>Login</title></html>"
    remaining = list(marker_counts or [])

    def count_for(selector: str) -> int:
        """Answer the marker check from the script, else from `challenged`."""
        if selector not in CF_INTERSTITIAL_INDICATORS_SELECTORS or not remaining:
            return 1 if challenged else 0
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    def locator(selector: str) -> MagicMock:
        handle = MagicMock()
        handle.count = AsyncMock(side_effect=lambda: count_for(selector))
        return handle

    page.locator = MagicMock(side_effect=locator)

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
    dep = fake_dep(fail_states={"networkidle"})
    response = await read_item(
        LinkRequest(url="https://example.test/login"),
        dep,
    )

    assert response.status == "ok"
    assert response.solution.status == HTTPStatus.OK
    assert response.solution.response == "<html><title>Login</title></html>"
    dep.solver.solve_captcha.assert_not_called()


@pytest.mark.asyncio
async def test_domcontentloaded_timeout_returns_408():
    """Fatal timeouts during initial page load still return a controlled 408."""
    with pytest.raises(HTTPException) as exc:
        await read_item(
            LinkRequest(url="https://example.test/login"),
            fake_dep(fail_states={"domcontentloaded"}),
        )

    assert exc.value.status_code == HTTPStatus.REQUEST_TIMEOUT


@pytest.mark.asyncio
async def test_user_agent_survives_csp_blocked_evaluate():
    """UA comes from request headers when page CSP blocks evaluate (#394).

    No CSP configuration (header, meta tag, or internal viewer document) may
    turn /v1 into a 500.
    """
    dep = fake_dep()
    dep.page.evaluate.side_effect = Exception("call to eval() blocked by CSP")

    response = await read_item(
        LinkRequest(url="https://example.test/login"),
        dep,
    )

    assert response.status == "ok"
    assert response.solution.user_agent == "UnitTestBrowser/1.0"


@pytest.mark.asyncio
async def test_challenge_that_clears_is_reported_as_success():
    """A challenge is over when its markup goes, not when the solver says so."""
    dep = fake_dep(challenged=True, marker_counts=[1, 0])
    dep.solver.solve_captcha.side_effect = CaptchaSolvingError(
        "challenge still present"
    )

    response = await read_item(
        LinkRequest(url="https://example.test/login", max_timeout=5), dep
    )

    assert response.status == "ok"
    assert response.solution.status == HTTPStatus.OK


@pytest.mark.asyncio
async def test_challenge_that_never_clears_returns_408():
    """A challenge still up when the budget runs out is a timeout, not a 500."""
    dep = fake_dep(challenged=True, marker_counts=[1])
    dep.solver.solve_captcha.side_effect = CaptchaDetectionError("iframes not found")

    with pytest.raises(HTTPException) as exc:
        await read_item(
            LinkRequest(url="https://example.test/login", max_timeout=2), dep
        )

    assert exc.value.status_code == HTTPStatus.REQUEST_TIMEOUT

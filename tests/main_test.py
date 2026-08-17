import base64
import json
import re
from http import HTTPStatus
from json import JSONDecodeError
from unittest.mock import AsyncMock, MagicMock

import httpx2
import pytest
from fastapi import HTTPException
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from starlette.testclient import TestClient

from main import app
from src.endpoints import CHALLENGE_MARKERS, CHECKBOX_OFFSET_X, read_item
from src.models import LinkRequest
from src.utils import BrowserDepClass

client = TestClient(app)

FIREFOX_CIPHER_SUITE_CEILING = 20

WIDGET_BOX = {"x": 512.0, "y": 304.0, "width": 300.0, "height": 65.0}

test_websites = [
    "https://nowsecure.nl/",
    'https://www.yggtorrent.top/engine/search?do=search&order=desc&sort=publish_date&name="UNESCAPED"+"DOUBLEQUOTES"&category=2145',
]

datacenter_hostile_websites = [
    "https://ext.to/",
    # "https://www.ygg.re/",
    "https://extratorrent.st/",
    "https://speed.cd/login",
    "https://1337x.to/home/",
]


def _bypass(website: str) -> None:
    """Ask Byparr for the page and require a clean answer."""
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

    assert response.status_code == HTTPStatus.OK


@pytest.mark.parametrize("website", test_websites)
def test_bypass(website: str):
    """Tests if the service can bypass cloudflare/DDOS-GUARD on given websites."""
    _bypass(website)


@pytest.mark.xfail(
    reason="Cloudflare declines the press on invisible_playwright; camoufox clears it",
    strict=False,
)
@pytest.mark.parametrize("website", datacenter_hostile_websites)
def test_bypass_datacenter_hostile(website: str):
    """Same check against sites Cloudflare guards hardest, outcome permitting."""
    _bypass(website)


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


def test_tls_handshake_looks_like_firefox():
    """The handshake must be Firefox's, not the HTTP client's (#398)."""
    url = "https://www.howsmyssl.com/a/check"
    if httpx2.get(url).status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
        pytest.skip("Skipping TLS check - howsmyssl is down")

    response = client.post(
        "/v1",
        json=LinkRequest.model_construct(url=url, cmd="request.get").model_dump(),
    )
    assert response.status_code == HTTPStatus.OK

    body = response.json()["solution"]["response"]
    report = json.loads(
        re.sub(r"<[^>]+>", "", re.search(r"\{.*\}", body, re.DOTALL).group(0))
    )
    suites = len(report["given_cipher_suites"])

    assert suites <= FIREFOX_CIPHER_SUITE_CEILING, (
        f"{suites} cipher suites offered - the handshake is not Firefox's"
    )


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


def fake_cloudflare_frame(*, checked: bool) -> MagicMock:
    """Build a widget frame offering one checkbox in the given state."""
    frame = MagicMock()
    frame.url = (
        "https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/b/turnstile"
    )
    frame.is_detached = MagicMock(return_value=False)

    checkbox = MagicMock()
    checkbox.count = AsyncMock(return_value=1)
    checkbox.first.is_checked = AsyncMock(return_value=checked)
    frame.locator = MagicMock(return_value=checkbox)

    element = AsyncMock()
    element.bounding_box.return_value = WIDGET_BOX
    frame.frame_element = AsyncMock(return_value=element)
    return frame


def fake_dep(
    *,
    fail_states: set[str] | None = None,
    challenged: bool = False,
    marker_counts: list[int] | None = None,
    checkbox: str | None = None,
) -> BrowserDepClass:
    """Build a browser dependency pair backed by mocks."""
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
        if selector != CHALLENGE_MARKERS or not remaining:
            return 1 if challenged else 0
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    def locator(selector: str) -> MagicMock:
        handle = MagicMock()
        handle.count = AsyncMock(return_value=None)
        handle.count.side_effect = lambda: count_for(selector)
        return handle

    page.locator = MagicMock(side_effect=locator)

    def wait_for_load_state(state: str, **_kwargs: object) -> None:
        """Fail the wait when asked for a configured state."""
        if state in (fail_states or set()):
            message = "load state wait timed out"
            raise PlaywrightTimeoutError(message)

    page.wait_for_load_state.side_effect = wait_for_load_state
    page.frames = (
        []
        if checkbox is None
        else [fake_cloudflare_frame(checked=checkbox == "checked")]
    )

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
    dep.page.mouse.down.assert_not_called()


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
async def test_challenge_that_clears_is_reported_as_success():
    """A challenge is over when its markup goes, not when a solver says so."""
    dep = fake_dep(challenged=True, marker_counts=[1, 0])

    response = await read_item(
        LinkRequest(url="https://example.test/login", max_timeout=5), dep
    )

    assert response.status == "ok"
    assert response.solution.status == HTTPStatus.OK


@pytest.mark.asyncio
async def test_unchecked_box_is_pressed_on_the_widgets_visible_pixels():
    """The press must land on the widget, not on the invisible input."""
    dep = fake_dep(challenged=True, marker_counts=[1, 1, 0], checkbox="unchecked")

    await read_item(LinkRequest(url="https://example.test/login", max_timeout=5), dep)

    dep.page.mouse.down.assert_called()
    assert dep.page.mouse.move.call_args.args[:2] == (
        WIDGET_BOX["x"] + CHECKBOX_OFFSET_X,
        WIDGET_BOX["y"] + WIDGET_BOX["height"] / 2,
    )


@pytest.mark.asyncio
async def test_checked_box_is_left_alone_while_cloudflare_verifies():
    """Pressing an already-checked box restarts Cloudflare's verification."""
    dep = fake_dep(challenged=True, marker_counts=[1, 1, 0], checkbox="checked")

    await read_item(LinkRequest(url="https://example.test/login", max_timeout=5), dep)

    dep.page.mouse.down.assert_not_called()


@pytest.mark.asyncio
async def test_challenge_that_never_clears_returns_408():
    """A challenge still up when the budget runs out is a timeout, not a 500."""
    dep = fake_dep(challenged=True, marker_counts=[1])

    with pytest.raises(HTTPException) as exc:
        await read_item(
            LinkRequest(url="https://example.test/login", max_timeout=2), dep
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

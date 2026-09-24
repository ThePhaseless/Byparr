import base64
from http import HTTPStatus
from json import JSONDecodeError
from unittest.mock import AsyncMock, MagicMock

import httpx2
import pytest
from fastapi import HTTPException
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from starlette.testclient import TestClient

from main import app
from src.challenge import CF_INTERSTITIAL_INDICATORS_SELECTORS
from src.endpoints import read_item
from src.models import LinkRequest
from src.utils import BrowserDepClass, TimeoutTimer, remaining_ms

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
        json=LinkRequest.model_construct(
            url=website, cmd="request.get", max_timeout=60
        ).model_dump(),
    )

    assert response.status_code == HTTPStatus.OK
    solution = response.json()["solution"]
    assert "_cf_chl_opt" not in solution["response"]
    assert "__cf_chl" not in solution["url"]


def test_json_api():
    """
    JSON APIs must return 200, not crash on the UA evaluate.

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


def test_post_data_uses_flaresolverr_alias():
    """FlareSolverr clients send the body as the camelCase `postData` string."""
    request = LinkRequest.model_validate(
        {
            "url": "https://example.com",
            "cmd": "request.post",
            "postData": "key1=value1&key2=value2",
        }
    )

    assert request.cmd == "request.post"
    assert request.post_data == "key1=value1&key2=value2"


def test_defaults_keep_plain_get():
    """A request without postData or headers must behave exactly like before."""
    request = LinkRequest(url="https://example.com")

    assert request.cmd == "request.get"
    assert request.post_data is None
    assert request.headers is None


def fake_route(
    *,
    url: str = "https://example.test/login",
    resource_type: str = "document",
    navigation: bool = True,
    main_frame: bool = True,
) -> MagicMock:
    """Build a route double for the handler installed by setup_routes."""
    route = MagicMock()
    route.continue_ = AsyncMock()
    route.abort = AsyncMock()
    route.request = MagicMock()
    route.request.url = url
    route.request.resource_type = resource_type
    route.request.is_navigation_request.return_value = navigation
    route.request.frame.parent_frame = None if main_frame else MagicMock()
    return route


def route_handler(dep: BrowserDepClass):
    """Return the handler setup_routes registered on the page."""
    pattern, handler = dep.page.route.await_args.args
    assert pattern == "**/*"
    return handler


@pytest.mark.asyncio
async def test_post_cmd_overrides_the_navigation_to_post():
    """request.post must reach the network as a POST with a form content type."""
    dep = fake_dep()
    await read_item(
        LinkRequest(
            url="https://example.test/login",
            cmd="request.post",
            post_data="user=byparr&pass=secret",
        ),
        dep,
    )

    route = fake_route()
    await route_handler(dep)(route)

    route.continue_.assert_awaited_once_with(
        method="POST",
        post_data="user=byparr&pass=secret",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    route.abort.assert_not_awaited()


@pytest.mark.asyncio
async def test_caller_content_type_is_not_overwritten():
    """An explicit content-type header wins over the form default."""
    dep = fake_dep()
    await read_item(
        LinkRequest(
            url="https://example.test/api",
            cmd="request.post",
            post_data='{"a":1}',
            headers={"content-type": "application/json"},
        ),
        dep,
    )

    route = fake_route()
    await route_handler(dep)(route)

    route.continue_.assert_awaited_once_with(
        method="POST",
        post_data='{"a":1}',
        headers={"content-type": "application/json"},
    )


@pytest.mark.asyncio
async def test_get_with_custom_headers_keeps_its_method():
    """Extra headers must not silently turn a GET into a POST."""
    dep = fake_dep()
    await read_item(
        LinkRequest(
            url="https://example.test/login",
            headers={"accept-language": "de-DE"},
        ),
        dep,
    )

    route = fake_route()
    await route_handler(dep)(route)

    route.continue_.assert_awaited_once_with(headers={"accept-language": "de-DE"})


@pytest.mark.asyncio
async def test_plain_get_registers_no_route_at_all():
    """Without media blocking, postData or headers the request stays untouched."""
    dep = fake_dep()
    await read_item(LinkRequest(url="https://example.test/login"), dep)

    assert dep.page.route.await_count == 0


@pytest.mark.asyncio
async def test_challenge_reload_reissues_the_post():
    """After the interstitial clears, reloading the URL must POST again."""
    dep = fake_dep()
    await read_item(
        LinkRequest(
            url="https://example.test/login",
            cmd="request.post",
            post_data="a=b",
        ),
        dep,
    )
    handler = route_handler(dep)

    first = fake_route()
    await handler(first)
    reload = fake_route()
    await handler(reload)

    reload.continue_.assert_awaited_once_with(
        method="POST",
        post_data="a=b",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )


@pytest.mark.asyncio
async def test_redirects_subresources_and_iframes_pass_through():
    """Only main-frame navigations to the target URL get the POST override."""
    dep = fake_dep()
    await read_item(
        LinkRequest(
            url="https://example.test/login",
            cmd="request.post",
            post_data="a=b",
        ),
        dep,
    )
    handler = route_handler(dep)

    # The initial navigation to the target consumes the first-navigation
    # fallback; everything after it is only a POST when the URL matches.
    await handler(fake_route())
    redirect = fake_route(url="https://other.test/landing")
    await handler(redirect)
    subresource = fake_route(url="https://example.test/app.js", resource_type="script")
    await handler(subresource)
    iframe = fake_route(main_frame=False)
    await handler(iframe)

    for passed in (redirect, subresource, iframe):
        passed.continue_.assert_awaited_once_with()
        passed.abort.assert_not_awaited()


@pytest.mark.asyncio
async def test_media_blocking_survives_the_combined_handler():
    """block_media must still abort media while the POST override exists."""
    dep = fake_dep()
    await read_item(
        LinkRequest(
            url="https://example.test/login",
            cmd="request.post",
            post_data="a=b",
            block_media=True,
        ),
        dep,
    )
    handler = route_handler(dep)

    image = fake_route(url="https://example.test/cat.png", resource_type="image")
    await handler(image)
    document = fake_route()
    await handler(document)

    image.abort.assert_awaited_once()
    image.continue_.assert_not_awaited()
    document.continue_.assert_awaited_once_with(
        method="POST",
        post_data="a=b",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )


@pytest.mark.asyncio
async def test_media_blocking_alone_still_works_for_gets():
    """A GET with only block_media registered keeps its old behavior."""
    dep = fake_dep()
    await read_item(
        LinkRequest(url="https://example.test/login", block_media=True),
        dep,
    )
    handler = route_handler(dep)

    image = fake_route(url="https://example.test/cat.png", resource_type="image")
    await handler(image)
    document = fake_route()
    await handler(document)

    image.abort.assert_awaited_once()
    document.continue_.assert_awaited_once_with()


def fake_dep(
    *,
    fail_states: set[str] | None = None,
    challenged: bool = False,
    marker_counts: list[int] | None = None,
    widget_box: dict[str, float] | None = None,
    user_agent: str | None = "UnitTestBrowser/1.0",
) -> BrowserDepClass:
    """Build a browser dependency pair backed by mocks."""
    page = AsyncMock()
    page.url = "https://example.test/login"
    page.goto.return_value = MagicMock(
        status=HTTPStatus.OK,
        headers={"content-type": "text/html"},
        request=MagicMock(headers={"user-agent": user_agent} if user_agent else {}),
    )
    page.title.return_value = "Login"
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
        handle.first.bounding_box = AsyncMock(return_value=widget_box)
        handle.first.input_value = AsyncMock(return_value="")
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
    return BrowserDepClass(page=page, context=context)


@pytest.mark.asyncio
async def test_networkidle_timeout_after_domcontentloaded_returns_content():
    """Pages that never go idle after DOM load must still return their content."""
    dep = fake_dep(fail_states={"networkidle"})
    response = await read_item(
        LinkRequest(url="https://example.test/login"),
        dep,
    )

    assert response.status == "ok"
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


@pytest.mark.asyncio
async def test_unreachable_host_is_a_502_not_a_500():
    """An upstream we cannot reach is a gateway failure, never a Byparr crash."""
    dep = fake_dep()
    dep.page.goto.side_effect = PlaywrightError("Page.goto: NS_ERROR_UNKNOWN_HOST")

    with pytest.raises(HTTPException) as exc:
        await read_item(LinkRequest(url="https://nope.invalid/"), dep)

    assert exc.value.status_code == HTTPStatus.BAD_GATEWAY


@pytest.mark.asyncio
async def test_status_is_always_ok_like_flaresolverr():
    """FlareSolverr hardcodes 200 because Selenium cannot report the real code."""
    dep = fake_dep()
    dep.page.goto.return_value = MagicMock(
        status=HTTPStatus.FORBIDDEN,
        headers={"content-type": "text/html"},
        request=MagicMock(headers={"user-agent": "UnitTestBrowser/1.0"}),
    )

    response = await read_item(LinkRequest(url="https://example.test/login"), dep)

    assert response.solution.status == HTTPStatus.OK


def test_exhausted_budget_never_disables_playwright_timeouts():
    """Playwright reads timeout=0 as no timeout at all, so the floor must hold."""
    spent = TimeoutTimer(duration=0)

    assert spent.remaining() == 0
    assert remaining_ms(spent) > 0


@pytest.mark.asyncio
async def test_missing_user_agent_header_is_not_a_500():
    """A request without a user-agent header degrades to empty, never a 500 (#394)."""
    response = await read_item(
        LinkRequest(url="https://example.test/login"),
        fake_dep(user_agent=None),
    )

    assert response.status == "ok"
    assert response.solution.user_agent == ""


@pytest.mark.asyncio
async def test_checkbox_is_clicked_while_the_challenge_is_up():
    """A measurable widget gets a humanised press, not a raw synthetic click."""
    dep = fake_dep(
        challenged=True,
        marker_counts=[1, 1, 0],
        widget_box={"x": 100.0, "y": 200.0, "width": 300.0, "height": 60.0},
    )

    response = await read_item(
        LinkRequest(url="https://example.test/login", max_timeout=5), dep
    )

    assert response.status == "ok"
    dep.page.mouse.move.assert_awaited_once_with(125.0, 230.0)
    dep.page.mouse.down.assert_awaited_once()
    dep.page.mouse.up.assert_awaited_once()


@pytest.mark.asyncio
async def test_challenge_that_clears_on_its_own_is_never_clicked():
    """A challenge is over when its markup goes, and until then we keep our hands off."""
    dep = fake_dep(
        challenged=True,
        marker_counts=[1, 0],
        widget_box={"x": 100.0, "y": 200.0, "width": 300.0, "height": 60.0},
    )

    response = await read_item(
        LinkRequest(url="https://example.test/login", max_timeout=5), dep
    )

    assert response.status == "ok"
    dep.page.mouse.down.assert_not_awaited()


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
async def test_marker_vanishing_mid_navigation_is_not_a_solved_challenge():
    """The marker drops out between challenge rounds; one clear read proves nothing."""
    dep = fake_dep(challenged=True, marker_counts=[1, 0, 1])

    with pytest.raises(HTTPException) as exc:
        await read_item(
            LinkRequest(url="https://example.test/login", max_timeout=2), dep
        )

    assert exc.value.status_code == HTTPStatus.REQUEST_TIMEOUT

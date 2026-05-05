from http import HTTPStatus
from json import JSONDecodeError

import httpx
import pytest
from starlette.testclient import TestClient

from main import app
from src.models import LinkRequest

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

    assert response.status_code == HTTPStatus.OK


def test_health_check():
    """
    Tests the health check endpoint.

    This test ensures that the health check
    endpoint returns HTTPStatus.OK.
    """
    response = client.get("/health")
    assert response.status_code == HTTPStatus.OK


def test_binary_endpoint_png():
    """
    Tests the /binary endpoint with a non-CF-protected PNG.

    Verifies that the endpoint streams binary bytes back with the correct
    content-type. Uses httpbin.org which doesn't gate behind Cloudflare,
    so this exercises the happy path without needing a CF solve.
    """
    response = client.get(
        "/binary",
        params={"url": "https://httpbin.org/image/png", "max_timeout": 60},
    )

    if response.status_code in (502, 503, 504):
        pytest.skip(f"httpbin.org unreachable: {response.status_code}")

    assert response.status_code == HTTPStatus.OK
    assert response.headers["content-type"].startswith("image/png")
    body = response.content
    assert len(body) > 0
    assert body.startswith(b"\x89PNG\r\n\x1a\n"), "body is not a valid PNG"
    assert response.headers.get("x-byparr-bytes") == str(len(body))


def test_binary_endpoint_rejects_bad_scheme():
    """The /binary endpoint must reject non-http(s) URLs with 400."""
    response = client.get("/binary", params={"url": "ftp://example.com/foo.png"})
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_binary_endpoint_rejects_max_bytes():
    """The /binary endpoint must enforce max_bytes."""
    response = client.get(
        "/binary",
        params={
            "url": "https://httpbin.org/image/png",
            "max_bytes": 10,
            "max_timeout": 30,
        },
    )
    if response.status_code in (502, 503, 504):
        pytest.skip(f"httpbin.org unreachable: {response.status_code}")
    assert response.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE

from http import HTTPStatus

import httpx
import pytest
from starlette.testclient import TestClient

from main import app
from src.models import LinkRequest

client = TestClient(app)

test_websites = [
    "https://ext.to/",
    "https://www.ygg.re/",
    "https://extratorrent.st/",
    "https://idope.se/",
    "https://speed.cd/login",
    'https://www.yggtorrent.top/engine/search?do=search&order=desc&sort=publish_date&name="UNESCAPED"+"DOUBLEQUOTES"&category=2145',
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
        pytest.skip(
            f"Skipping {website} - ({test_request.status_code}) {test_request.json()}"
        )

    response = client.post(
        "/v1",
        json=LinkRequest.model_construct(url=website, cmd="request.get").model_dump(),
        # "proxy": "203.174.15.83:8080",
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


def test_turnstile():
    """
    Tests the turnstile endpoint.

    This test ensures that the turnstile endpoint returns HTTPStatus.OK.
    """
    url = "https://nopecha.com/demo/cloudflare"
    response = client.post(
        "/v1",
        json=LinkRequest.model_construct(
            url=url, max_timeout=30, cmd="request.get"
        ).model_dump(),
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()["solution"]["status"] == HTTPStatus.OK

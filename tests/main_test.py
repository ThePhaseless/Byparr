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
        test_request.status_code != HTTPStatus.OK
        and "Just a moment..." not in test_request.text
    ):
        pytest.skip(f"Skipping {website} due to {test_request.status_code}")

    response = client.post(
        "/v1",
        json={
            **LinkRequest.model_construct(
                url=website, max_timeout=30, cmd="request.get"
            ).model_dump(),
            "proxy": "203.174.15.83:8080",
        },
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

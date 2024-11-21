import os
import platform
from http import HTTPStatus
from time import sleep

import httpx
import pytest
from starlette.testclient import TestClient

from main import app
from src.models.requests import LinkRequest

client = TestClient(app)

test_websites = [
    "https://btmet.com/",
    "https://ext.to/",
]

# Not testable on github actions
github_restricted = [
    "https://www.ygg.re/",
    "https://extratorrent.st/",
    "https://idope.se/",
    "https://speed.cd/login",
]

if os.getenv("GITHUB_ACTIONS") == "true":
    test_websites.extend(github_restricted)


@pytest.mark.parametrize("website", test_websites)
def test_bypass(website: str):
    if (platform.machine() == "arm64") and os.getenv("GITHUB_ACTIONS") == "true":
        pytest.skip("Skipping on arm64 due to lack of support")

    sleep(3)
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
        json=LinkRequest(url=website, maxTimeout=30, cmd="request.get").model_dump(),
    )

    assert response.status_code == HTTPStatus.OK


def test_health_check():
    response = client.get("/health")
    assert response.status_code == HTTPStatus.OK

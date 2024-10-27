import os
from http import HTTPStatus
from time import sleep

import httpx
import pytest
from starlette.testclient import TestClient

from main import app
from src.models.requests import LinkRequest
from src.utils import logger

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
    sleep(3)
    test_request = httpx.get(
        website,
    )
    if (
        test_request.status_code != HTTPStatus.OK
        and "Just a moment..." not in test_request.text
    ):
        logger.info(f"Skipping {website} due to {test_request.status_code}")
        pytest.skip()

    response = client.post(
        "/v1",
        json=LinkRequest(url=website, maxTimeout=30, cmd="request.get").model_dump(),
    )

    assert response.status_code == HTTPStatus.OK


def test_health_check():
    response = client.get("/health")
    assert response.status_code == HTTPStatus.OK

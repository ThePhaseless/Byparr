from http import HTTPStatus
from time import sleep

import pytest
from starlette.testclient import TestClient

from main import app
from src.models.requests import LinkRequest

client = TestClient(app)

test_websites = [
    "https://ext.to/",
    "https://btmet.com/",
    "https://extratorrent.st/",  # github is blocking these
    "https://idope.se/",  # github is blocking these
    "https://www.ygg.re/",
    "https://speed.cd/browse/freeleech",
]


@pytest.mark.parametrize("website", test_websites)
def test_bypass(website: str):
    sleep(3)
    response = client.post(
        "/v1",
        json=LinkRequest(url=website, maxTimeout=30, cmd="request.get").model_dump(),
    )
    if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
        # if rate limited
        assert True
    assert response.status_code == HTTPStatus.OK

from http import HTTPStatus

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
]


@pytest.mark.parametrize("website", test_websites)
def test_bypass(website: str):
    response = client.post(
        "/v1",
        json=LinkRequest(
            url=website, maxTimeout=120 * len(test_websites), cmd="request.get"
        ).model_dump(),
    )
    if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
        # if rate limited
        assert True
    assert response.status_code == HTTPStatus.OK

from http import HTTPStatus

import pytest
from starlette.testclient import TestClient

from main import app
from src.models.requests import LinkRequest

client = TestClient(app)

test_websites = [
    "https://ext.to/",
    "https://btmet.com/",
    "https://extratorrent.st/",
    "https://idope.se/",
]


@pytest.mark.parametrize("website", test_websites)
def test_bypass(website: str):
    response = client.post(
        "/v1",
        json=LinkRequest(url=website, maxTimeout=60, cmd="request.get").model_dump(),
    )
    assert response.status_code == HTTPStatus.OK

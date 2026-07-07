from http import HTTPStatus
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from main import app

client = TestClient(app)


def test_owui_load_basic():
    """Test /load endpoint returns correct structure."""
    response = client.post("/load", json={"urls": ["https://example.com"]})
    assert response.status_code == HTTPStatus.OK
    results = response.json()
    assert len(results) == 1
    assert "page_content" in results[0]
    assert "metadata" in results[0]
    assert results[0]["metadata"]["source"] == "https://example.com"


def test_owui_load_multiple_urls():
    """Test /load endpoint handles multiple URLs."""
    urls = ["https://example.com", "https://example.org"]
    response = client.post("/load", json={"urls": urls})
    assert response.status_code == HTTPStatus.OK
    results = response.json()
    assert len(results) == 2
    assert results[0]["metadata"]["source"] == urls[0]
    assert results[1]["metadata"]["source"] == urls[1]


def test_owui_load_extracts_content():
    """Test /load endpoint extracts non-empty content from a real page."""
    response = client.post("/load", json={"urls": ["https://example.com"]})
    assert response.status_code == HTTPStatus.OK
    results = response.json()
    # example.com has minimal content but should have something
    assert len(results[0]["page_content"]) > 0


def test_owui_load_auth_required():
    """Test /load returns 401 when API key is set but not provided."""
    with patch("src.owui._API_KEY", "test-secret-key"):
        response = client.post("/load", json={"urls": ["https://example.com"]})
        assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_owui_load_auth_invalid():
    """Test /load returns 401 when API key is wrong."""
    with patch("src.owui._API_KEY", "test-secret-key"):
        response = client.post(
            "/load",
            json={"urls": ["https://example.com"]},
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_owui_load_auth_valid():
    """Test /load succeeds with correct API key."""
    with patch("src.owui._API_KEY", "test-secret-key"):
        response = client.post(
            "/load",
            json={"urls": ["https://example.com"]},
            headers={"Authorization": "Bearer test-secret-key"},
        )
        assert response.status_code == HTTPStatus.OK


def test_owui_load_invalid_url_graceful():
    """Test /load returns empty content for unreachable URLs."""
    response = client.post(
        "/load", json={"urls": ["https://this-domain-does-not-exist-12345.invalid"]}
    )
    assert response.status_code == HTTPStatus.OK
    results = response.json()
    assert len(results) == 1
    assert results[0]["page_content"] == ""
    assert "this-domain-does-not-exist" in results[0]["metadata"]["source"]

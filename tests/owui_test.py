from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from starlette.testclient import TestClient

from main import app
from src.owui import LoadRequest, load_urls
from src.utils import BrowserDepClass

client = TestClient(app)


def test_owui_load_basic():
    """/load returns one result per URL with the expected shape."""
    response = client.post("/load", json={"urls": ["https://example.com"]})
    assert response.status_code == HTTPStatus.OK
    results = response.json()
    assert len(results) == 1
    assert results[0]["page_content"]
    assert results[0]["metadata"] == {"source": "https://example.com"}


def test_owui_load_multiple_urls():
    """/load returns one result per URL, in order."""
    urls = ["https://example.com", "https://example.org"]
    response = client.post("/load", json={"urls": urls})
    assert response.status_code == HTTPStatus.OK
    results = response.json()
    assert [r["metadata"]["source"] for r in results] == urls


def test_owui_load_invalid_url_graceful():
    """Unreachable URLs yield empty page_content instead of an error."""
    response = client.post(
        "/load", json={"urls": ["https://this-domain-does-not-exist-12345.invalid"]}
    )
    assert response.status_code == HTTPStatus.OK
    results = response.json()
    assert len(results) == 1
    assert results[0]["page_content"] == ""


@pytest.mark.parametrize(
    "headers",
    [None, {"Authorization": "Bearer wrong-key"}],
)
def test_owui_load_rejects_missing_or_wrong_key(headers):
    """/load returns 401 without a valid bearer token when a key is set."""
    with patch("src.owui.OWUI_API_KEY", "test-secret-key"):
        response = client.post(
            "/load", json={"urls": ["https://example.com"]}, headers=headers
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_owui_load_accepts_valid_key():
    """/load succeeds with the configured bearer token."""
    with patch("src.owui.OWUI_API_KEY", "test-secret-key"):
        response = client.post(
            "/load",
            json={"urls": ["https://example.com"]},
            headers={"Authorization": "Bearer test-secret-key"},
        )
        assert response.status_code == HTTPStatus.OK


ARTICLE_HTML = """<html><head><title>Test</title></head><body>
<article><h1>Example Title</h1><p>This is the main article body with enough words for
trafilatura to consider it real content rather than boilerplate.</p></article>
<nav><a href="/x">nav link</a></nav>
</body></html>"""


def fake_dep(*, html: str = ARTICLE_HTML) -> BrowserDepClass:
    """Browser dependency whose page loads HTML but never reaches networkidle."""
    page = AsyncMock()
    page.goto.return_value = MagicMock()
    page.content.return_value = html
    page.evaluate.return_value = "line one\n\nline two"

    def wait_for_load_state(state: str, **_kwargs: object) -> None:
        if state == "networkidle":
            message = "load state wait timed out"
            raise PlaywrightTimeoutError(message)

    page.wait_for_load_state.side_effect = wait_for_load_state
    return BrowserDepClass(page=page, solver=AsyncMock(), context=AsyncMock())


@pytest.mark.asyncio
async def test_networkidle_timeout_still_extracts_content():
    """A page that never reaches networkidle still yields its article text."""
    results = await load_urls(
        LoadRequest(urls=["https://example.test"]), None, fake_dep()
    )
    assert results[0].page_content == (
        "Example TitleThis is the main article body with enough words for "
        "trafilatura to consider it real content rather than boilerplate."
    )


@pytest.mark.asyncio
async def test_extraction_falls_back_to_innertext():
    """Pages trafilatura cannot score fall back to the rendered innerText."""
    results = await load_urls(
        LoadRequest(urls=["https://example.test"]),
        None,
        fake_dep(html="<html><body></body></html>"),
    )
    assert results[0].page_content == "line one\nline two"

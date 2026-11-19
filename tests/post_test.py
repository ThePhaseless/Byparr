import html
import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from starlette.testclient import TestClient

from main import app
from src.models import LinkRequest


class EchoHandler(BaseHTTPRequestHandler):
    """Answer every request with the method, body and cookie it received."""

    def _answer(self) -> None:
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length).decode() if length else ""
        if self.path == "/redirect":
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("location", "/landed")
            self.end_headers()
            return
        payload = json.dumps(
            {
                "method": self.command,
                "path": self.path,
                "body": body,
                "content_type": self.headers.get("content-type"),
                "cookie": self.headers.get("cookie"),
            }
        )
        page = f"<html><body><pre id='echo'>{payload}</pre></body></html>".encode()
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", "text/html")
        self.send_header("content-length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)

    do_GET = do_POST = _answer  # noqa: N815

    def log_message(self, *_args: object) -> None:
        """Keep test output quiet."""


@pytest.fixture(scope="module")
def echo_url():
    """Serve the echo handler on a free local port."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), EchoHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def echoed(response) -> dict:
    """Return what the echo server saw, parsed from the solved page."""
    assert response.status_code == HTTPStatus.OK, response.text
    page = response.json()["solution"]["response"]
    echo = page.split('<pre id="echo">')[1].split("</pre>")[0]
    return json.loads(html.unescape(echo))


def post(echo_url: str, path: str = "/form", **fields: object):
    """Send a /v1 request.post for the echo server."""
    request = LinkRequest.model_construct(
        url=f"{echo_url}{path}", cmd="request.post", max_timeout=60, **fields
    )
    with TestClient(app) as client:
        return client.post(
            "/v1",
            json={
                "cmd": request.cmd,
                "url": request.url,
                "maxTimeout": 60,
                **{
                    {"post_data": "postData"}.get(key, key): value
                    for key, value in fields.items()
                },
            },
        )


def test_request_post_sends_the_form_body(echo_url: str):
    """The POST carries the body and the form content type."""
    seen = echoed(post(echo_url, post_data="username=a&password=b%21"))
    assert seen["method"] == "POST"
    assert seen["body"] == "username=a&password=b%21"
    assert seen["content_type"] == "application/x-www-form-urlencoded"


def test_request_post_sends_the_cookies(echo_url: str):
    """Cookies without a domain apply to the request URL."""
    seen = echoed(
        post(
            echo_url,
            post_data="x=1",
            cookies=[{"name": "sid", "value": "abc"}],
        )
    )
    assert seen["method"] == "POST"
    assert "sid=abc" in seen["cookie"]


def test_request_post_redirect_is_followed_as_get(echo_url: str):
    """A redirect after the POST is followed as a GET."""
    seen = echoed(post(echo_url, path="/redirect", post_data="x=1"))
    assert seen["method"] == "GET"
    assert seen["path"] == "/landed"


def test_request_post_without_post_data_is_rejected(echo_url: str):
    """request.post needs postData."""
    response = post(echo_url)
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_request_get_ignores_post_data(echo_url: str):
    """request.get stays a GET even with postData."""
    request = {"cmd": "request.get", "url": f"{echo_url}/form", "postData": "x=1"}
    with TestClient(app) as client:
        seen = echoed(client.post("/v1", json=request))
    assert seen["method"] == "GET"
    assert seen["body"] == ""


def test_invalid_cookie_is_rejected(echo_url: str):
    """A cookie the browser refuses gives a 400, not a 500."""
    response = post(
        echo_url,
        post_data="x=1",
        cookies=[{"name": "sid", "value": "abc", "sameSite": "Bogus"}],
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST

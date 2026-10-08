import asyncio
import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from invisible_core import SessionGeo, SessionLocale

from src import utils

BERLIN = SessionGeo(
    "Europe/Berlin",
    "203.0.113.7",
    locale=SessionLocale(languages=("de", "en-US", "en"), region="DE"),
)
FAILED = SessionGeo(
    "", None, locale=SessionLocale(languages=("en-US", "en"), region="US")
)


@pytest.fixture(autouse=True)
def fresh_geo_cache(monkeypatch: pytest.MonkeyPatch):
    """Every test starts with nothing resolved."""
    monkeypatch.setattr(utils, "_geo", None)
    monkeypatch.setattr(utils, "_geo_lock", asyncio.Lock())


@pytest.mark.asyncio
async def test_egress_lookup_runs_once_per_process():
    """Concurrent first requests and every later one share a single lookup."""
    with patch("src.utils.prepare_session_geo", return_value=BERLIN) as lookup:
        results = await asyncio.gather(*(utils.get_browser_geo() for _ in range(3)))
        results.append(await utils.get_browser_geo())

    lookup.assert_called_once_with("", None, "auto")
    assert set(results) == {utils.BrowserGeo("Europe/Berlin", "de", math.inf)}


@pytest.mark.asyncio
async def test_failed_lookup_uses_host_timezone_then_retries(
    monkeypatch: pytest.MonkeyPatch,
):
    """A failed lookup is not repaid per request, but is retried later."""
    with (
        patch("src.utils.get_localzone_name", return_value="Asia/Shanghai"),
        patch("src.utils.prepare_session_geo", return_value=FAILED) as lookup,
    ):
        geo = await utils.get_browser_geo()
        assert (geo.timezone, geo.locale) == ("Asia/Shanghai", "en-US")
        await utils.get_browser_geo()
        assert lookup.call_count == 1

        monkeypatch.setattr(utils, "_geo", geo._replace(expires_at=0))
        await utils.get_browser_geo()
        assert lookup.call_count == 2  # noqa: PLR2004


@pytest.mark.asyncio
async def test_failed_lookup_without_a_host_zone_uses_utc():
    """No zone from the host either is what the Docker image has: UTC."""
    with (
        patch("src.utils.get_localzone_name", return_value=None),
        patch("src.utils.prepare_session_geo", return_value=FAILED),
    ):
        geo = await utils.get_browser_geo()

    assert geo.timezone == "UTC"


@pytest.mark.asyncio
async def test_explicit_timezone_and_locale_touch_no_network():
    """BROWSER_TIMEZONE with BROWSER_LOCALE needs neither egress IP nor geoip."""
    with (
        patch("src.utils.BROWSER_TIMEZONE", "Asia/Shanghai"),
        patch("src.utils.BROWSER_LOCALE", "zh-CN"),
        patch("invisible_core._geo.discover_egress_ip") as discover,
        patch("invisible_core.download.ensure_geoip_mmdb") as geoip,
    ):
        geo = await utils.get_browser_geo()

    assert (geo.timezone, geo.locale) == ("Asia/Shanghai", "zh-CN")
    discover.assert_not_called()
    geoip.assert_not_called()


def fake_invisible_playwright() -> MagicMock:
    """Stand-in for InvisiblePlaywright that records how it was built."""
    browser = MagicMock()
    browser.new_context = AsyncMock(return_value=AsyncMock())
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=browser)
    session.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=session)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("proxy_header", "expected"),
    [
        (None, {"timezone": "Europe/Berlin", "locale": "de"}),
        ("socks5://proxy.test:1080", {"timezone": "", "locale": "auto"}),
    ],
)
async def test_proxy_sessions_resolve_their_own_egress(
    proxy_header: str | None, expected: dict[str, str]
):
    """The cache only covers direct sessions; a proxy's egress is its own."""
    launcher = fake_invisible_playwright()
    with (
        patch("src.utils.PROXY_SERVER", None),
        patch("src.utils.InvisiblePlaywright", launcher),
        patch("src.utils.prepare_session_geo", return_value=BERLIN) as lookup,
    ):
        async for _ in utils.get_browser(x_proxy_server=proxy_header):
            pass

    kwargs = launcher.call_args.kwargs
    assert {"timezone": kwargs["timezone"], "locale": kwargs["locale"]} == expected
    assert lookup.called is (proxy_header is None)

# pyright: reportPrivateUsage=false, reportPrivateImportUsage=false
import asyncio
import logging
import math
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import DEFAULT, AsyncMock, MagicMock, patch

import pytest
from invisible_core import GeoTimezoneError, SessionGeo, SessionLocale
from invisible_playwright.async_api import prepare_session_geo

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
def fresh_geo_cache(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Every test starts with nothing resolved and the warm-up already done."""
    monkeypatch.setattr(utils, "_geo", None)
    monkeypatch.setattr(utils, "_geo_lock", asyncio.Lock())
    monkeypatch.setattr(utils, "_warm_lock", asyncio.Lock())
    monkeypatch.setattr(utils, "_warmed", True)
    utils.discover_egress_ip.clear()
    utils.ensure_geoip_mmdb.clear()
    yield
    utils.discover_egress_ip.clear()
    utils.ensure_geoip_mmdb.clear()


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
async def test_raised_lookup_falls_back_to_host_timezone():
    """invisible-core >=49.46 raises on a failed "auto" lookup; it must not escape."""
    with (
        patch("src.utils.get_localzone_name", return_value="Asia/Shanghai"),
        patch(
            "src.utils.prepare_session_geo",
            side_effect=GeoTimezoneError("egress IP discovery failed"),
        ),
    ):
        geo = await utils.get_browser_geo()

    assert (geo.timezone, geo.locale) == ("Asia/Shanghai", "en-US")
    assert geo.expires_at != math.inf  # retried later, like any failed lookup


@pytest.mark.asyncio
async def test_explicit_timezone_and_locale_survive_a_failed_lookup():
    """The egress IP is always looked up now, but explicit values do not need it."""
    with (
        patch("src.utils.BROWSER_TIMEZONE", "Asia/Shanghai"),
        patch("src.utils.BROWSER_LOCALE", "zh-CN"),
        patch.object(
            utils.discover_egress_ip, "lookup", side_effect=OSError("blocked")
        ),
        patch.object(utils.ensure_geoip_mmdb, "lookup") as geoip,
    ):
        geo = await utils.get_browser_geo()

    assert geo == utils.BrowserGeo("Asia/Shanghai", "zh-CN", math.inf)
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


EGRESS_IP = "203.0.113.7"


def test_launches_reuse_one_egress_and_geoip_lookup():
    """Seam guard: the launcher's geo step goes through the remembered lookups."""
    with (
        patch.object(utils.discover_egress_ip, "lookup", return_value=EGRESS_IP) as ip,
        patch.object(
            utils.ensure_geoip_mmdb, "lookup", return_value=Path("geo.mmdb")
        ) as geoip,
        patch("invisible_core._geo.ip_to_coordinates", return_value=(52.5, 13.4)),
    ):
        results = [
            prepare_session_geo("Europe/Berlin", None, "de-DE") for _ in range(3)
        ]

    ip.assert_called_once_with()
    geoip.assert_called_once_with()
    assert {geo.egress_ip for geo in results} == {EGRESS_IP}


def test_failed_lookup_is_skipped_until_the_window_ends(
    monkeypatch: pytest.MonkeyPatch,
):
    """A failure is kept for GEO_RETRY_SECONDS instead of being repaid per launch."""
    with (
        patch.object(
            utils.discover_egress_ip, "lookup", side_effect=GeoTimezoneError("blocked")
        ) as ip,
        patch.object(utils.ensure_geoip_mmdb, "lookup"),
    ):
        for _ in range(2):
            assert prepare_session_geo("UTC", None, "en-US").egress_ip is None
        assert ip.call_count == 1

        monkeypatch.setattr(utils.discover_egress_ip, "retry_seconds", 0)
        utils.discover_egress_ip.clear()
        for _ in range(2):
            prepare_session_geo("UTC", None, "en-US")
        assert ip.call_count == 3  # noqa: PLR2004


def test_failed_geoip_download_is_retried_after_a_short_window():
    """A boot blip is retried within seconds; a lasting outage backs off to 10 minutes."""
    now = time.monotonic()

    def fail_at(offset: float) -> None:
        with (
            patch("src.utils.time.monotonic", return_value=now + offset),
            pytest.raises(RuntimeError),
        ):
            utils.ensure_geoip_mmdb()

    with patch.object(
        utils.ensure_geoip_mmdb, "lookup", side_effect=RuntimeError("offline")
    ) as geoip:
        fail_at(0)
        fail_at(utils.GEOIP_RETRY_SECONDS - 1)
        assert geoip.call_count == 1

        # Each failure doubles the next window until it reaches GEO_RETRY_SECONDS.
        offset, window, calls = 0.0, utils.GEOIP_RETRY_SECONDS, 1
        while window < utils.GEO_RETRY_SECONDS:
            offset += window
            fail_at(offset)
            calls += 1
            window *= 2
            fail_at(offset + min(window, utils.GEO_RETRY_SECONDS) - 1)
            assert geoip.call_count == calls
        offset += utils.GEO_RETRY_SECONDS
        fail_at(offset)
        fail_at(offset + utils.GEO_RETRY_SECONDS - 1)
        assert geoip.call_count == calls + 1

        utils.ensure_geoip_mmdb.clear()
        fail_at(offset)
        fail_at(offset + utils.GEOIP_RETRY_SECONDS)
        assert geoip.call_count == calls + 3
    assert utils.GEOIP_RETRY_SECONDS < utils.GEO_RETRY_SECONDS


def test_long_outage_keeps_raising_the_lookup_error():
    """Thousands of failures with a float window still back off and raise the real error."""
    lookup = utils.RememberedLookup(MagicMock(side_effect=RuntimeError("offline")), 0.5)
    for step in range(1100):
        with (
            patch("src.utils.time.monotonic", return_value=step * 1e6),
            pytest.raises(RuntimeError, match="offline"),
        ):
            lookup()
    assert lookup.lookup.call_count == 1100  # noqa: PLR2004


def test_proxied_egress_lookups_are_not_cached():
    """Each proxy has its own egress, so proxied lookups always pass through."""
    proxy = {"server": "socks5://proxy.test:1080"}
    with patch.object(utils.discover_egress_ip, "lookup", return_value=EGRESS_IP) as ip:
        for _ in range(2):
            assert utils.discover_egress_ip(proxy, timeout=5) == EGRESS_IP
    assert ip.call_count == 2  # noqa: PLR2004
    ip.assert_called_with(proxy, timeout=5)

    with patch.object(
        utils.discover_egress_ip, "lookup", side_effect=GeoTimezoneError("down")
    ) as ip:
        for _ in range(2):
            with pytest.raises(GeoTimezoneError):
                utils.discover_egress_ip(proxy, timeout=5)
    assert ip.call_count == 2  # noqa: PLR2004


def test_concurrent_first_lookups_share_one_request():
    """Threads that ask at once wait for the one lookup already running."""

    def slow_lookup(**_: object) -> str:
        time.sleep(0.05)
        return EGRESS_IP

    with (
        patch.object(utils.discover_egress_ip, "lookup", side_effect=slow_lookup) as ip,
        ThreadPoolExecutor(4) as pool,
    ):
        results = list(pool.map(utils.discover_egress_ip, [None] * 4))

    assert results == [EGRESS_IP] * 4
    assert ip.call_count == 1


async def drain_browser(**kwargs: str | None) -> None:
    """Run get_browser() to the end, as FastAPI does for one request."""
    async for _ in utils.get_browser(**kwargs):
        pass


@pytest.mark.asyncio
async def test_warm_up_runs_once_before_any_browser(monkeypatch: pytest.MonkeyPatch):
    """Concurrent first launches wait for one warm-up instead of each fetching."""
    monkeypatch.setattr(utils, "_warmed", False)

    def slow(value: object) -> Callable[..., object]:
        def lookup(**_: object) -> object:
            time.sleep(0.05)
            return value

        return lookup

    launcher = fake_invisible_playwright()
    seen: list[tuple[bool, int, int]] = []
    with (
        patch("src.utils.PROXY_SERVER", None),
        patch("src.utils.BROWSER_LOCALE", "de-DE"),
        patch("src.utils.InvisiblePlaywright", launcher),
        patch.object(
            utils.discover_egress_ip, "lookup", side_effect=slow(EGRESS_IP)
        ) as ip,
        patch.object(
            utils.ensure_geoip_mmdb, "lookup", side_effect=slow(Path("geo.mmdb"))
        ) as geoip,
        patch("invisible_core._geo.ip_to_coordinates", return_value=(52.5, 13.4)),
        patch("invisible_core._geo.ip_to_timezone", return_value="Europe/Berlin"),
    ):

        def record(**_: object) -> object:
            seen.append((utils._warmed, ip.call_count, geoip.call_count))  # noqa: SLF001
            return DEFAULT

        launcher.side_effect = record
        await asyncio.gather(*(drain_browser() for _ in range(3)))

    ip.assert_called_once_with()
    geoip.assert_called_once_with()
    assert seen == [(True, 1, 1)] * 3
    assert launcher.call_args.kwargs["timezone"] == "Europe/Berlin"


@pytest.mark.asyncio
async def test_failed_warm_up_still_serves_with_the_fallback(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """A failed warm-up logs one warning per fact and browsers use the fallback."""
    monkeypatch.setattr(utils, "_warmed", False)
    caplog.set_level(logging.WARNING, logger="uvicorn.error")
    launcher = fake_invisible_playwright()
    with (
        patch("src.utils.PROXY_SERVER", None),
        patch("src.utils.get_localzone_name", return_value=None),
        patch("src.utils.InvisiblePlaywright", launcher),
        patch.object(
            utils.discover_egress_ip, "lookup", side_effect=GeoTimezoneError("blocked")
        ) as ip,
        patch.object(
            utils.ensure_geoip_mmdb,
            "lookup",
            side_effect=RuntimeError("geoip mmdb unavailable"),
        ) as geoip,
    ):
        await utils.warm_up()
        assert utils._warmed is True  # noqa: SLF001

        messages = [
            r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING
        ]
        assert len([m for m in messages if "GeoIP" in m]) == 1
        assert len([m for m in messages if "timezone" in m]) == 1

        await drain_browser()

    kwargs = launcher.call_args.kwargs
    assert (kwargs["timezone"], kwargs["locale"]) == ("UTC", "en-US")
    assert (ip.call_count, geoip.call_count) == (1, 1)


@pytest.mark.asyncio
async def test_warm_up_skips_the_direct_egress_behind_a_proxy(
    monkeypatch: pytest.MonkeyPatch,
):
    """With PROXY_SERVER set every session is proxied, so the direct IP is unused."""
    monkeypatch.setattr(utils, "_warmed", False)
    with (
        patch("src.utils.PROXY_SERVER", "socks5://proxy.test:1080"),
        patch.object(utils.discover_egress_ip, "lookup") as ip,
        patch.object(
            utils.ensure_geoip_mmdb, "lookup", return_value=Path("geo.mmdb")
        ) as geoip,
    ):
        await utils.warm_up()

    geoip.assert_called_once_with()
    ip.assert_not_called()
    assert utils._geo is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_warm_up_is_a_no_op_once_done(monkeypatch: pytest.MonkeyPatch):
    """The _warmed flag, not the remembered lookup, short-circuits a second call."""
    monkeypatch.setattr(utils, "_warmed", False)
    with (
        patch("src.utils.PROXY_SERVER", None),
        patch("src.utils.prepare_session_geo", return_value=BERLIN),
        patch.object(
            utils.ensure_geoip_mmdb, "lookup", return_value=Path("geo.mmdb")
        ) as geoip,
    ):
        await utils.warm_up()
        utils.ensure_geoip_mmdb.clear()
        await utils.warm_up()

    assert geoip.call_count == 1

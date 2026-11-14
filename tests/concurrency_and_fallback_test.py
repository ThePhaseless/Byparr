from __future__ import annotations

import asyncio
import pytest

from src.browser_manager import BrowserManager
from src.concurrency_advisor import ConcurrencyAdvisor
from src.dynamic_semaphore import DynamicSemaphore
from src.protocol_fallback import ProtocolFallbackManager


def test_protocol_fallback_manager_error_detection():
    manager = ProtocolFallbackManager()

    assert manager.is_http3_error(Exception("Page.goto: NS_ERROR_NET_HTTP3_PROTOCOL_ERROR"))
    assert manager.is_http3_error(Exception("ERR_QUIC_PROTOCOL_ERROR"))
    assert not manager.is_http3_error(Exception("Page.goto: NS_ERROR_UNKNOWN_HOST"))


def test_protocol_fallback_manager_domain_tracking():
    manager = ProtocolFallbackManager()
    url = "https://uindex.org/search.php?q=test"

    assert not manager.requires_http2_fallback(url)

    host = manager.record_http3_failure(url)
    assert host == "uindex.org"
    assert manager.requires_http2_fallback(url)
    assert manager.requires_http2_fallback("https://uindex.org/other-page")
    assert not manager.requires_http2_fallback("https://google.com")


def test_concurrency_advisor_memory_estimation():
    advisor = ConcurrencyAdvisor(byparr_concurrency=5)

    assert advisor.get_memory_estimate_mb(5) == 1250
    assert advisor.get_memory_estimate_gb(5) == pytest.approx(1.22, rel=0.1)

    warning = advisor.generate_memory_warning(10)
    assert "10 sessões simultâneas" in warning
    assert "2500 MB" in warning
    assert "ATENÇÃO" in warning


def test_concurrency_advisor_divergence_evaluation():
    advisor = ConcurrencyAdvisor(byparr_concurrency=6)

    # Divergence: Jackett (3) < Byparr (6) -> Limited by Jackett
    limit, msg = advisor.evaluate_divergence(3)
    assert limit == 3
    assert "LIMITADA PELO JACKETT (3 sessões)" in msg

    # Divergence: Jackett (10) > Byparr (6) -> Limited by Byparr
    limit, msg = advisor.evaluate_divergence(10)
    assert limit == 6
    assert "LIMITADA PELO BYPARR (6 sessões)" in msg

    # Aligned: Jackett (6) == Byparr (6)
    limit, msg = advisor.evaluate_divergence(6)
    assert limit == 6
    assert "Concorrência alinhada" in msg


@pytest.mark.asyncio
async def test_dynamic_semaphore_lifecycle_and_resizing():
    sem = DynamicSemaphore(capacity=2)
    assert sem.capacity == 2
    assert sem.active_count == 0

    # Acquire permits
    await sem.acquire()
    assert sem.active_count == 1
    await sem.acquire()
    assert sem.active_count == 2

    # Dynamically expand capacity
    sem.set_capacity(5)
    assert sem.capacity == 5

    # Should allow acquiring 3 more without blocking
    await sem.acquire()
    assert sem.active_count == 3

    # Release
    await sem.release()
    await sem.release()
    await sem.release()
    assert sem.active_count == 0

    # Context manager test
    async with sem:
        assert sem.active_count == 1
    assert sem.active_count == 0


def test_browser_manager_runtime_update():
    bm = BrowserManager(max_concurrency=4)
    assert bm.max_concurrency == 4

    updated = bm.update_concurrency(12)
    assert updated == 12
    assert bm.max_concurrency == 12
    assert bm._semaphore.capacity == 12

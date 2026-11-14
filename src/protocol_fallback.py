from __future__ import annotations

import logging
from urllib.parse import urlparse

logger = logging.getLogger("uvicorn.error")


class ProtocolFallbackManager:
    """
    Manages HTTP protocol compatibility and intelligent fallback.
    Maintains full HTTP/3 support by default and automatically falls back to
    HTTP/2 only when a target domain triggers an HTTP/3 / QUIC handshake error.
    """

    def __init__(self) -> None:
        self._http3_disabled_hosts: set[str] = set()

    @staticmethod
    def extract_host(url: str) -> str:
        """Extract lowercase host string from URL."""
        try:
            parsed = urlparse(url)
            return (parsed.hostname or "").lower()
        except Exception:
            return ""

    def requires_http2_fallback(self, url: str) -> bool:
        """Check if the given URL's host has previously failed HTTP/3."""
        host = self.extract_host(url)
        return host in self._http3_disabled_hosts

    def record_http3_failure(self, url: str) -> str:
        """Register host as requiring HTTP/2 fallback."""
        host = self.extract_host(url)
        if host and host not in self._http3_disabled_hosts:
            self._http3_disabled_hosts.add(host)
            logger.warning(
                "HTTP/3 protocol error detected for '%s'. Registered host for automatic HTTP/2 fallback.",
                host,
            )
        return host

    @staticmethod
    def is_http3_error(exc: Exception) -> bool:
        """Check if exception message indicates an HTTP/3 / QUIC protocol failure."""
        msg = str(exc)
        return any(
            err in msg
            for err in (
                "NS_ERROR_NET_HTTP3_PROTOCOL_ERROR",
                "HTTP3_PROTOCOL_ERROR",
                "ERR_QUIC_PROTOCOL_ERROR",
                "HTTP3",
            )
        )


protocol_fallback_manager = ProtocolFallbackManager()

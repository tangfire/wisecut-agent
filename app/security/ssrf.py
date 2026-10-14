"""SSRF guard for external URLs used by tools and providers.

All external URLs (product links, material URLs, API endpoints) must pass
this guard before being fetched. The guard checks:
  - Protocol: only http/https allowed
  - Host: not a private/reserved/internal address (IPv4 + IPv6)
  - Port: not a known dangerous port (optional)
  - Blocklist: explicit blocked domains
"""
from __future__ import annotations

import ipaddress
import logging

from app.settings import settings

logger = logging.getLogger(__name__)

# RFC 1918 private ranges + loopback + link-local + unspecified
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

# Ports that should not be reachable from tools
_BLOCKED_PORTS = {22, 23, 25, 3306, 5432, 6379, 5672, 9200, 9300, 11211}


class SSRFValidationError(Exception):
    """Raised when a URL fails SSRF validation."""

    def __init__(self, url: str, reason: str) -> None:
        self.url = url
        self.reason = reason
        super().__init__(f"SSRF validation failed for {url!r}: {reason}")


def validate_external_url(url: str, *, allow_private: bool = False) -> str:
    """Validate a URL for SSRF safety.

    Args:
        url: The URL to validate.
        allow_private: If True, allow private/internal IPs (for local-demo only).

    Returns:
        The validated URL string.

    Raises:
        SSRFValidationError: If the URL is unsafe.
    """
    if not url or not isinstance(url, str):
        raise SSRFValidationError(url or "", "URL is empty or not a string")

    url = url.strip()
    if not url:
        raise SSRFValidationError(url, "URL is empty after stripping")

    if not url.lower().startswith(("http://", "https://")):
        raise SSRFValidationError(url, "URL must use http or https protocol")

    # Parse host
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port
    except Exception as exc:
        raise SSRFValidationError(url, f"URL parse error: {exc}") from exc

    if not host:
        raise SSRFValidationError(url, "URL has no hostname")

    host_lower = host.lower()

    # Check blocklist
    _check_blocklist(host_lower)

    # Resolve to IP and check private ranges
    _check_host_ip(host_lower, allow_private=allow_private)

    # Check blocked ports
    if port is not None and port in _BLOCKED_PORTS:
        raise SSRFValidationError(url, f"Port {port} is blocked for security")

    logger.debug("SSRF validation passed", extra={"url": url, "host": host_lower})
    return url


def _check_blocklist(host: str) -> None:
    """Check host against blocklist."""
    # Strip port if present (shouldn't happen after urlparse, but be safe)
    host = host.split(":")[0].strip("[]")
    blocked = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
    if host in blocked:
        raise SSRFValidationError(host, "Host is in blocklist")


def _check_host_ip(host: str, *, allow_private: bool) -> None:
    """Resolve host to IP and check against private networks."""
    import socket

    host = host.split(":")[0].strip("[]")
    if not host:
        raise SSRFValidationError(host, "Empty host")

    try:
        addr_infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        # DNS resolution failed - in production this should fail;
        # in demo we may allow unresolvable hosts
        if settings.app_env.value != "local-demo":
            raise SSRFValidationError(host, "DNS resolution failed") from None
        return

    for addr_info in addr_infos:
        ip_str = addr_info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified:
            if not allow_private:
                raise SSRFValidationError(
                    host, f"Host resolves to private/internal IP: {ip_str}"
                )

"""Outbound-URL validation for endpoints the service will call.

Deny-by-default: only https URLs to public hosts are allowed. Set
ALLOW_PRIVATE_OUTBOUND_URLS=true to opt in (e.g. local providers, webhooks
inside a private network).

shortcut: DNS-rebinding TOCTOU remains — the IP resolved here can differ from
the one the HTTP client connects to; network egress controls are the real backstop.
"""
import ipaddress
import os
import socket
from urllib.parse import urlparse


def _private_allowed() -> bool:
    return os.environ.get("ALLOW_PRIVATE_OUTBOUND_URLS", "").lower() == "true"


def validate_outbound_url(url: str) -> str:
    """Return the URL if it is safe to fetch, else raise ValueError."""
    allow_private = _private_allowed()

    parsed = urlparse(url)
    if parsed.scheme == "http" and not allow_private:
        raise ValueError("Outbound URLs must use https")
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme!r}")
    if parsed.username or parsed.password:
        raise ValueError("Outbound URLs must not contain userinfo")
    host = parsed.hostname
    if not host:
        raise ValueError("Outbound URL has no host")

    if allow_private:
        return url

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise ValueError(f"Outbound URL host does not resolve: {host}") from e

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise ValueError(f"Outbound URL host resolves to non-public address: {host}")

    return url

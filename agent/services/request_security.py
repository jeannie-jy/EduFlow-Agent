"""Trusted client addressing and same-origin write protection."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from starlette.requests import Request

from config import get_settings


def _trusted_proxy(remote: str) -> bool:
    entries = [item.strip() for item in get_settings().trusted_proxy_ips.split(",") if item.strip()]
    try:
        address = ipaddress.ip_address(remote)
    except ValueError:
        return False
    for entry in entries:
        try:
            if address in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            continue
    return False


def client_ip(request: Request) -> str:
    """Honor X-Forwarded-For only when the direct peer is explicitly trusted."""
    remote = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded and _trusted_proxy(remote):
        candidate = forwarded.split(",", 1)[0].strip()
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            return remote
    return remote


def request_origin(request: Request) -> str | None:
    origin = request.headers.get("origin")
    if origin:
        return origin.rstrip("/")
    referer = request.headers.get("referer")
    if not referer:
        return None
    parsed = urlsplit(referer)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")

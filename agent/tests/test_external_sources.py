"""External URL policy and network-boundary regression checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx
import pytest

from services.external_sources import fetch_external_fingerprint, validate_external_url


@pytest.mark.parametrize("url", [
    "http://www.postgresql.org/docs/16/indexes.html",
    "https://127.0.0.1/docs/16/indexes.html",
    "https://www.postgresql.org.evil.example/docs/16/indexes.html",
    "https://www.postgresql.org:8443/docs/16/indexes.html",
    "https://user@www.postgresql.org/docs/16/indexes.html",
    "https://www.postgresql.org/docs/17/indexes.html",
    "https://www.postgresql.org/docs/16/indexes.html?url=http://localhost/",
    "https://www.postgresql.org/docs/16/../admin",
    "https://www.postgresql.org/docs/16/%2e%2e/admin",
    "https://www.postgresql.org/docs/16/indexes.html#fragment",
])
def test_external_url_rejects_untrusted_or_unversioned_locations(url):
    with pytest.raises(ValueError):
        validate_external_url(url)


def test_external_url_accepts_exact_official_paths():
    assert validate_external_url("https://www.postgresql.org/docs/16/indexes.html") == (
        "https://www.postgresql.org/docs/16/indexes.html"
    )
    assert validate_external_url("https://www.rfc-editor.org/rfc/rfc9110.html") == (
        "https://www.rfc-editor.org/rfc/rfc9110.html"
    )


def test_curated_candidates_are_valid_but_not_preapproved_content():
    path = Path(__file__).resolve().parents[1] / "data" / "external_source_proposals.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["status"] == "candidate_only_not_published"
    assert len(manifest["sources"]) == 2
    for source in manifest["sources"]:
        assert validate_external_url(source["url"]) == source["url"]
        assert source["license_note"] and "summary" not in source


@pytest.mark.asyncio
async def test_fingerprint_stores_hash_only_and_never_follows_redirect():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, text="synthetic official-page fixture", headers={
            "content-type": "text/html", "etag": '"revision-1"',
        })

    value = await fetch_external_fingerprint(
        "https://www.postgresql.org/docs/16/indexes.html",
        transport=httpx.MockTransport(handler),
    )
    assert value.checksum == hashlib.sha256(b"synthetic official-page fixture").hexdigest()
    assert value.etag == '"revision-1"'
    assert calls == ["https://www.postgresql.org/docs/16/indexes.html"]

    def redirect(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://127.0.0.1/internal"})

    with pytest.raises(ValueError, match="HTTP 302"):
        await fetch_external_fingerprint(
            "https://www.postgresql.org/docs/16/indexes.html",
            transport=httpx.MockTransport(redirect),
        )


@pytest.mark.asyncio
async def test_fingerprint_rejects_oversized_or_nontext_response():
    def oversized(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 1_000_001, headers={"content-type": "text/html"})

    with pytest.raises(ValueError, match="size limit"):
        await fetch_external_fingerprint(
            "https://www.postgresql.org/docs/16/indexes.html",
            transport=httpx.MockTransport(oversized),
        )

    def binary(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"binary", headers={"content-type": "application/pdf"})

    with pytest.raises(ValueError, match="text document"):
        await fetch_external_fingerprint(
            "https://www.postgresql.org/docs/16/indexes.html",
            transport=httpx.MockTransport(binary),
        )

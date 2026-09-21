from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware import SecurityMiddleware


def _app():
    app = FastAPI()
    app.add_middleware(SecurityMiddleware)

    @app.post("/api/write")
    async def write():
        return {"ok": True}

    return app


def test_authenticated_cross_origin_write_is_rejected():
    settings = type("Settings", (), {
        "enforce_origin_check": True,
        "public_origin": "https://eduflow.example.com",
        "environment": "production",
    })()
    with patch("config.get_settings", return_value=settings):
        client = TestClient(_app())
        response = client.post(
            "/api/write",
            headers={"Origin": "https://evil.example"},
            cookies={"eduflow_session": "opaque"},
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORIGIN_REJECTED"


def test_same_origin_write_requires_matching_csrf_token():
    settings = type("Settings", (), {
        "enforce_origin_check": True,
        "public_origin": "https://eduflow.example.com",
        "environment": "production",
    })()
    with patch("config.get_settings", return_value=settings):
        client = TestClient(_app())
        client.cookies.set("eduflow_session", "opaque")
        client.cookies.set("eduflow_csrf", "csrf-value")
        missing = client.post("/api/write", headers={"Origin": settings.public_origin})
        accepted = client.post(
            "/api/write",
            headers={"Origin": settings.public_origin, "X-CSRF-Token": "csrf-value"},
        )
    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "CSRF_REJECTED"
    assert accepted.status_code == 200


def test_security_headers_are_applied():
    settings = type("Settings", (), {
        "enforce_origin_check": False,
        "public_origin": "http://localhost:5173",
        "environment": "development",
    })()
    with patch("config.get_settings", return_value=settings):
        response = TestClient(_app()).post("/api/write")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]

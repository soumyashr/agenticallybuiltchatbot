"""
CORS regression tests — added after production incident where frontend
App Runner URL was missing from allow_origins. curl bypasses CORS so
smoke tests never caught this; only discovered when opening the browser UI.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, raise_server_exceptions=False)

FRONTEND_ORIGIN = "https://gazfq7ai7a.ap-south-1.awsapprunner.com"


class TestCORSHeaders:

    def test_preflight_from_frontend_origin(self):
        """Browser preflight (OPTIONS) from the production frontend must be allowed."""
        resp = client.options(
            "/auth/token",
            headers={
                "Origin": FRONTEND_ORIGIN,
                "Access-Control-Request-Method": "POST",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == FRONTEND_ORIGIN

    def test_preflight_from_localhost(self):
        """Preflight from localhost dev server must be allowed."""
        resp = client.options(
            "/auth/token",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"

    def test_cors_rejected_from_unknown_origin(self):
        """Preflight from an unknown origin must NOT echo that origin back."""
        resp = client.options(
            "/auth/token",
            headers={
                "Origin": "https://evil.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert resp.headers.get("access-control-allow-origin") != "https://evil.com"

    def test_actual_request_from_frontend_has_cors_header(self):
        """Actual POST from frontend origin must include CORS header in response."""
        resp = client.post(
            "/auth/token",
            data={"username": "student1", "password": "HMStudent@2024"},
            headers={"Origin": FRONTEND_ORIGIN},
        )
        assert resp.headers.get("access-control-allow-origin") == FRONTEND_ORIGIN

    def test_cors_origins_config_contains_frontend_url(self):
        """Config must contain the frontend URL — fails immediately if removed."""
        from app.config import settings
        assert FRONTEND_ORIGIN in settings.cors_origins

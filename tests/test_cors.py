import httpx
import pytest
from app.core import config as config_module
from app.main import create_app

pytestmark = pytest.mark.asyncio

ORIGIN = "http://localhost:5173"


@pytest.fixture
def cors_client(monkeypatch):
    # CORS is only wired when origins are configured; build a fresh app with one.
    monkeypatch.setattr(config_module.settings, "cors_origins", [ORIGIN])
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_credentialed_cors_headers_present(cors_client):
    async with cors_client as client:
        r = await client.get("/health", headers={"Origin": ORIGIN})
        assert r.headers.get("access-control-allow-origin") == ORIGIN
        assert r.headers.get("access-control-allow-credentials") == "true"


async def test_preflight_is_allowed(cors_client):
    async with cors_client as client:
        r = await client.options(
            "/api/v1/users/me",
            headers={
                "Origin": ORIGIN,
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "x-csrf-token",
            },
        )
        assert r.status_code in (200, 204)
        assert r.headers.get("access-control-allow-origin") == ORIGIN

import pytest
from app.web.spa import spa_is_built

pytestmark = pytest.mark.asyncio

# The SPA bundle is a build artifact (Vite). These tests run only when it has
# been built (CI builds it before the suite); otherwise they skip so an SSR-only
# checkout stays green.
needs_bundle = pytest.mark.skipif(
    not spa_is_built(), reason="SPA bundle not built (run `pnpm -C frontend run build`)"
)


@needs_bundle
async def test_app_root_serves_spa(client):
    r = await client.get("/app")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert '<div id="root">' in r.text


@needs_bundle
async def test_client_route_returns_index(client):
    # A deep link the client router owns must still return index.html.
    r = await client.get("/app/some/client/route")
    assert r.status_code == 200
    assert '<div id="root">' in r.text


@needs_bundle
async def test_assets_are_served(client):
    # index.html references a hashed JS bundle under /app/assets.
    import re

    index = (await client.get("/app")).text
    m = re.search(r'src="(/app/assets/[^"]+)"', index)
    assert m, "expected a hashed asset reference in index.html"
    r = await client.get(m.group(1))
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]

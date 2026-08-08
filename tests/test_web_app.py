import pytest
from httpx import AsyncClient, ASGITransport
from codeguard.web.app import create_app


@pytest.mark.asyncio
async def test_health_endpoint():
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["mode"] == "demo"


@pytest.mark.asyncio
async def test_session_isolation():
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.post("/session", json={"scenario": "a"})
        r2 = await client.post("/session", json={"scenario": "a"})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["session_id"] != r2.json()["session_id"]


@pytest.mark.asyncio
async def test_mock_banner_present():
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert "MOCK" in response.text or "Demo" in response.text

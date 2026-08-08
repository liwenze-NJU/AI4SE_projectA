import pytest
from httpx import AsyncClient, ASGITransport
from codeguard.web.app import create_app


@pytest.mark.asyncio
async def test_dashboard_endpoint_returns_200():
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/dashboard")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_has_state_machine_stepper():
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/dashboard")
    assert response.status_code == 200
    text = response.text.lower()
    assert "initializing" in text or "初始化" in text


@pytest.mark.asyncio
async def test_dashboard_has_three_columns():
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/dashboard")
    assert response.status_code == 200
    text = response.text.lower()
    # Check for state machine timeline, execution trace, guardrail areas
    assert "state" in text or "状态" in text
    assert "trace" in text or "轨迹" in text or "执行" in text
    assert "guardrail" in text or "护栏" in text or "rule" in text or "决策" in text


@pytest.mark.asyncio
async def test_session_state_endpoint():
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a session first
        r = await client.post("/session", json={"scenario": "a"})
        session_id = r.json()["session_id"]
        # Get state
        r2 = await client.get(f"/session/{session_id}/state")
        assert r2.status_code == 200
        data = r2.json()
        assert "state" in data
        assert "scenario" in data


@pytest.mark.asyncio
async def test_dashboard_has_demo_controls():
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/dashboard")
    assert response.status_code == 200
    text = response.text.lower()
    assert "步进" in text or "step" in text or "重放" in text or "replay" in text or "暂停" in text or "pause" in text


@pytest.mark.asyncio
async def test_dashboard_mock_banner_present():
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/dashboard")
    assert response.status_code == 200
    assert "mock" in response.text.lower() or "MOCK" in response.text

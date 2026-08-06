import pytest
from httpx import AsyncClient, ASGITransport
from codeguard.web.app import create_app


@pytest.mark.asyncio
async def test_scenarios_page_has_three_cards():
    """All three scenario cards (A/B/C) must be present on the index page."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    text = response.text
    # Check for all three scenario cards
    assert "路径逃逸" in text or "BLOCK" in text
    assert "审批" in text or "Scenario B" in text
    assert "反馈" in text or "Scenario C" in text or "修复" in text


@pytest.mark.asyncio
async def test_mock_banner_visible():
    """The mock banner must be visible on the index page."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    text = response.text.lower()
    assert "mock" in text


@pytest.mark.asyncio
async def test_scenario_page_has_teaching_intro():
    """The index page must have a teaching introduction section."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert "Harness" in response.text or "Agent" in response.text or "机制" in response.text


@pytest.mark.asyncio
async def test_mock_banner_not_closable():
    """The mock banner must NOT have a close/dismiss button."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    text = response.text
    # Banner should NOT have a close button
    assert "close" not in text.lower()
    assert "dismiss" not in text.lower()
    assert "×" not in text


@pytest.mark.asyncio
async def test_scenario_entry_redirects_to_dashboard():
    """Scenario card entry (`/session?scenario=a`) must not 404."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        response = await client.get("/session?scenario=a")
    assert response.status_code in (302, 303, 307)
    assert "/dashboard" in response.headers.get("location", "")

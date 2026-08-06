import pytest
from httpx import AsyncClient, ASGITransport
from codeguard.web.app import create_app


@pytest.mark.asyncio
async def test_results_shows_memory_types():
    """Results page must show memory summary entries."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/results")
    assert response.status_code == 200
    assert "memory" in response.text.lower() or "convention" in response.text.lower()


@pytest.mark.asyncio
async def test_results_shows_trace():
    """Results page must show a trace log."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/results")
    assert "trace" in response.text.lower() or "step" in response.text.lower()


@pytest.mark.asyncio
async def test_results_shows_final_state():
    """Results page must show the terminal state."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/results")
    assert response.status_code == 200
    text = response.text
    assert "COMPLETED" in text or "FAILED" in text or "CANCELLED" in text or "LIMIT" in text


@pytest.mark.asyncio
async def test_results_shows_guardrail_counts():
    """Results page must summarize guardrail decisions (ALLOW/BLOCK/APPROVAL)."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/results")
    assert response.status_code == 200
    text = response.text.upper()
    assert "ALLOW" in text
    assert "BLOCK" in text


@pytest.mark.asyncio
async def test_results_has_navigation_actions():
    """Results page must offer back-to-scenarios and replay actions."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/results")
    assert response.status_code == 200
    text = response.text
    assert ("返回" in text or "/" in text) and ("重放" in text or "replay" in text.lower())

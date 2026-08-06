import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from codeguard.web.app import create_app


@pytest.mark.asyncio
async def test_mock_banner_always_visible():
    """Mock banner must be visible on every page."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for path in ["/", "/dashboard", "/approval", "/results"]:
            response = await client.get(path)
            assert response.status_code == 200, path
            assert "MOCK" in response.text or "mock" in response.text.lower()


@pytest.mark.asyncio
async def test_no_real_components_accessible():
    """Demo mode must report mock boundary and never expose real components."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    data = response.json()
    assert data["mock"] is True
    assert data["mode"] == "demo"


def test_web_app_imports_no_real_components():
    """The WebUI app module must not import real external-boundary components.

    SPEC §3.9 safety boundary: DemoCompositionRoot must not import real
    DeepSeekAdapter, KeyringCredentialStore, LocalToolExecutor or network clients.
    """
    source = (Path(__file__).parent.parent / "codeguard/web/app.py").read_text(encoding="utf-8")
    for forbidden in ("deepseek", "DeepSeekAdapter", "keyring", "KeyringCredentialStore",
                      "LocalToolExecutor", "requests", "openai"):
        assert forbidden not in source, f"web app must not import {forbidden}"

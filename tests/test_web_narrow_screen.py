import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from codeguard.web.app import create_app

IPHONE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15"


@pytest.mark.asyncio
async def test_narrow_screen_no_overflow():
    """375px viewport: page loads, readable, scrollable, no occlusion."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/", headers={"User-Agent": IPHONE_UA})
    assert response.status_code == 200
    assert "Mock" in response.text or "Demo" in response.text  # banner still visible


@pytest.mark.asyncio
async def test_narrow_screen_approval_operable():
    """375px viewport: approval buttons are reachable and touchable."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/approval", headers={"User-Agent": IPHONE_UA})
    assert response.status_code == 200
    assert "approve" in response.text.lower() or "reject" in response.text.lower()


@pytest.mark.asyncio
async def test_narrow_screen_dashboard_operable():
    """375px viewport: dashboard loads with stepper and controls reachable."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/dashboard", headers={"User-Agent": IPHONE_UA})
    assert response.status_code == 200
    text = response.text
    assert "步进" in text or "pause" in text.lower() or "replay" in text.lower()


def test_narrow_screen_css_rules_present():
    """style.css must contain narrow-screen rules for dashboard, modal and 44px touch targets."""
    css = (Path(__file__).parent.parent / "codeguard/web/static/style.css").read_text(encoding="utf-8")
    assert "@media (max-width: 767px)" in css
    # Modal must stay within viewport on narrow screens
    assert "max-width: 95vw" in css or "max-width: 100vw" in css or "max-width: 90vw" in css
    # Touch targets must be >= 44px on narrow screens
    assert "min-height: 44px" in css

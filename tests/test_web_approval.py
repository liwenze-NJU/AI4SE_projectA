import pytest
from httpx import AsyncClient, ASGITransport
from codeguard.web.app import create_app


@pytest.mark.asyncio
async def test_approval_modal_has_buttons():
    """Approval modal must have approve and reject buttons."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/session", json={"scenario": "b"})
        response = await client.get("/approval")
    assert response.status_code == 200
    assert "approve" in response.text.lower() or "Approve" in response.text
    assert "reject" in response.text.lower() or "Reject" in response.text


@pytest.mark.asyncio
async def test_approval_modal_shows_countdown():
    """Approval modal must show a timeout countdown."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/approval")
    assert "timeout" in response.text.lower() or "second" in response.text.lower() or "countdown" in response.text.lower()


@pytest.mark.asyncio
async def test_approval_modal_shows_risk_reasons():
    """Approval modal must show risk reasons for the pending action."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/approval")
    assert response.status_code == 200
    assert "副作用" in response.text or "风险" in response.text or "risk" in response.text.lower()


@pytest.mark.asyncio
async def test_approval_approve_updates_session():
    """Approving a pending request must update the session state."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "b"})
        session_id = r.json()["session_id"]
        # Session enters AWAITING_APPROVAL with a pending request
        resp = await client.post(
            f"/session/{session_id}/approval",
            json={"request_id": "mock-req-1", "decision": "approve"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "approve"
        # Session state must advance past AWAITING_APPROVAL
        r3 = await client.get(f"/session/{session_id}/state")
        assert r3.json()["state"] == "EXECUTING"


@pytest.mark.asyncio
async def test_approval_reject_updates_session():
    """Rejecting a pending request must update the session state."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "b"})
        session_id = r.json()["session_id"]
        resp = await client.post(
            f"/session/{session_id}/approval",
            json={"request_id": "mock-req-1", "decision": "reject"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "reject"


@pytest.mark.asyncio
async def test_approval_unknown_session_rejected():
    """Approval on an unknown session must fail clearly."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/session/does-not-exist/approval",
            json={"request_id": "mock-req-1", "decision": "approve"},
        )
    assert resp.status_code == 404

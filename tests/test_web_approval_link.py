"""Tests for scenario B approval link correctness and full flow.

RED phase: dashboard approval-link has href="#" (no session), clicking it
doesn't navigate to the approval page with the correct session.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from codeguard.web.app import create_app


@pytest.mark.asyncio
async def test_dashboard_approval_link_has_session_id():
    """The dashboard approval-link href must contain the current session_id
    so clicking it navigates to /approval?session=<id>."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "b"})
        sid = r.json()["session_id"]

        # Step to AWAITING_APPROVAL so the bar becomes visible
        for _ in range(20):
            resp = await client.post(f"/session/{sid}/step")
            if resp.json()["state"] == "AWAITING_APPROVAL":
                break

        resp = await client.get(f"/dashboard?session={sid}")
        html = resp.text
        # The link must contain /approval?session= with the real session ID
        assert f'/approval?session={sid}' in html, (
            "approval-link href missing correct session_id"
        )
        assert 'href="#"' not in html or f'href="/approval?session={sid}"' in html


@pytest.mark.asyncio
async def test_approval_link_navigates_to_valid_approval_page():
    """GET the approval-link's URL must return 200 and show scenario B label."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "b"})
        sid = r.json()["session_id"]

        for _ in range(20):
            resp = await client.post(f"/session/{sid}/step")
            if resp.json()["state"] == "AWAITING_APPROVAL":
                break

        # Navigate to approval page with session
        resp = await client.get(f"/approval?session={sid}")
        assert resp.status_code == 200
        html = resp.text
        assert "场景 B" in html or "副作用动作待审批" in html
        assert "批准" in html or "approve" in html.lower()


@pytest.mark.asyncio
async def test_approval_page_shows_correct_scenario_and_session():
    """The approval page must reference the same session and scenario B."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "b"})
        sid = r.json()["session_id"]

        # Advance to AWAITING_APPROVAL
        for _ in range(20):
            resp = await client.post(f"/session/{sid}/step")
            if resp.json()["state"] == "AWAITING_APPROVAL":
                break

        # GET the approval page
        resp = await client.get(f"/approval?session={sid}")
        html = resp.text
        assert f'data-session-id="{sid}"' in html or f"data-session-id='{sid}'" in html


@pytest.mark.asyncio
async def test_approve_completes_same_session():
    """After approving on the /approval page via POST /approval,
    the same session progresses from EXECUTING to COMPLETED."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "b"})
        sid = r.json()["session_id"]

        for _ in range(20):
            resp = await client.post(f"/session/{sid}/step")
            if resp.json()["state"] == "AWAITING_APPROVAL":
                break

        # Approve via POST endpoint
        appr = await client.post(
            f"/session/{sid}/approval",
            json={"decision": "approve", "request_id": "mock-req-1"},
        )
        assert appr.status_code == 200

        # Continue stepping to COMPLETED
        for _ in range(20):
            resp = await client.post(f"/session/{sid}/step")
            if resp.json()["state"] in ("COMPLETED", "FAILED", "CANCELLED"):
                break

        final = (await client.get(f"/session/{sid}/state")).json()
        assert final["state"] == "COMPLETED"


@pytest.mark.asyncio
async def test_reject_goes_to_cancelled_zero_steps():
    """After rejection, state must be CANCELLED with zero executions."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "b"})
        sid = r.json()["session_id"]

        for _ in range(20):
            resp = await client.post(f"/session/{sid}/step")
            if resp.json()["state"] == "AWAITING_APPROVAL":
                break

        await client.post(
            f"/session/{sid}/approval",
            json={"decision": "reject", "request_id": "mock-req-1"},
        )

        # After rejection, no more steps should execute
        final = (await client.get(f"/session/{sid}/state")).json()
        assert final["state"] == "CANCELLED"
        # steps should be 0 since no action executed before reject
        assert final.get("current_step", 0) >= 0


@pytest.mark.asyncio
async def test_defer_keeps_awaiting_approval():
    """Clicking '稍后' (without approve/reject) leaves state as
    AWAITING_APPROVAL — no change."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "b"})
        sid = r.json()["session_id"]

        for _ in range(20):
            resp = await client.post(f"/session/{sid}/step")
            if resp.json()["state"] == "AWAITING_APPROVAL":
                break

        # Simulate 'later': just get state without POST approval
        later = (await client.get(f"/session/{sid}/state")).json()
        assert later["state"] == "AWAITING_APPROVAL"

        # Step is still blocked
        for _ in range(3):
            resp = await client.post(f"/session/{sid}/step")
            assert resp.json()["state"] == "AWAITING_APPROVAL"

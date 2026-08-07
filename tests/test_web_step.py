"""Tests for WebUI step, replay, polling, session isolation, and timeline reset.

RED phase: all tests should fail because:

- POST /session/{id}/step and /replay don't exist yet
- Scenario A/B/C replay data isn't wired into sessions
- updateTimeline() doesn't clear old markers on reset
"""

import pytest
from httpx import AsyncClient, ASGITransport
from codeguard.web.app import create_app


@pytest.mark.asyncio
async def test_step_advances_state_on_backend():
    """Clicking step should advance backend state, not just local JS."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create session for scenario A
        r = await client.post("/session", json={"scenario": "a"})
        session_id = r.json()["session_id"]
        assert r.status_code == 200

        # Before step: INITIALIZING
        r0 = await client.get(f"/session/{session_id}/state")
        assert r0.json()["state"] == "INITIALIZING"

        # Step 1
        r1 = await client.post(f"/session/{session_id}/step")
        assert r1.status_code == 200
        assert r1.json()["state"] != "INITIALIZING"

        # Step 2
        r2 = await client.post(f"/session/{session_id}/step")
        assert r2.status_code == 200
        state2 = r2.json()["state"]
        assert state2 != r1.json()["state"]


@pytest.mark.asyncio
async def test_polling_does_not_reset_stepped_state():
    """After step advances state, GET /state should return the advanced state,
    not reset it to INITIALIZING."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "a"})
        session_id = r.json()["session_id"]

        # Advance
        await client.post(f"/session/{session_id}/step")
        stepped = (await client.post(f"/session/{session_id}/step")).json()["state"]

        # Polling: should return stepped state, not INITIALIZING
        polled = (await client.get(f"/session/{session_id}/state")).json()
        assert polled["state"] == stepped
        assert polled["state"] != "INITIALIZING"


@pytest.mark.asyncio
async def test_replay_resets_frontend_and_backend():
    """Replay should reset both frontend and backend to INITIALIZING
    and start fresh."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "a"})
        session_id = r.json()["session_id"]

        # Advance a few steps
        await client.post(f"/session/{session_id}/step")
        await client.post(f"/session/{session_id}/step")

        # Replay
        rep = await client.post(f"/session/{session_id}/replay")
        assert rep.status_code == 200

        # Backend must reset
        state_data = await client.get(f"/session/{session_id}/state")
        assert state_data.json()["state"] == "INITIALIZING"
        assert state_data.json()["current_step"] == 0


@pytest.mark.asyncio
async def test_replay_clears_trace_and_guardrail():
    """When replaying, trace and guardrail_decisions must be cleared."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "a"})
        session_id = r.json()["session_id"]

        # Step until we have guardrail decisions (scenario A has 2)
        for _ in range(10):
            s = await client.post(f"/session/{session_id}/step")
            sdata = s.json()
            if sdata.get("guardrail_decisions"):
                break

        # Verify we have decisions
        state_before = await client.get(f"/session/{session_id}/state")
        assert len(state_before.json().get("guardrail_decisions", [])) > 0

        # Replay
        await client.post(f"/session/{session_id}/replay")

        # Verify cleared
        state_after = await client.get(f"/session/{session_id}/state")
        assert len(state_after.json().get("guardrail_decisions", [])) == 0
        assert len(state_after.json().get("trace", [])) == 0


@pytest.mark.asyncio
async def test_scenario_a_reaches_completed():
    """Scenario A should complete: BLOCK -> feedback -> safe action -> COMPLETED."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "a"})
        session_id = r.json()["session_id"]

        terminal_states = {"COMPLETED", "FAILED", "CANCELLED", "LIMIT_REACHED"}
        for _ in range(30):
            resp = await client.post(f"/session/{session_id}/step")
            s = resp.json()["state"]
            if s in terminal_states:
                break

        final = (await client.get(f"/session/{session_id}/state")).json()
        assert final["state"] == "COMPLETED"


@pytest.mark.asyncio
async def test_scenario_b_approval_stuck_then_approve():
    """Scenario B: step until AWAITING_APPROVAL, then approve -> COMPLETED."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "b"})
        session_id = r.json()["session_id"]

        # Step until AWAITING_APPROVAL
        for _ in range(20):
            resp = await client.post(f"/session/{session_id}/step")
            if resp.json()["state"] == "AWAITING_APPROVAL":
                break

        state = (await client.get(f"/session/{session_id}/state")).json()
        assert state["state"] == "AWAITING_APPROVAL"

        # Approve
        appr_resp = await client.post(
            f"/session/{session_id}/approval",
            json={"decision": "approve", "request_id": "mock-req-1"},
        )
        assert appr_resp.status_code == 200

        # Continue stepping after approval
        terminal_states = {"COMPLETED", "FAILED", "CANCELLED", "LIMIT_REACHED"}
        for _ in range(20):
            resp = await client.post(f"/session/{session_id}/step")
            if resp.json()["state"] in terminal_states:
                break

        final = (await client.get(f"/session/{session_id}/state")).json()
        assert final["state"] == "COMPLETED"


@pytest.mark.asyncio
async def test_scenario_b_reject_oes_to_cancelled():
    """Scenario B: reject leads to CANCELLED with zero executions."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "b"})
        session_id = r.json()["session_id"]

        for _ in range(20):
            resp = await client.post(f"/session/{session_id}/step")
            if resp.json()["state"] == "AWAITING_APPROVAL":
                break

        await client.post(
            f"/session/{session_id}/approval",
            json={"decision": "reject", "request_id": "mock-req-1"},
        )

        final = (await client.get(f"/session/{session_id}/state")).json()
        assert final["state"] == "CANCELLED"


@pytest.mark.asyncio
async def test_scenario_c_has_feedback_cycle():
    """Scenario C should show: first FAILED -> feedback -> repair -> COMPLETED."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "c"})
        session_id = r.json()["session_id"]

        terminal_states = {"COMPLETED", "FAILED", "CANCELLED", "LIMIT_REACHED"}
        for _ in range(30):
            resp = await client.post(f"/session/{session_id}/step")
            if resp.json()["state"] in terminal_states:
                break

        final = (await client.get(f"/session/{session_id}/state")).json()
        assert final["state"] == "COMPLETED"
        # Scenario C has feedback_results
        feedback = final.get("feedback_results", [])
        assert len(feedback) >= 2
        assert any("FAILED" in str(f.get("status", "")) for f in feedback)
        assert any("PASSED" in str(f.get("status", "")) for f in feedback)


@pytest.mark.asyncio
async def test_sessions_are_isolated():
    """Two sessions should not interfere with each other."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.post("/session", json={"scenario": "a"})
        r2 = await client.post("/session", json={"scenario": "a"})
        sid1 = r1.json()["session_id"]
        sid2 = r2.json()["session_id"]
        assert sid1 != sid2

        # Step session 1
        await client.post(f"/session/{sid1}/step")
        s1 = (await client.get(f"/session/{sid1}/state")).json()
        # Session 2 should still be INITIALIZING
        s2 = (await client.get(f"/session/{sid2}/state")).json()
        assert s1["state"] != "INITIALIZING"
        assert s2["state"] == "INITIALIZING"


@pytest.mark.asyncio
async def test_step_returns_trace_and_guardrail_in_response():
    """Each step response should include updated trace and guardrail_decisions."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "a"})
        session_id = r.json()["session_id"]

        for _ in range(15):
            resp = await client.post(f"/session/{session_id}/step")
            data = resp.json()
            if data.get("guardrail_decisions"):
                assert isinstance(data["guardrail_decisions"], list)
                assert len(data["guardrail_decisions"]) > 0
                assert isinstance(data["trace"], list)
                assert data["state"] != "INITIALIZING"
                return

        pytest.fail("never received guardrail_decisions from step endpoint")


@pytest.mark.asyncio
async def test_step_without_session_returns_404():
    """Stepping a nonexistent session should return 404."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session/bad-id-12345/step")
        assert r.status_code == 404

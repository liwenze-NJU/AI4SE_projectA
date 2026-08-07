"""Tests for terminal-state button UX and Scenario C feedback-loop trace display.

RED phase — expected failures:
1. Terminal states don't disable step/pause buttons
2. CANCELLED page has no rejection explanation
3. Scenario C trace doesn't show FAILED/PASSED on INTERMEDIATE_VALIDATION frames
"""

import pytest
from httpx import AsyncClient, ASGITransport
from codeguard.web.app import create_app


# ---------------------------------------------------------------------------
# Group 1: Terminal-state button behaviour
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_terminal_state_disables_step_button():
    """After reaching COMPLETED, the step endpoint must not advance further."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "a"})
        sid = r.json()["session_id"]

        for _ in range(30):
            resp = await client.post(f"/session/{sid}/step")
            if resp.json()["state"] == "COMPLETED":
                break

        # Try stepping further — state must remain COMPLETED
        for _ in range(3):
            resp = await client.post(f"/session/{sid}/step")
            assert resp.json()["state"] == "COMPLETED"


@pytest.mark.asyncio
async def test_cancelled_state_does_not_advance():
    """After CANCELLED, step must not advance."""
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

        final = (await client.get(f"/session/{sid}/state")).json()
        assert final["state"] == "CANCELLED"

        for _ in range(3):
            resp = await client.post(f"/session/{sid}/step")
            assert resp.json()["state"] == "CANCELLED"


@pytest.mark.asyncio
async def test_replay_from_terminal_resets_and_enables_stepping():
    """After replay from a terminal state, step must work again."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "a"})
        sid = r.json()["session_id"]

        for _ in range(30):
            resp = await client.post(f"/session/{sid}/step")
            if resp.json()["state"] == "COMPLETED":
                break

        # Replay
        rep = await client.post(f"/session/{sid}/replay")
        assert rep.json()["state"] == "INITIALIZING"

        # Step should advance again
        s1 = await client.post(f"/session/{sid}/step")
        assert s1.json()["state"] != "INITIALIZING"


# ---------------------------------------------------------------------------
# Group 2: Scenario C feedback-loop trace display
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_c_first_intermediate_validation_is_failed():
    """The first INTERMEDIATE_VALIDATION frame in scenario C must have
    failed=True and failure_category ~ TEST."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "c"})
        sid = r.json()["session_id"]

        iv_count = 0
        for _ in range(30):
            resp = await client.post(f"/session/{sid}/step")
            s = resp.json()
            # check trace for INTERMEDIATE_VALIDATION entries
            for t in s.get("trace", []):
                if t.get("to", "").upper() == "INTERMEDIATE_VALIDATION":
                    iv_count += 1
                    if iv_count == 1:
                        assert t.get("failed") is True, (
                            "first INTERMEDIATE_VALIDATION must be failed"
                        )
                        cat = t.get("failure_category", "")
                        assert "TEST" in cat.upper() or "ASSERTION" in cat.upper()
                        return
            if s["state"] == "COMPLETED":
                break

        pytest.fail("never saw failed INTERMEDIATE_VALIDATION in scenario C trace")


@pytest.mark.asyncio
async def test_scenario_c_second_intermediate_validation_is_passed():
    """The second INTERMEDIATE_VALIDATION in scenario C must NOT be failed."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "c"})
        sid = r.json()["session_id"]

        iv_entries = []
        for _ in range(30):
            resp = await client.post(f"/session/{sid}/step")
            s = resp.json()
            for t in s.get("trace", []):
                if (t.get("to", "").upper() == "INTERMEDIATE_VALIDATION"
                        and t not in iv_entries):
                    iv_entries.append(t)
            if s["state"] == "COMPLETED":
                break

        assert len(iv_entries) >= 2, (
            f"expected >=2 INTERMEDIATE_VALIDATION, got {len(iv_entries)}"
        )
        assert iv_entries[0].get("failed") is True
        assert iv_entries[1].get("failed") is not True


@pytest.mark.asyncio
async def test_scenario_c_feedback_summary_in_state_response():
    """After COMPLETED, GET /state must return feedback_results with both
    FAILED and PASSED entries."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "c"})
        sid = r.json()["session_id"]

        for _ in range(30):
            resp = await client.post(f"/session/{sid}/step")
            if resp.json()["state"] == "COMPLETED":
                break

        final = (await client.get(f"/session/{sid}/state")).json()
        fb = final.get("feedback_results", [])
        assert len(fb) >= 2
        statuses = [f.get("status", "") for f in fb]
        assert any("FAILED" in s.upper() for s in statuses), (
            f"no FAILED in feedback_results: {fb}"
        )
        assert any("PASSED" in s.upper() for s in statuses), (
            f"no PASSED in feedback_results: {fb}"
        )

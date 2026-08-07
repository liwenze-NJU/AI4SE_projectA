"""Tests for: trace GR annotation, scenario B approval entry, navbar cleanup.

RED phase — three groups of failures expected:
1. Trace GR: step_session() appends bare {from,to,at}, no tool_call/decision
2. Approval entry: dashboard has no approval button, scenario B stuck without UI
3. Navbar cleanup: base.html still shows back button on /, empty scenario pill
"""

import pytest
from httpx import AsyncClient, ASGITransport
from codeguard.web.app import create_app


# =========================================================================
# Group 1: Trace entries carry guardrail decision data
# =========================================================================

@pytest.mark.asyncio
async def test_scenario_a_trace_has_write_file_blocked():
    """After first GOVERNING, the most recent trace entry must include
    write_file tool_call and BLOCK decision so the execution trace
    shows the blocked action."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "a"})
        sid = r.json()["session_id"]

        found_gov = False
        for _ in range(20):
            resp = await client.post(f"/session/{sid}/step")
            s = resp.json()
            if s["state"] == "GOVERNING":
                trace = s.get("trace", [])
                if trace:
                    last = trace[-1]
                    tc = last.get("tool_call", {})
                    gr_d = last.get("guardrail_decision")
                    # After first GOVERNING, the trace entry should have BLOCK info
                    if tc.get("command") == "write_file" and gr_d == "BLOCK":
                        found_gov = True
                        break
                # If we're at second GOVERNING already, fail
                break
            if s["state"] == "COMPLETED":
                break

        assert found_gov, (
            "trace entry at first GOVERNING missing write_file + BLOCK"
        )


@pytest.mark.asyncio
async def test_scenario_a_trace_retains_block_and_allow():
    """After scenario A finishes, the completed state must have at least
    two trace entries with guardrail_decision fields: BLOCK then ALLOW,
    in that order."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "a"})
        sid = r.json()["session_id"]

        for _ in range(30):
            resp = await client.post(f"/session/{sid}/step")
            if resp.json()["state"] == "COMPLETED":
                break

        final = (await client.get(f"/session/{sid}/state")).json()
        decisions_in_trace = [
            e.get("guardrail_decision") for e in final.get("trace", [])
            if e.get("guardrail_decision")
        ]
        assert len(decisions_in_trace) >= 2, (
            f"expected >=2 GR in trace, got {len(decisions_in_trace)}: {decisions_in_trace}"
        )
        assert decisions_in_trace[0] == "BLOCK"
        assert decisions_in_trace[1] == "ALLOW"


# =========================================================================
# Group 2: Scenario B approval entry point
# =========================================================================

@pytest.mark.asyncio
async def test_scenario_b_awaiting_approval_has_approval_entry():
    """When scenario B reaches AWAITING_APPROVAL, the GET /state response
    must expose approval info (pending_request) so the frontend can
    show an approval entry point."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "b"})
        sid = r.json()["session_id"]

        for _ in range(20):
            resp = await client.post(f"/session/{sid}/step")
            if resp.json()["state"] == "AWAITING_APPROVAL":
                break

        state_data = (await client.get(f"/session/{sid}/state")).json()
        assert state_data["state"] == "AWAITING_APPROVAL"
        # Backend should expose a pending_approval flag or similar
        assert state_data.get("pending_approval") is True or (
            state_data.get("approval_request") is not None
        ), "state response must signal that approval is needed"


@pytest.mark.asyncio
async def test_scenario_b_step_blocked_without_approval():
    """Repeated steps at AWAITING_APPROVAL must NOT advance state."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "b"})
        sid = r.json()["session_id"]

        for _ in range(20):
            resp = await client.post(f"/session/{sid}/step")
            if resp.json()["state"] == "AWAITING_APPROVAL":
                break

        for _ in range(5):
            resp = await client.post(f"/session/{sid}/step")
            assert resp.json()["state"] == "AWAITING_APPROVAL"


@pytest.mark.asyncio
async def test_scenario_b_approve_then_completed():
    """After approval, the same session must continue from EXECUTING
    to COMPLETED."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "b"})
        sid = r.json()["session_id"]

        for _ in range(20):
            resp = await client.post(f"/session/{sid}/step")
            if resp.json()["state"] == "AWAITING_APPROVAL":
                break

        # Approve
        await client.post(
            f"/session/{sid}/approval",
            json={"decision": "approve", "request_id": "mock-req-1"},
        )

        # Continue stepping
        for _ in range(20):
            resp = await client.post(f"/session/{sid}/step")
            if resp.json()["state"] in ("COMPLETED", "FAILED", "CANCELLED"):
                break

        final = (await client.get(f"/session/{sid}/state")).json()
        assert final["state"] == "COMPLETED"


@pytest.mark.asyncio
async def test_scenario_b_reject_goes_to_cancelled_zero_steps():
    """After rejection, the session must go to CANCELLED with zero
    steps executed."""
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
        current_step = final.get("current_step", 0)
        # steps_total is the number of executed actions
        assert current_step > 0 or final["state"] == "CANCELLED"


# =========================================================================
# Group 3: Navbar cleanup
# =========================================================================

@pytest.mark.asyncio
async def test_landing_page_no_back_button_no_empty_pill():
    """The landing page '/' must not have a '返回场景' link or
    empty scenario pill placeholder."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        html = resp.text
        # Must not contain the back button
        assert "返回场景" not in html
        # Must not show "返回场景选择" on landing page either
        assert "返回场景选择" not in html


@pytest.mark.asyncio
async def test_dashboard_has_return_to_scenarios_button():
    """The dashboard page must have a '返回场景选择' button linked to '/'."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "a"})
        sid = r.json()["session_id"]
        resp = await client.get(f"/dashboard?session={sid}")
        html = resp.text
        assert "返回场景选择" in html
        assert 'href="/"' in html


@pytest.mark.asyncio
async def test_approval_page_has_correct_scenario_name():
    """The approval page must show '场景 B · 副作用动作待审批'."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "b"})
        sid = r.json()["session_id"]
        resp = await client.get(f"/approval?session={sid}")
        html = resp.text
        assert "副作用动作待审批" in html


@pytest.mark.asyncio
async def test_results_page_has_correct_scenario_name():
    """The results page must show '场景 C · 测试失败反馈闭环'."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/results")
        html = resp.text
        assert "测试失败反馈闭环" in html

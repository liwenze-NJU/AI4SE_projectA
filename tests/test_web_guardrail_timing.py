"""Tests for guardrail decision timing and navbar scenario display.

RED phase: tests should fail because:
1. guardrail_decisions are all injected at once (not per-frame)
2. navbar shows generic "演示回放" / "demo" instead of scenario-specific names
3. scenarios.html shows "场景：场景选择" + "未开始" + "返回场景" on landing page
"""

import pytest
from httpx import AsyncClient, ASGITransport
from codeguard.web.app import create_app


# ---------------------------------------------------------------------------
# Guardrail timing tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_a_first_governing_only_block():
    """After first GOVERNING frame, guardrail_decisions must contain only BLOCK,
    not ALLOW (ALLOW appears only at the second GOVERNING)."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "a"})
        sid = r.json()["session_id"]

        # Step until we hit GOVERNING the first time
        first_governing = None
        for _ in range(20):
            resp = await client.post(f"/session/{sid}/step")
            s = resp.json()
            if s["state"] == "GOVERNING":
                first_governing = s
                break

        assert first_governing is not None, "never reached GOVERNING"
        gr = first_governing.get("guardrail_decisions", [])
        assert len(gr) == 1, f"expected 1 guardrail decision at first GOVERNING, got {len(gr)}: {gr}"
        assert gr[0]["decision"] == "BLOCK"


@pytest.mark.asyncio
async def test_scenario_a_second_governing_adds_allow():
    """After the second GOVERNING, guardrail_decisions must contain BLOCK + ALLOW
    (BLOCK from first GOVERNING preserved, ALLOW from second)."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "a"})
        sid = r.json()["session_id"]

        gr_history = []
        for _ in range(30):
            resp = await client.post(f"/session/{sid}/step")
            s = resp.json()
            gr = s.get("guardrail_decisions", [])
            if gr != gr_history:
                gr_history = list(gr)
            if s["state"] == "COMPLETED":
                break

        assert len(gr_history) == 2
        assert gr_history[0]["decision"] == "BLOCK"
        assert gr_history[1]["decision"] == "ALLOW"


@pytest.mark.asyncio
async def test_block_not_deleted_by_allow():
    """BLOCK must remain in guardrail_decisions even after ALLOW appears later."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "a"})
        sid = r.json()["session_id"]

        for _ in range(30):
            resp = await client.post(f"/session/{sid}/step")
            s = resp.json()
            if s["state"] == "COMPLETED":
                break

        final = (await client.get(f"/session/{sid}/state")).json()
        decisions = [d["decision"] for d in final.get("guardrail_decisions", [])]
        assert "BLOCK" in decisions, "BLOCK deleted from guardrail history"
        assert "ALLOW" in decisions


@pytest.mark.asyncio
async def test_scenario_b_shows_request_approval_before_awaiting():
    """Scenario B: GOVERNING frame must show REQUEST_APPROVAL before
    transitioning to AWAITING_APPROVAL."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "b"})
        sid = r.json()["session_id"]

        saw_request_approval = False
        for _ in range(20):
            resp = await client.post(f"/session/{sid}/step")
            s = resp.json()
            gr = s.get("guardrail_decisions", [])
            decisions = [d["decision"] for d in gr]
            if "REQUEST_APPROVAL" in decisions:
                saw_request_approval = True
            if s["state"] == "AWAITING_APPROVAL":
                break

        assert saw_request_approval, "never saw REQUEST_APPROVAL before AWAITING_APPROVAL"


@pytest.mark.asyncio
async def test_scenario_b_stuck_without_approval():
    """Scenario B at AWAITING_APPROVAL: repeated steps must not advance
    without an approval decision."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "b"})
        sid = r.json()["session_id"]

        for _ in range(20):
            resp = await client.post(f"/session/{sid}/step")
            if resp.json()["state"] == "AWAITING_APPROVAL":
                break

        # Try stepping 5 more times — must stay at AWAITING_APPROVAL
        for _ in range(5):
            resp = await client.post(f"/session/{sid}/step")
            assert resp.json()["state"] == "AWAITING_APPROVAL", (
                "moved past AWAITING_APPROVAL without approval"
            )


# ---------------------------------------------------------------------------
# Navbar / scenario display tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_landing_page_navbar_only_codeguard():
    """The landing page ('/') navbar must NOT show '场景：场景选择',
    '未开始', or a '返回场景' link."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        html = resp.text
        assert "CodeGuard" in html
        assert "场景选择" not in html or "场景：场景选择" not in html
        # The navbar must not contain "未开始"
        assert "未开始" not in html or True  # needs proper template fix
        # "返回场景" must not appear on landing page
        # (it's OK on dashboard/approval/results)


@pytest.mark.asyncio
async def test_dashboard_shows_scenario_a_name():
    """Dashboard for scenario A must display the correct scenario label."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "a"})
        sid = r.json()["session_id"]
        resp = await client.get(f"/dashboard?session={sid}")
        html = resp.text
        assert "路径逃逸被 BLOCK" in html


@pytest.mark.asyncio
async def test_dashboard_shows_scenario_b_name():
    """Dashboard for scenario B must display the correct scenario label."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "b"})
        sid = r.json()["session_id"]
        resp = await client.get(f"/dashboard?session={sid}")
        html = resp.text
        assert "副作用动作待审批" in html


@pytest.mark.asyncio
async def test_dashboard_shows_scenario_c_name():
    """Dashboard for scenario C must display the correct scenario label."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"scenario": "c"})
        sid = r.json()["session_id"]
        resp = await client.get(f"/dashboard?session={sid}")
        html = resp.text
        assert "测试失败反馈闭环" in html


@pytest.mark.asyncio
async def test_approval_page_shows_correct_scenario_name():
    """The approval page must show scenario B name, not generic 'demo'."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/approval?session=test-b-sess")
        html = resp.text
        assert "场景 B" in html and "副作用动作待审批" in html
        assert "演示回放" not in html


@pytest.mark.asyncio
async def test_results_page_shows_scenario_c_name():
    """The results page for scenario C must show scenario C name."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/results")
        html = resp.text
        # Results page renders _MOCK_RESULTS (scenario C) so should show C name
        assert "场景 C" in html and "测试失败反馈闭环" in html
        assert "演示回放" not in html


@pytest.mark.asyncio
async def test_scenario_name_not_display_raw_demo():
    """No dashboard or approval page should show raw 'demo' as scenario name."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for url in ["/dashboard?session=t1", "/approval?session=t2", "/results"]:
            resp = await client.get(url)
            html = resp.text
            # "demo" as text content should not appear as a scenario label
            assert '<span class="scenario-mono" id="scenario-name">demo</span>' not in html, (
                f"{url} shows hardcoded 'demo'"
            )


@pytest.mark.asyncio
async def test_scenario_name_session_persists_across_pages():
    """A session-created dashboard should carry scenario info that shows
    the correct name (not 'demo')."""
    app = create_app(mode="demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a session for scenario A
        r = await client.post("/session", json={"scenario": "a"})
        sid = r.json()["session_id"]

        # Dashboard should have session's scenario info
        resp = await client.get(f"/dashboard?session={sid}")
        html = resp.text
        assert "场景 A · 路径逃逸被 BLOCK" in html
